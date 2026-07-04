from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Any

from app.schemas.content import ContentPage


SCRIPT_POLICY_VERSION = "2026-07-04.1"
MAX_FINDINGS = 50
SCRIPT_REFERENCE_KEYS = {"script", "scriptpath", "scripturl", "scriptsrc", "inlinescript"}
INLINE_SCRIPT_KEYS = {"inlinescript"}
SCRIPT_LOCATION_KEYS = {"script", "scriptpath", "scripturl", "scriptsrc"}
BLOCKED_PROTOCOLS = ("javascript:", "data:", "vbscript:")

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
            }.items()
            if value is not None
        }


@dataclass(frozen=True)
class ScriptPolicyResult:
    policy_version: str
    status: str
    risk_level: str
    findings: list[ScriptPolicyFinding]

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
            "schema_hash": schema_hash,
            "status": self.status,
            "risk_level": self.risk_level,
            "finding_count": len(self.findings),
            "findings": [finding.to_dict() for finding in self.findings],
        }


def analyze_content_script_policy(page_schema: ContentPage | dict[str, Any]) -> ScriptPolicyResult:
    if isinstance(page_schema, ContentPage):
        payload = page_schema.model_dump(mode="json")
    else:
        payload = page_schema
    findings: list[ScriptPolicyFinding] = []
    _scan_value(payload, "$", findings)
    risk_level = _risk_level(findings)
    status = "blocked" if risk_level == "blocked" else "review_required" if findings else "clean"
    return ScriptPolicyResult(
        policy_version=SCRIPT_POLICY_VERSION,
        status=status,
        risk_level=risk_level,
        findings=findings,
    )


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
        )
        for item in payload.get("findings", [])
        if isinstance(item, dict)
    ]
    return ScriptPolicyResult(
        policy_version=str(payload.get("policy_version", SCRIPT_POLICY_VERSION)),
        status=str(payload.get("status", "clean")),
        risk_level=str(payload.get("risk_level", _risk_level(findings))),
        findings=findings,
    )


def _scan_value(value: Any, path: str, findings: list[ScriptPolicyFinding], key: str | None = None) -> None:
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
                _scan_script_reference_value(nested_value, child_path, child_key, normalized_key, findings)
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
            _scan_value(nested_value, child_path, findings, child_key)
        return
    if isinstance(value, list):
        for index, nested_value in enumerate(value):
            if len(findings) >= MAX_FINDINGS:
                return
            _scan_value(nested_value, f"{path}[{index}]", findings, key)
        return
    if isinstance(value, str):
        _scan_string(value, path, key, findings)


def _scan_script_reference_value(
    value: Any,
    path: str,
    key: str,
    normalized_key: str,
    findings: list[ScriptPolicyFinding],
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
                message="Script references cannot use javascript:, data:, or vbscript: protocols.",
            )
        )
    if ".." in stripped.replace("\\", "/").split("/"):
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
                message="Content props cannot include javascript:, data:, or vbscript: values.",
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


def _uses_blocked_protocol(value: str) -> bool:
    return value.startswith(BLOCKED_PROTOCOLS)


def _is_external_url(value: str) -> bool:
    lowered = value.lower()
    return lowered.startswith("http://") or lowered.startswith("https://") or lowered.startswith("//")


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
