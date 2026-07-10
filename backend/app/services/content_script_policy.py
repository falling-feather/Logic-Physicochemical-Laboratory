from __future__ import annotations

import base64
from copy import deepcopy
from dataclasses import dataclass
import hashlib
import hmac
import json
import re
from typing import Any, Callable
from urllib.parse import unquote, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from app.schemas.content import ContentPage
from app.services.content_script_sandbox_templates import (
    ScriptSandboxDocumentError,
    resolve_script_sandbox_document,
)


SCRIPT_POLICY_VERSION = "2026-07-10.1"
MAX_FINDINGS = 50
MAX_EXTERNAL_SCRIPT_BYTES = 1_000_000
EXTERNAL_SCRIPT_FETCH_TIMEOUT_SECONDS = 10
SCRIPT_REFERENCE_KEYS = {"script", "scriptpath", "scripturl", "scriptsrc", "inlinescript"}
INLINE_SCRIPT_KEYS = {"inlinescript"}
SCRIPT_LOCATION_KEYS = {"script", "scriptpath", "scripturl", "scriptsrc"}
SCRIPT_SANDBOX_KEYS = {"scriptsandbox"}
SCRIPT_INTEGRITY_KEYS = {"scriptintegrity", "integrity"}
SCRIPT_CROSSORIGIN_KEYS = {"scriptcrossorigin", "crossorigin"}
SCRIPT_ASSET_METADATA_KEYS = SCRIPT_INTEGRITY_KEYS | SCRIPT_CROSSORIGIN_KEYS
SCRIPT_SANDBOX_MODE = "isolated-iframe"
SCRIPT_SANDBOX_IFRAME_DIRECTIVE = "allow-scripts"
SCRIPT_SANDBOX_CSP = "default-src 'none'; script-src 'self'; connect-src 'none'; img-src 'self' data:; style-src 'self' 'unsafe-inline'"
SCRIPT_SANDBOX_SAME_ORIGIN_CSP = (
    "default-src 'none'; script-src 'self'; connect-src 'self'; img-src 'self' data:; "
    "style-src 'self' 'unsafe-inline'"
)
BLOCKED_PROTOCOLS = ("javascript:", "data:", "vbscript:", "blob:")
SRI_PATTERN = re.compile(r"^(sha256|sha384|sha512)-[A-Za-z0-9+/]+={0,2}$")
BLOCKED_SANDBOX_CAPABILITIES = {
    "allowSameOrigin": "Script sandboxes cannot grant same-origin access with allow-scripts.",
    "allowTopNavigation": "Script sandboxes cannot navigate the top-level browsing context.",
    "allowPopups": "Script sandboxes cannot open popups in the first content protocol phase.",
    "allowDownloads": "Script sandboxes cannot trigger downloads in the first content protocol phase.",
}
SCRIPT_SANDBOX_ALLOWED_FIELDS = {
    "mode",
    "network",
    "storage",
    "document",
    *BLOCKED_SANDBOX_CAPABILITIES,
}
ExternalScriptFetcher = Callable[[str], bytes]

_SEVERITY_ORDER = {"info": 0, "medium": 1, "high": 2, "blocked": 3}
_RISK_BY_SEVERITY = {
    "info": "none",
    "medium": "medium",
    "high": "high",
    "blocked": "blocked",
}


@dataclass(frozen=True)
class ScriptPolicyFinding:
    code: str
    severity: str
    path: str
    message: str
    key: str | None = None
    value_type: str | None = None
    value_preview: str | None = None
    value_sha256: str | None = None
    metadata: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            key: value
            for key, value in {
                "code": self.code,
                "severity": self.severity,
                "path": self.path,
                "message": self.message,
                "key": self.key,
                "value_type": self.value_type,
                "value_preview": self.value_preview,
                "value_sha256": self.value_sha256,
                "metadata": self.metadata,
            }.items()
            if value is not None
        }


@dataclass(frozen=True)
class ScriptPolicyResult:
    policy_version: str
    policy_context_hash: str
    status: str
    risk_level: str
    findings: list[ScriptPolicyFinding]
    sandbox: dict[str, Any]

    @property
    def requires_review(self) -> bool:
        return any(finding.severity in {"medium", "high"} for finding in self.findings)

    @property
    def has_blocking_findings(self) -> bool:
        return any(finding.severity == "blocked" for finding in self.findings)

    @property
    def has_script_findings(self) -> bool:
        return bool(self.findings)

    def to_json(self, *, schema_hash: str | None = None) -> dict[str, Any]:
        return {
            "policy_version": self.policy_version,
            "policy_context_hash": self.policy_context_hash,
            "schema_hash": schema_hash,
            "status": self.status,
            "risk_level": self.risk_level,
            "finding_count": len(self.findings),
            "sandbox": self.sandbox,
            "findings": [finding.to_dict() for finding in self.findings],
        }


def analyze_content_script_policy(
    page_schema: ContentPage | dict[str, Any],
    *,
    allowed_external_hosts: list[str] | tuple[str, ...] | set[str] | None = None,
    verify_external_assets: bool = False,
    external_script_fetcher: ExternalScriptFetcher | None = None,
) -> ScriptPolicyResult:
    if isinstance(page_schema, ContentPage):
        payload = page_schema.model_dump(mode="json")
    else:
        payload = page_schema
    findings: list[ScriptPolicyFinding] = []
    allowed_hosts = {host.strip().lower() for host in allowed_external_hosts or [] if host.strip()}
    _scan_value(
        payload,
        "$",
        findings,
        allowed_external_hosts=allowed_hosts,
        verify_external_assets=verify_external_assets,
        external_script_fetcher=external_script_fetcher or _default_external_script_fetcher,
    )
    risk_level = _risk_level(findings)
    status = "blocked" if risk_level == "blocked" else "review_required" if findings else "clean"
    sandbox = _sandbox_summary(findings)
    return ScriptPolicyResult(
        policy_version=SCRIPT_POLICY_VERSION,
        policy_context_hash=script_policy_context_hash(allowed_external_hosts=allowed_hosts),
        status=status,
        risk_level=risk_level,
        findings=findings,
        sandbox=sandbox,
    )


def script_policy_context_hash(
    *,
    allowed_external_hosts: list[str] | tuple[str, ...] | set[str] | None = None,
) -> str:
    normalized_hosts = sorted({host.strip().lower() for host in allowed_external_hosts or [] if host.strip()})
    payload = json.dumps(
        {"allowed_external_hosts": normalized_hosts},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def script_policy_result_from_json(payload: dict[str, Any] | None) -> ScriptPolicyResult | None:
    if not payload:
        return None
    findings = [
        ScriptPolicyFinding(
            code=str(item.get("code", "unknown")),
            severity=str(item.get("severity", "info")),
            path=str(item.get("path", "$")),
            message=str(item.get("message", "")),
            key=item.get("key"),
            value_type=item.get("value_type"),
            value_preview=item.get("value_preview"),
            value_sha256=item.get("value_sha256"),
            metadata=item.get("metadata") if isinstance(item.get("metadata"), dict) else None,
        )
        for item in payload.get("findings", [])
        if isinstance(item, dict)
    ]
    return ScriptPolicyResult(
        policy_version=str(payload.get("policy_version", SCRIPT_POLICY_VERSION)),
        policy_context_hash=str(payload.get("policy_context_hash", "")),
        status=str(payload.get("status", "clean")),
        risk_level=str(payload.get("risk_level", _risk_level(findings))),
        findings=findings,
        sandbox=payload.get("sandbox") if isinstance(payload.get("sandbox"), dict) else _sandbox_summary(findings),
    )


def public_content_page_schema(page_schema: ContentPage | dict[str, Any]) -> ContentPage:
    payload = page_schema.model_dump(mode="json") if isinstance(page_schema, ContentPage) else deepcopy(page_schema)
    _strip_public_script_fields(payload)
    return ContentPage.model_validate(payload)


def collect_content_script_manifests(
    page_schema: ContentPage | dict[str, Any],
    *,
    include_private_values: bool = False,
) -> list[dict[str, Any]]:
    payload = page_schema.model_dump(mode="json") if isinstance(page_schema, ContentPage) else page_schema
    manifests: list[dict[str, Any]] = []
    _collect_content_script_manifests(payload, manifests, include_private_values=include_private_values)
    return manifests


def _scan_value(
    value: Any,
    path: str,
    findings: list[ScriptPolicyFinding],
    key: str | None = None,
    *,
    allowed_external_hosts: set[str],
    verify_external_assets: bool,
    external_script_fetcher: ExternalScriptFetcher,
) -> None:
    if len(findings) >= MAX_FINDINGS:
        return
    if isinstance(value, dict):
        for raw_key, nested_value in value.items():
            if len(findings) >= MAX_FINDINGS:
                return
            child_key = str(raw_key)
            child_path = f"{path}.{child_key}"
            normalized_key = _normalize_key(child_key)
            if normalized_key in SCRIPT_REFERENCE_KEYS:
                findings.append(_script_reference_finding(child_path, child_key, nested_value, normalized_key))
                _scan_script_reference_value(
                    nested_value,
                    child_path,
                    child_key,
                    normalized_key,
                    findings,
                    container=value,
                    container_path=path,
                    allowed_external_hosts=allowed_external_hosts,
                    verify_external_assets=verify_external_assets,
                    external_script_fetcher=external_script_fetcher,
                )
                if normalized_key in SCRIPT_LOCATION_KEYS:
                    _scan_script_sandbox_contract(value, path, child_path, findings)
            elif _looks_like_event_handler(child_key):
                findings.append(
                    _finding(
                        code="event_handler",
                        severity="high",
                        path=child_path,
                        key=child_key,
                        value=nested_value,
                        message="Inline event handler props require review and are not part of the stable schema.",
                    )
                )
            _scan_value(
                nested_value,
                child_path,
                findings,
                child_key,
                allowed_external_hosts=allowed_external_hosts,
                verify_external_assets=verify_external_assets,
                external_script_fetcher=external_script_fetcher,
            )
        return
    if isinstance(value, list):
        for index, nested_value in enumerate(value):
            if len(findings) >= MAX_FINDINGS:
                return
            _scan_value(
                nested_value,
                f"{path}[{index}]",
                findings,
                key,
                allowed_external_hosts=allowed_external_hosts,
                verify_external_assets=verify_external_assets,
                external_script_fetcher=external_script_fetcher,
            )
        return
    if isinstance(value, str):
        _scan_string(value, path, key, findings)


def _scan_script_reference_value(
    value: Any,
    path: str,
    key: str,
    normalized_key: str,
    findings: list[ScriptPolicyFinding],
    *,
    container: dict[str, Any],
    container_path: str,
    allowed_external_hosts: set[str],
    verify_external_assets: bool,
    external_script_fetcher: ExternalScriptFetcher,
) -> None:
    if normalized_key in INLINE_SCRIPT_KEYS:
        findings.append(
            _finding(
                code="inline_script",
                severity="blocked",
                path=path,
                key=key,
                value=value,
                message="Inline script bodies are blocked in content drafts; use a reviewed script asset reference.",
                omit_preview=True,
            )
        )
        return
    if not isinstance(value, str):
        return
    stripped = value.strip()
    lowered = stripped.lower()
    if _uses_blocked_protocol(lowered):
        findings.append(
            _finding(
                code="blocked_script_protocol",
                severity="blocked",
                path=path,
                key=key,
                value=value,
                message="Script references cannot use javascript:, data:, vbscript:, or blob: protocols.",
            )
        )
    if ".." in unquote(stripped).replace("\\", "/").split("/"):
        findings.append(
            _finding(
                code="script_path_traversal",
                severity="blocked",
                path=path,
                key=key,
                value=value,
                message="Script references cannot traverse parent directories.",
            )
        )
    if normalized_key in SCRIPT_LOCATION_KEYS and _is_external_url(stripped):
        findings.append(
            _finding(
                code="external_script_url",
                severity="high",
                path=path,
                key=key,
                value=value,
                message="External script URLs require explicit administrative review.",
            )
        )
        _scan_external_script_asset(
            stripped,
            path,
            key,
            findings,
            container=container,
            container_path=container_path,
            allowed_external_hosts=allowed_external_hosts,
            verify_external_assets=verify_external_assets,
            external_script_fetcher=external_script_fetcher,
        )


def _scan_external_script_asset(
    url: str,
    path: str,
    key: str,
    findings: list[ScriptPolicyFinding],
    *,
    container: dict[str, Any],
    container_path: str,
    allowed_external_hosts: set[str],
    verify_external_assets: bool,
    external_script_fetcher: ExternalScriptFetcher,
) -> None:
    parsed = _parse_external_url(url)
    contract_is_verifiable = True
    if parsed is None or parsed.scheme != "https":
        contract_is_verifiable = False
        findings.append(
            _finding(
                code="external_script_insecure_scheme",
                severity="blocked",
                path=path,
                key=key,
                value=url,
                message="External script URLs must use an explicit https:// URL.",
            )
        )
    if parsed is not None and (parsed.query or parsed.fragment):
        contract_is_verifiable = False
        findings.append(
            _finding(
                code="external_script_query_or_fragment",
                severity="blocked",
                path=path,
                key=key,
                value=url,
                message="External script URLs must not include query strings or fragments.",
            )
        )
    host = parsed.hostname.lower() if parsed is not None and parsed.hostname else ""
    if not host or not _host_allowed(host, allowed_external_hosts):
        contract_is_verifiable = False
        findings.append(
            _finding(
                code="external_script_host_not_allowed",
                severity="blocked",
                path=path,
                key=key,
                value=url,
                message="External script URLs must use a configured allowed host.",
            )
        )

    integrity_key, integrity = _container_value_by_normalized_key(container, SCRIPT_INTEGRITY_KEYS)
    integrity_path = f"{container_path}.{integrity_key}" if integrity_key is not None else path
    if integrity_key is None:
        contract_is_verifiable = False
        findings.append(
            _finding(
                code="script_integrity_missing",
                severity="blocked",
                path=path,
                key=key,
                value=url,
                message="External script URLs must declare a Subresource Integrity hash.",
            )
        )
    elif not isinstance(integrity, str) or not _valid_sri(integrity):
        contract_is_verifiable = False
        findings.append(
            _finding(
                code="script_integrity_invalid",
                severity="blocked",
                path=integrity_path,
                key=integrity_key,
                value=integrity,
                message="Script integrity must be a sha256, sha384, or sha512 SRI token.",
            )
        )

    crossorigin_key, crossorigin = _container_value_by_normalized_key(container, SCRIPT_CROSSORIGIN_KEYS)
    crossorigin_path = f"{container_path}.{crossorigin_key}" if crossorigin_key is not None else path
    if crossorigin_key is None:
        contract_is_verifiable = False
        findings.append(
            _finding(
                code="script_crossorigin_missing",
                severity="blocked",
                path=path,
                key=key,
                value=url,
                message="External script URLs must declare crossorigin=anonymous for SRI.",
            )
        )
    elif not isinstance(crossorigin, str) or crossorigin.strip().lower() != "anonymous":
        contract_is_verifiable = False
        findings.append(
            _finding(
                code="script_crossorigin_invalid",
                severity="blocked",
                path=crossorigin_path,
                key=crossorigin_key,
                value=crossorigin,
                message="External script crossorigin must be anonymous.",
            )
        )

    if verify_external_assets and contract_is_verifiable and isinstance(integrity, str):
        _verify_external_script_asset(url, integrity, path, key, findings, external_script_fetcher)


def _verify_external_script_asset(
    url: str,
    integrity: str,
    path: str,
    key: str,
    findings: list[ScriptPolicyFinding],
    external_script_fetcher: ExternalScriptFetcher,
) -> None:
    try:
        asset_bytes = external_script_fetcher(url)
    except Exception:
        findings.append(
            _finding(
                code="external_script_asset_unavailable",
                severity="blocked",
                path=path,
                key=key,
                value=url,
                message="External script asset could not be downloaded for SRI verification.",
            )
        )
        return
    verification_metadata = external_script_asset_verification_metadata(integrity, asset_bytes)
    if "matched_algorithm" not in verification_metadata:
        findings.append(
            _finding(
                code="script_integrity_mismatch",
                severity="blocked",
                path=path,
                key=key,
                value=url,
                message="External script asset bytes do not match the declared SRI hash.",
                metadata=verification_metadata,
            )
        )
        return
    findings.append(
        _finding(
            code="script_integrity_verified",
            severity="info",
            path=path,
            key=key,
            value=url,
            message="External script asset was downloaded and matched the declared SRI hash.",
            metadata=verification_metadata,
        )
    )


def _scan_string(value: str, path: str, key: str | None, findings: list[ScriptPolicyFinding]) -> None:
    stripped = value.strip()
    lowered = stripped.lower()
    if _uses_blocked_protocol(lowered):
        findings.append(
            _finding(
                code="blocked_protocol",
                severity="blocked",
                path=path,
                key=key,
                value=value,
                message="Content props cannot include javascript:, data:, vbscript:, or blob: values.",
            )
        )
    if "<script" in lowered:
        findings.append(
            _finding(
                code="inline_script_tag",
                severity="blocked",
                path=path,
                key=key,
                value=value,
                message="Inline script tags are blocked in content props.",
                omit_preview=True,
            )
        )


def _scan_script_sandbox_contract(
    container: dict[str, Any],
    container_path: str,
    script_path: str,
    findings: list[ScriptPolicyFinding],
) -> None:
    sandbox_key, sandbox = _script_sandbox_contract(container)
    if sandbox_key is None:
        findings.append(
            _finding(
                code="script_sandbox_missing",
                severity="blocked",
                path=script_path,
                message="Script references must declare a scriptSandbox contract for isolated execution.",
            )
        )
        return
    sandbox_path = f"{container_path}.{sandbox_key}"
    if not isinstance(sandbox, dict):
        findings.append(
            _finding(
                code="script_sandbox_invalid",
                severity="blocked",
                path=sandbox_path,
                key=sandbox_key,
                value=sandbox,
                message="scriptSandbox must be an object with an isolated-iframe mode.",
            )
        )
        return
    for unsupported_field in _unsupported_script_sandbox_fields(sandbox):
        findings.append(
            _finding(
                code="script_sandbox_unsupported_field",
                severity="blocked",
                path=f"{sandbox_path}.{unsupported_field}",
                key=unsupported_field,
                value=sandbox.get(unsupported_field),
                message="scriptSandbox contains an unsupported field; executable markup and entry points must use a registered document template.",
                omit_preview=True,
            )
        )
    mode = sandbox.get("mode")
    if mode != SCRIPT_SANDBOX_MODE:
        findings.append(
            _finding(
                code="script_sandbox_invalid_mode",
                severity="blocked",
                path=f"{sandbox_path}.mode",
                key="mode",
                value=mode,
                message="scriptSandbox.mode must be isolated-iframe.",
            )
        )
    for capability, message in BLOCKED_SANDBOX_CAPABILITIES.items():
        if _is_enabled(sandbox.get(capability)):
            findings.append(
                _finding(
                    code="script_sandbox_unsafe_capability",
                    severity="blocked",
                    path=f"{sandbox_path}.{capability}",
                    key=capability,
                    value=sandbox.get(capability),
                    message=message,
                )
            )
    network = sandbox.get("network", "none")
    if network not in {"none", "same-origin"}:
        findings.append(
            _finding(
                code="script_sandbox_unsafe_network",
                severity="blocked",
                path=f"{sandbox_path}.network",
                key="network",
                value=network,
                message="scriptSandbox.network must be none or same-origin.",
            )
        )
    storage = sandbox.get("storage", "none")
    if storage != "none":
        findings.append(
            _finding(
                code="script_sandbox_unsafe_storage",
                severity="blocked",
                path=f"{sandbox_path}.storage",
                key="storage",
                value=storage,
                message="scriptSandbox.storage must be none for reviewed content scripts.",
            )
        )
    if "document" in sandbox:
        try:
            resolve_script_sandbox_document(sandbox.get("document"))
        except ScriptSandboxDocumentError as exc:
            findings.append(
                _finding(
                    code=exc.code,
                    severity="blocked",
                    path=f"{sandbox_path}.document",
                    key="document",
                    value=sandbox.get("document"),
                    message=exc.message,
                    omit_preview=True,
                )
            )


def _script_sandbox_contract(container: dict[str, Any]) -> tuple[str | None, Any]:
    for key, value in container.items():
        if _normalize_key(str(key)) in SCRIPT_SANDBOX_KEYS:
            return str(key), value
    return None, None


def _sandbox_summary(findings: list[ScriptPolicyFinding]) -> dict[str, Any]:
    script_reference_count = sum(1 for finding in findings if finding.code == "script_reference")
    sandbox_violation_count = sum(1 for finding in findings if finding.code.startswith("script_sandbox_"))
    if script_reference_count == 0:
        return {
            "required": False,
            "status": "not_required",
            "script_reference_count": 0,
            "violation_count": sandbox_violation_count,
        }
    blocked = any(finding.severity == "blocked" for finding in findings)
    status = "blocked" if blocked or sandbox_violation_count else "isolated"
    summary: dict[str, Any] = {
        "required": True,
        "status": status,
        "script_reference_count": script_reference_count,
        "violation_count": sandbox_violation_count,
    }
    if status == "isolated":
        summary.update(
            {
                "mode": SCRIPT_SANDBOX_MODE,
                "iframe_sandbox": SCRIPT_SANDBOX_IFRAME_DIRECTIVE,
                "csp": SCRIPT_SANDBOX_CSP,
            }
        )
    return summary


def _strip_public_script_fields(value: Any) -> None:
    if isinstance(value, list):
        for item in value:
            _strip_public_script_fields(item)
        return
    if not isinstance(value, dict):
        return

    script_references: list[dict[str, Any]] = []
    sandbox: dict[str, Any] | None = None
    contains_script_reference = any(_normalize_key(str(key)) in SCRIPT_REFERENCE_KEYS for key in value)
    for raw_key in list(value):
        normalized_key = _normalize_key(str(raw_key))
        nested_value = value[raw_key]
        if normalized_key in SCRIPT_REFERENCE_KEYS:
            script_references.append(_public_script_reference(str(raw_key), nested_value))
            del value[raw_key]
            continue
        if normalized_key in SCRIPT_SANDBOX_KEYS:
            sandbox = nested_value if isinstance(nested_value, dict) else None
            del value[raw_key]
            continue
        if contains_script_reference and normalized_key in SCRIPT_ASSET_METADATA_KEYS:
            del value[raw_key]
            continue
        _strip_public_script_fields(nested_value)

    if script_references:
        value["scriptManifest"] = _public_script_manifest(script_references, _public_sandbox_manifest(sandbox))


def _collect_content_script_manifests(
    value: Any,
    manifests: list[dict[str, Any]],
    *,
    include_private_values: bool,
) -> None:
    if isinstance(value, list):
        for item in value:
            _collect_content_script_manifests(item, manifests, include_private_values=include_private_values)
        return
    if not isinstance(value, dict):
        return

    script_references: list[dict[str, Any]] = []
    sandbox: dict[str, Any] | None = None
    contains_script_reference = any(_normalize_key(str(key)) in SCRIPT_REFERENCE_KEYS for key in value)
    for raw_key, nested_value in value.items():
        normalized_key = _normalize_key(str(raw_key))
        if normalized_key in SCRIPT_REFERENCE_KEYS:
            script_references.append(
                _script_reference_manifest(
                    str(raw_key),
                    nested_value,
                    container=value,
                    include_private_value=include_private_values,
                )
            )
            continue
        if normalized_key in SCRIPT_SANDBOX_KEYS:
            sandbox = nested_value if isinstance(nested_value, dict) else None
            continue
        if contains_script_reference and normalized_key in SCRIPT_ASSET_METADATA_KEYS:
            continue
        _collect_content_script_manifests(nested_value, manifests, include_private_values=include_private_values)

    if script_references:
        manifests.append(_public_script_manifest(script_references, _public_sandbox_manifest(sandbox)))


def _public_script_manifest(script_references: list[dict[str, Any]], sandbox: dict[str, Any]) -> dict[str, Any]:
    return {
        "sandboxId": _script_manifest_id(script_references, sandbox),
        "executionMode": "sandbox-required",
        "sandbox": sandbox,
        "referenceCount": len(script_references),
        "references": script_references,
    }


def _script_reference_manifest(
    key: str,
    value: Any,
    *,
    container: dict[str, Any] | None = None,
    include_private_value: bool,
) -> dict[str, Any]:
    reference = _public_script_reference(key, value)
    if include_private_value and isinstance(value, str):
        reference["value"] = value
        if container is not None:
            integrity_key, integrity = _container_value_by_normalized_key(container, SCRIPT_INTEGRITY_KEYS)
            crossorigin_key, crossorigin = _container_value_by_normalized_key(container, SCRIPT_CROSSORIGIN_KEYS)
            if integrity_key is not None and isinstance(integrity, str):
                reference["integrity"] = integrity
            if crossorigin_key is not None and isinstance(crossorigin, str):
                reference["crossorigin"] = crossorigin
    return reference


def _script_manifest_id(script_references: list[dict[str, Any]], sandbox: dict[str, Any]) -> str:
    public_references = [
        {
            key: value
            for key, value in reference.items()
            if key not in {"value", "integrity", "crossorigin"}
        }
        for reference in script_references
    ]
    payload = json.dumps(
        {
            "references": public_references,
            "sandbox": sandbox,
            "policyVersion": SCRIPT_POLICY_VERSION,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return f"sm_{hashlib.sha256(payload.encode('utf-8')).hexdigest()[:24]}"


def _public_script_reference(key: str, value: Any) -> dict[str, Any]:
    value_text = value if isinstance(value, str) else None
    return {
        key: item
        for key, item in {
            "key": key,
            "valueType": type(value).__name__,
            "valueSha256": _sha256(value_text),
        }.items()
        if item is not None
    }


def _public_sandbox_manifest(sandbox: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(sandbox, dict) or sandbox.get("mode") != SCRIPT_SANDBOX_MODE:
        return {"status": "blocked"}
    if _unsupported_script_sandbox_fields(sandbox):
        return {"status": "blocked", "code": "script_sandbox_unsupported_field"}
    network = sandbox.get("network", "none")
    if (
        any(_is_enabled(sandbox.get(capability)) for capability in BLOCKED_SANDBOX_CAPABILITIES)
        or network not in {"none", "same-origin"}
        or sandbox.get("storage", "none") != "none"
    ):
        return {"status": "blocked"}
    effective_network = network
    csp = _script_sandbox_csp(effective_network)
    manifest = {
        "status": "isolated",
        "mode": SCRIPT_SANDBOX_MODE,
        "iframeSandbox": SCRIPT_SANDBOX_IFRAME_DIRECTIVE,
        "csp": csp,
        "network": effective_network,
        "storage": "none",
        "enforcement": {
            "browserContext": "sandboxed-iframe",
            "requiredIframeSandbox": SCRIPT_SANDBOX_IFRAME_DIRECTIVE,
            "requiredContentSecurityPolicy": csp,
            "sandboxOrigin": "opaque",
        },
        "capabilities": {
            "scripts": True,
            "sameOrigin": False,
            "topNavigation": False,
            "popups": False,
            "downloads": False,
            "network": effective_network,
            "storage": "none",
        },
    }
    if "document" in sandbox:
        try:
            document = resolve_script_sandbox_document(sandbox.get("document"))
        except ScriptSandboxDocumentError as exc:
            return {"status": "blocked", "code": exc.code}
        manifest["document"] = document.public_contract()
    return manifest


def _script_sandbox_csp(network: str) -> str:
    if network == "same-origin":
        return SCRIPT_SANDBOX_SAME_ORIGIN_CSP
    return SCRIPT_SANDBOX_CSP


def _unsupported_script_sandbox_fields(sandbox: dict[str, Any]) -> list[str]:
    return sorted(str(key) for key in sandbox if key not in SCRIPT_SANDBOX_ALLOWED_FIELDS)


def _script_reference_finding(path: str, key: str, value: Any, normalized_key: str) -> ScriptPolicyFinding:
    if normalized_key in INLINE_SCRIPT_KEYS:
        return _finding(
            code="script_reference",
            severity="high",
            path=path,
            key=key,
            value=value,
            message="Inline script references are high risk and require replacement with reviewed assets.",
            omit_preview=True,
        )
    return _finding(
        code="script_reference",
        severity="medium",
        path=path,
        key=key,
        value=value,
        message="Script asset references require administrative review before publication.",
    )


def _finding(
    *,
    code: str,
    severity: str,
    path: str,
    message: str,
    key: str | None = None,
    value: Any = None,
    omit_preview: bool = False,
    metadata: dict[str, Any] | None = None,
) -> ScriptPolicyFinding:
    value_type = type(value).__name__ if value is not None else None
    value_text = value if isinstance(value, str) else None
    return ScriptPolicyFinding(
        code=code,
        severity=severity,
        path=path,
        message=message,
        key=key,
        value_type=value_type,
        value_preview=None if omit_preview else _preview(value_text),
        value_sha256=_sha256(value_text) if value_text is not None else None,
        metadata=metadata,
    )


def _risk_level(findings: list[ScriptPolicyFinding]) -> str:
    if not findings:
        return "none"
    max_severity = max(findings, key=lambda item: _SEVERITY_ORDER.get(item.severity, 0)).severity
    return _RISK_BY_SEVERITY.get(max_severity, "none")


def _normalize_key(key: str) -> str:
    return key.replace("_", "").replace("-", "").lower()


def _looks_like_event_handler(key: str) -> bool:
    return len(key) > 2 and key.lower().startswith("on") and key[2:3].isalpha()


def _is_enabled(value: Any) -> bool:
    if value is True:
        return True
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "allow", "allowed", "enabled"}
    return False


def _uses_blocked_protocol(value: str) -> bool:
    return value.startswith(BLOCKED_PROTOCOLS)


def _is_external_url(value: str) -> bool:
    lowered = value.lower()
    return lowered.startswith("http://") or lowered.startswith("https://") or lowered.startswith("//")


def _parse_external_url(value: str):
    if value.startswith("//"):
        return urlsplit(value)
    return urlsplit(value)


def _host_allowed(host: str, allowed_hosts: set[str]) -> bool:
    if not allowed_hosts:
        return False
    return host in allowed_hosts


def _container_value_by_normalized_key(container: dict[str, Any], normalized_keys: set[str]) -> tuple[str | None, Any]:
    for key, value in container.items():
        if _normalize_key(str(key)) in normalized_keys:
            return str(key), value
    return None, None


def _valid_sri(value: str) -> bool:
    tokens = [token.strip() for token in value.split() if token.strip()]
    return bool(tokens) and all(SRI_PATTERN.match(token) for token in tokens)


def external_script_asset_verification_metadata(integrity: str, asset_bytes: bytes) -> dict[str, Any]:
    return _external_script_asset_verification_metadata(integrity, asset_bytes)


def _external_script_asset_verification_metadata(integrity: str, asset_bytes: bytes) -> dict[str, Any]:
    tokens = [item.strip() for item in integrity.split() if item.strip()]
    metadata: dict[str, Any] = {
        "asset_sha256": hashlib.sha256(asset_bytes).hexdigest(),
        "asset_size_bytes": len(asset_bytes),
        "integrity_token_count": len(tokens),
    }
    for token in tokens:
        algorithm, _ = token.split("-", 1)
        if _sri_token_matches_asset(token, asset_bytes):
            metadata["matched_algorithm"] = algorithm
            break
    return metadata


def _sri_token_matches_asset(token: str, asset_bytes: bytes) -> bool:
    algorithm, encoded_digest = token.split("-", 1)
    padding = "=" * ((4 - len(encoded_digest) % 4) % 4)
    try:
        expected_digest = base64.b64decode(encoded_digest + padding, validate=True)
    except Exception:
        return False
    actual_digest = hashlib.new(algorithm, asset_bytes).digest()
    return hmac.compare_digest(actual_digest, expected_digest)


def _default_external_script_fetcher(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": "Astra-content-script-verifier/1.0"})
    opener = build_opener(_NoRedirectHandler)
    with opener.open(request, timeout=EXTERNAL_SCRIPT_FETCH_TIMEOUT_SECONDS) as response:
        payload = response.read(MAX_EXTERNAL_SCRIPT_BYTES + 1)
    if len(payload) > MAX_EXTERNAL_SCRIPT_BYTES:
        raise ValueError("external script asset exceeds maximum verification size")
    return payload


class _NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _preview(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = " ".join(value.strip().split())
    if _is_external_url(normalized):
        normalized = normalized.split("?", 1)[0].split("#", 1)[0]
    if len(normalized) > 96:
        return f"{normalized[:93]}..."
    return normalized


def _sha256(value: str | None) -> str | None:
    if value is None:
        return None
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
