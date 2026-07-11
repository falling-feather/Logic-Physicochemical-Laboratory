import json

from app.services.audit import redact_audit_snapshot


def test_redact_audit_snapshot_removes_sensitive_fields_recursively():
    snapshot = {
        "format": "unit_test",
        "current_hash": "hash-is-not-secret-here",
        "after": {"name": "Visible School"},
        "message": "Authorization: Bearer scalar-secret",
        "payload_json": {"secret": "payload-secret"},
        "nested": {
            "source_url": "https://cdn.example.test/secret.js",
            "metadata_json": {"token": "metadata-secret"},
        },
        "items": [
            {"review_note": "manual-review-secret", "status": "planned"},
            {"scheduler_lease_token": "lease-secret", "attempt_count": 2},
        ],
    }

    redacted = redact_audit_snapshot(snapshot)
    redacted_text = json.dumps(redacted, ensure_ascii=False)

    assert redacted["format"] == "unit_test"
    assert redacted["current_hash"] == "hash-is-not-secret-here"
    assert redacted["after"] == {"name": "Visible School"}
    assert redacted["message"]["redacted"] is True
    assert redacted["payload_json"]["redacted"] is True
    assert redacted["nested"]["source_url"]["redacted"] is True
    assert redacted["nested"]["metadata_json"]["redacted"] is True
    assert redacted["items"][0]["review_note"]["redacted"] is True
    assert redacted["items"][0]["status"] == "planned"
    assert redacted["items"][1]["scheduler_lease_token"]["redacted"] is True
    assert redacted["items"][1]["attempt_count"] == 2
    assert "payload-secret" not in redacted_text
    assert "metadata-secret" not in redacted_text
    assert "manual-review-secret" not in redacted_text
    assert "lease-secret" not in redacted_text
    assert "scalar-secret" not in redacted_text
