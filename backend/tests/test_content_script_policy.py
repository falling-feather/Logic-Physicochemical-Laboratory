import base64
import hashlib

from app.services import content_script_policy
from app.services.content_script_policy import (
    analyze_content_script_policy,
    public_content_page_schema,
    script_policy_result_from_json,
)
from app.services.content_script_sandbox_templates import (
    ENERGY_CONSERVATION_TEMPLATE_ID,
    SCRIPT_SANDBOX_DOCUMENT_CONTRACT_VERSION,
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


def test_registered_sandbox_document_is_public_and_participates_in_manifest_identity():
    def page(default_friction):
        return _page_payload(
            {
                "scriptPath": "pages/physics/energy-conservation.js",
                "scriptSandbox": {
                    "mode": "isolated-iframe",
                    "network": "same-origin",
                    "storage": "none",
                    "document": _sandbox_document(default_friction),
                },
            }
        )

    result = analyze_content_script_policy(page(0.1))
    first = public_content_page_schema(page(0.1)).model_dump(mode="json")["sections"][0]["props"]["scriptManifest"]
    second = public_content_page_schema(page(0.2)).model_dump(mode="json")["sections"][0]["props"]["scriptManifest"]

    assert result.status == "review_required"
    assert result.has_blocking_findings is False
    assert first["sandbox"]["document"] == _sandbox_document(0.1)
    assert "initializer" not in first["sandbox"]["document"]
    assert "html" not in first["sandbox"]["document"]
    assert first["sandboxId"] != second["sandboxId"]


def test_script_policy_blocks_unregistered_or_raw_sandbox_document_contracts():
    documents = [
        {
            "contractVersion": SCRIPT_SANDBOX_DOCUMENT_CONTRACT_VERSION,
            "templateId": "physics-unregistered-template-v1",
            "config": {},
        },
        {
            **_sandbox_document(0.1),
            "html": "<main>unreviewed</main>",
        },
        {
            **_sandbox_document(0.1),
            "initializer": "runArbitraryGlobal",
        },
    ]

    results = [
        analyze_content_script_policy(
            _page_payload(
                {
                    "scriptPath": "pages/physics/energy-conservation.js",
                    "scriptSandbox": {
                        "mode": "isolated-iframe",
                        "network": "same-origin",
                        "storage": "none",
                        "document": document,
                    },
                }
            )
        )
        for document in documents
    ]

    assert all(result.status == "blocked" for result in results)
    assert "content_script_sandbox_template_unsupported" in {finding.code for finding in results[0].findings}
    for result in results[1:]:
        assert "content_script_sandbox_document_invalid" in {finding.code for finding in result.findings}


def test_script_policy_blocks_raw_execution_fields_beside_registered_document():
    results = []
    for field, value in [
        ("html", "<main>unreviewed</main>"),
        ("entry", "runArbitraryGlobal"),
        ("initializer", "runArbitraryGlobal"),
    ]:
        payload = _page_payload(
            {
                "scriptPath": "pages/physics/energy-conservation.js",
                "scriptSandbox": {
                    "mode": "isolated-iframe",
                    "network": "same-origin",
                    "storage": "none",
                    "document": _sandbox_document(0.1),
                    field: value,
                },
            }
        )
        result = analyze_content_script_policy(payload)
        manifest = public_content_page_schema(payload).model_dump(mode="json")["sections"][0]["props"]["scriptManifest"]
        results.append((field, result, manifest))

    for field, result, manifest in results:
        finding = next(item for item in result.findings if item.code == "script_sandbox_unsupported_field")
        assert result.status == "blocked"
        assert result.has_blocking_findings is True
        assert finding.path == f"$.sections[0].props.scriptSandbox.{field}"
        assert finding.value_preview is None
        assert manifest["sandbox"] == {
            "status": "blocked",
            "code": "script_sandbox_unsupported_field",
        }


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


def test_default_external_script_fetcher_uses_public_https_boundary(monkeypatch):
    captured = {}

    def fake_fetch(url: str, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        return b"console.log('ok');"

    monkeypatch.setattr(content_script_policy, "fetch_public_https_bytes", fake_fetch)

    payload = content_script_policy._default_external_script_fetcher("https://cdn.example.test/tool.js")

    assert payload == b"console.log('ok');"
    assert captured["url"] == "https://cdn.example.test/tool.js"
    assert captured["timeout_seconds"] == content_script_policy.EXTERNAL_SCRIPT_FETCH_TIMEOUT_SECONDS
    assert captured["max_bytes"] == content_script_policy.MAX_EXTERNAL_SCRIPT_BYTES


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
    assert props["scriptManifest"]["sandboxId"].startswith("sm_")
    assert len(props["scriptManifest"]["sandboxId"]) == 27
    assert props["scriptManifest"]["references"][0]["key"] == "scriptUrl"
    assert len(props["scriptManifest"]["references"][0]["valueSha256"]) == 64
    sandbox = props["scriptManifest"]["sandbox"]
    assert sandbox["csp"] == (
        "default-src 'none'; script-src 'self'; connect-src 'none'; img-src 'self' data:; "
        "style-src 'self' 'unsafe-inline'"
    )
    assert sandbox["enforcement"] == {
        "browserContext": "sandboxed-iframe",
        "requiredIframeSandbox": "allow-scripts",
        "requiredContentSecurityPolicy": sandbox["csp"],
        "sandboxOrigin": "opaque",
    }
    assert sandbox["capabilities"] == {
        "scripts": True,
        "sameOrigin": False,
        "topNavigation": False,
        "popups": False,
        "downloads": False,
        "network": "none",
        "storage": "none",
    }


def test_public_schema_derives_same_origin_script_sandbox_csp():
    payload = _page_payload(
        {
            "scriptPath": "pages/physics/energy-conservation.js",
            "scriptSandbox": {"mode": "isolated-iframe", "network": "same-origin", "storage": "none"},
        }
    )

    public_schema = public_content_page_schema(payload).model_dump(mode="json")

    sandbox = public_schema["sections"][0]["props"]["scriptManifest"]["sandbox"]
    assert sandbox["network"] == "same-origin"
    assert sandbox["csp"] == (
        "default-src 'none'; script-src 'self'; connect-src 'self'; img-src 'self' data:; "
        "style-src 'self' 'unsafe-inline'"
    )
    assert sandbox["enforcement"]["requiredContentSecurityPolicy"] == sandbox["csp"]
    assert sandbox["capabilities"]["network"] == "same-origin"
    assert sandbox["capabilities"]["sameOrigin"] is False


def test_public_schema_blocks_unsafe_public_sandbox_manifest():
    payload = _page_payload(
        {
            "scriptPath": "drafts/custom-energy.js",
            "scriptSandbox": {
                "mode": "isolated-iframe",
                "network": "external",
                "storage": "local",
                "allowSameOrigin": True,
            },
        }
    )

    public_schema = public_content_page_schema(payload).model_dump(mode="json")

    sandbox = public_schema["sections"][0]["props"]["scriptManifest"]["sandbox"]
    assert sandbox == {"status": "blocked"}


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


def _sandbox_document(default_friction: float) -> dict:
    return {
        "contractVersion": SCRIPT_SANDBOX_DOCUMENT_CONTRACT_VERSION,
        "templateId": ENERGY_CONSERVATION_TEMPLATE_ID,
        "config": {"defaultFriction": default_friction},
    }


def _sri_sha384(payload: bytes) -> str:
    return "sha384-" + base64.b64encode(hashlib.sha384(payload).digest()).decode("ascii")
