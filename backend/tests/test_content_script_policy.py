import base64
import hashlib

from app.services import content_script_policy
from app.services.content_script_policy import (
    analyze_content_script_policy,
    public_content_page_schema,
    script_policy_result_from_json,
)


def test_script_policy_accepts_clean_schema():
    result = analyze_content_script_policy(_page_payload())

    assert result.status == "clean"
    assert result.risk_level == "none"
    assert result.sandbox["status"] == "not_required"
    assert result.findings == []


def test_script_policy_blocks_script_reference_without_sandbox_contract():
    payload = _page_payload({"scriptPath": "drafts/custom-energy.js"})

    result = analyze_content_script_policy(payload)

    codes = {finding.code for finding in result.findings}
    assert result.status == "blocked"
    assert result.risk_level == "blocked"
    assert result.sandbox["status"] == "blocked"
    assert result.sandbox["required"] is True
    assert "script_reference" in codes
    assert "script_sandbox_missing" in codes


def test_script_policy_marks_local_script_reference_with_sandbox_for_review():
    payload = _page_payload(
        {
            "scriptPath": "drafts/custom-energy.js",
            "scriptSandbox": {"mode": "isolated-iframe", "network": "same-origin", "storage": "none"},
        }
    )

    result = analyze_content_script_policy(payload)

    assert result.status == "review_required"
    assert result.risk_level == "medium"
    assert result.sandbox["status"] == "isolated"
    assert result.sandbox["mode"] == "isolated-iframe"
    assert result.sandbox["iframe_sandbox"] == "allow-scripts"
    assert result.requires_review is True
    assert result.has_blocking_findings is False
    assert result.findings[0].code == "script_reference"
    assert result.findings[0].path == "$.sections[0].props.scriptPath"


def test_script_policy_flags_external_script_url_as_high_risk_without_query_preview():
    payload = _page_payload(
        {
            "scriptUrl": "https://cdn.example.test/tool.js?token=secret#frag",
            "scriptSandbox": {"mode": "isolated-iframe", "network": "none", "storage": "none"},
        }
    )

    result = analyze_content_script_policy(payload)

    codes = {finding.code for finding in result.findings}
    external_finding = next(finding for finding in result.findings if finding.code == "external_script_url")
    assert result.status == "blocked"
    assert result.risk_level == "blocked"
    assert result.sandbox["status"] == "blocked"
    assert "script_reference" in codes
    assert "external_script_url" in codes
    assert "external_script_host_not_allowed" in codes
    assert "external_script_query_or_fragment" in codes
    assert "script_integrity_missing" in codes
    assert "script_crossorigin_missing" in codes
    assert external_finding.value_preview == "https://cdn.example.test/tool.js"


def test_script_policy_allows_reviewed_external_script_asset_with_sri_contract():
    payload = _page_payload(
        {
            "scriptUrl": "https://cdn.example.test/tool.js",
            "scriptIntegrity": "sha384-AbCdEf0123456789+/=",
            "scriptCrossorigin": "anonymous",
            "scriptSandbox": {"mode": "isolated-iframe", "network": "none", "storage": "none"},
        }
    )

    result = analyze_content_script_policy(payload, allowed_external_hosts={"cdn.example.test"})

    codes = {finding.code for finding in result.findings}
    assert result.status == "review_required"
    assert result.risk_level == "high"
    assert result.sandbox["status"] == "isolated"
    assert result.requires_review is True
    assert result.has_blocking_findings is False
    assert "external_script_url" in codes
    assert "external_script_host_not_allowed" not in codes
    assert "script_integrity_missing" not in codes
    assert "script_integrity_invalid" not in codes
    assert "script_crossorigin_missing" not in codes
    assert "script_crossorigin_invalid" not in codes


def test_script_policy_verifies_external_script_asset_sri_with_fetcher():
    asset_bytes = b"console.log('verified asset');\n"
    payload = _page_payload(
        {
            "scriptUrl": "https://cdn.example.test/tool.js",
            "scriptIntegrity": _sri_sha384(asset_bytes),
            "scriptCrossorigin": "anonymous",
            "scriptSandbox": {"mode": "isolated-iframe", "network": "none", "storage": "none"},
        }
    )
    fetched_urls = []

    def fetcher(url: str) -> bytes:
        fetched_urls.append(url)
        return asset_bytes

    result = analyze_content_script_policy(
        payload,
        allowed_external_hosts={"cdn.example.test"},
        verify_external_assets=True,
        external_script_fetcher=fetcher,
    )

    codes = {finding.code for finding in result.findings}
    assert fetched_urls == ["https://cdn.example.test/tool.js"]
    assert result.status == "review_required"
    assert result.risk_level == "high"
    assert result.has_blocking_findings is False
    assert "external_script_url" in codes
    assert "script_integrity_verified" in codes
    assert "script_integrity_mismatch" not in codes
    assert "external_script_asset_unavailable" not in codes
    verified_finding = next(finding for finding in result.findings if finding.code == "script_integrity_verified")
    assert verified_finding.metadata == {
        "asset_sha256": hashlib.sha256(asset_bytes).hexdigest(),
        "asset_size_bytes": len(asset_bytes),
        "integrity_token_count": 1,
        "matched_algorithm": "sha384",
    }

    restored = script_policy_result_from_json(result.to_json(schema_hash="schema-hash"))
    assert restored is not None
    restored_verified = next(finding for finding in restored.findings if finding.code == "script_integrity_verified")
    assert restored_verified.metadata == verified_finding.metadata


def test_script_policy_blocks_external_script_asset_sri_mismatch():
    original_bytes = b"console.log('original asset');\n"
    payload = _page_payload(
        {
            "scriptUrl": "https://cdn.example.test/tool.js",
            "scriptIntegrity": _sri_sha384(original_bytes),
            "scriptCrossorigin": "anonymous",
            "scriptSandbox": {"mode": "isolated-iframe", "network": "none", "storage": "none"},
        }
    )

    result = analyze_content_script_policy(
        payload,
        allowed_external_hosts={"cdn.example.test"},
        verify_external_assets=True,
        external_script_fetcher=lambda url: b"console.log('changed asset');\n",
    )

    codes = {finding.code for finding in result.findings}
    assert result.status == "blocked"
    assert result.risk_level == "blocked"
    assert result.has_blocking_findings is True
    assert "script_integrity_mismatch" in codes
    assert "script_integrity_verified" not in codes
    mismatch_finding = next(finding for finding in result.findings if finding.code == "script_integrity_mismatch")
    assert mismatch_finding.metadata == {
        "asset_sha256": hashlib.sha256(b"console.log('changed asset');\n").hexdigest(),
        "asset_size_bytes": len(b"console.log('changed asset');\n"),
        "integrity_token_count": 1,
    }


def test_script_policy_blocks_external_script_asset_download_failure():
    asset_bytes = b"console.log('unreachable asset');\n"
    payload = _page_payload(
        {
            "scriptUrl": "https://cdn.example.test/tool.js",
            "scriptIntegrity": _sri_sha384(asset_bytes),
            "scriptCrossorigin": "anonymous",
            "scriptSandbox": {"mode": "isolated-iframe", "network": "none", "storage": "none"},
        }
    )

    def fetcher(url: str) -> bytes:
        raise OSError("cdn unavailable")

    result = analyze_content_script_policy(
        payload,
        allowed_external_hosts={"cdn.example.test"},
        verify_external_assets=True,
        external_script_fetcher=fetcher,
    )

    codes = {finding.code for finding in result.findings}
    assert result.status == "blocked"
    assert result.risk_level == "blocked"
    assert result.has_blocking_findings is True
    assert "external_script_asset_unavailable" in codes
    assert "script_integrity_verified" not in codes


def test_default_external_script_fetcher_uses_no_redirect_opener(monkeypatch):
    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self, size: int) -> bytes:
            captured["read_size"] = size
            return b"console.log('ok');"

    class FakeOpener:
        def open(self, request, timeout: int):
            captured["request"] = request
            captured["timeout"] = timeout
            return FakeResponse()

    def fake_build_opener(handler):
        captured["handler"] = handler
        return FakeOpener()

    monkeypatch.setattr(content_script_policy, "build_opener", fake_build_opener)

    payload = content_script_policy._default_external_script_fetcher("https://cdn.example.test/tool.js")

    assert payload == b"console.log('ok');"
    assert captured["handler"]().redirect_request(None, None, 302, "Found", {}, "https://other.example.test") is None
    assert captured["timeout"] == content_script_policy.EXTERNAL_SCRIPT_FETCH_TIMEOUT_SECONDS
    assert captured["read_size"] == content_script_policy.MAX_EXTERNAL_SCRIPT_BYTES + 1


def test_script_policy_blocks_external_script_asset_without_sri_contract_details():
    payload = _page_payload(
        {
            "scriptUrl": "http://cdn.example.test/tool.js",
            "scriptIntegrity": "md5-deadbeef",
            "scriptCrossorigin": "use-credentials",
            "scriptSandbox": {"mode": "isolated-iframe", "network": "none", "storage": "none"},
        }
    )

    result = analyze_content_script_policy(payload, allowed_external_hosts={"cdn.example.test"})

    codes = {finding.code for finding in result.findings}
    assert result.status == "blocked"
    assert "external_script_insecure_scheme" in codes
    assert "script_integrity_invalid" in codes
    assert "script_crossorigin_invalid" in codes


def test_public_schema_strips_script_asset_metadata_from_manifest():
    payload = _page_payload(
        {
            "scriptUrl": "https://cdn.example.test/tool.js",
            "scriptIntegrity": "sha384-AbCdEf0123456789+/=",
            "scriptCrossorigin": "anonymous",
            "scriptSandbox": {"mode": "isolated-iframe", "network": "none", "storage": "none"},
        }
    )

    public_schema = public_content_page_schema(payload).model_dump(mode="json")

    props = public_schema["sections"][0]["props"]
    assert "scriptUrl" not in props
    assert "scriptIntegrity" not in props
    assert "scriptCrossorigin" not in props
    assert "scriptSandbox" not in props
    assert props["scriptManifest"]["executionMode"] == "sandbox-required"
    assert props["scriptManifest"]["references"][0]["key"] == "scriptUrl"
    assert len(props["scriptManifest"]["references"][0]["valueSha256"]) == 64


def test_public_schema_preserves_non_script_integrity_metadata():
    payload = _page_payload(
        {
            "integrity": "rubric evidence is complete",
            "crossorigin": "not a script asset flag",
            "label": "Observation integrity",
        }
    )

    public_schema = public_content_page_schema(payload).model_dump(mode="json")

    props = public_schema["sections"][0]["props"]
    assert props["integrity"] == "rubric evidence is complete"
    assert props["crossorigin"] == "not a script asset flag"
    assert "scriptManifest" not in props


def test_script_policy_blocks_unsafe_sandbox_capabilities():
    payload = _page_payload(
        {
            "scriptPath": "drafts/custom-energy.js",
            "scriptSandbox": {
                "mode": "isolated-iframe",
                "allowSameOrigin": True,
                "allowTopNavigation": "true",
                "network": "external",
                "storage": "local",
            },
        }
    )

    result = analyze_content_script_policy(payload)

    codes = {finding.code for finding in result.findings}
    assert result.status == "blocked"
    assert result.sandbox["status"] == "blocked"
    assert "script_sandbox_unsafe_capability" in codes
    assert "script_sandbox_unsafe_network" in codes
    assert "script_sandbox_unsafe_storage" in codes


def test_script_policy_blocks_inline_script_body_event_handler_and_script_tag():
    payload = _page_payload(
        {
            "inlineScript": "alert('x')",
            "onClick": "alert('x')",
            "html": "<script>alert('x')</script>",
        }
    )

    result = analyze_content_script_policy(payload)

    codes = {finding.code for finding in result.findings}
    assert result.status == "blocked"
    assert result.risk_level == "blocked"
    assert result.has_blocking_findings is True
    assert "inline_script" in codes
    assert "event_handler" in codes
    assert "inline_script_tag" in codes
    inline_finding = next(finding for finding in result.findings if finding.code == "inline_script")
    assert inline_finding.value_preview is None
    assert len(inline_finding.value_sha256) == 64


def test_script_policy_blocks_dangerous_protocols_and_path_traversal():
    payload = _page_payload(
        {
            "scriptSrc": "%2e%2e/private/tool.js",
            "scriptUrl": "javascript:alert(1)",
            "previewAsset": "blob:https://example.test/asset",
            "link": "data:text/html,<script>alert(1)</script>",
        }
    )

    result = analyze_content_script_policy(payload)

    codes = {finding.code for finding in result.findings}
    assert result.status == "blocked"
    assert "script_path_traversal" in codes
    assert "blocked_script_protocol" in codes
    assert "blocked_protocol" in codes


def _page_payload(props: dict | None = None) -> dict:
    return {
        "slug": "physics/script-policy",
        "galaxy": "englab",
        "subject": "physics",
        "title": "Script Policy",
        "layout": "experiment-page",
        "status": "draft",
        "version": "draft-local",
        "summary": "Policy smoke schema.",
        "sections": [
            {
                "type": "learning-task",
                "title": "Observe",
                "summary": "Check script policy.",
                "props": props or {},
            }
        ],
        "sources": [],
    }


def _sri_sha384(payload: bytes) -> str:
    return "sha384-" + base64.b64encode(hashlib.sha384(payload).digest()).decode("ascii")
