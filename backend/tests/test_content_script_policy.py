from app.services.content_script_policy import analyze_content_script_policy


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
    assert result.risk_level == "high"
    assert result.sandbox["status"] == "isolated"
    assert "script_reference" in codes
    assert "external_script_url" in codes
    assert external_finding.value_preview == "https://cdn.example.test/tool.js"


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
            "scriptSrc": "../private/tool.js",
            "scriptUrl": "javascript:alert(1)",
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
