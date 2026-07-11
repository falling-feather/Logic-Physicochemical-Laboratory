from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Iterable

from app.core.config import Settings
from app.services.alert_delivery import alert_delivery_posture
from app.services.audit_anchor_delivery import audit_anchor_posture
from app.services.external_issue_providers import external_issue_sync_posture


RC_EXTERNAL_CHANNELS = (
    "alert_webhook",
    "github_issue_sync",
    "audit_anchor",
)

_CHANNEL_LABELS = {
    "alert_webhook": "alert delivery webhook",
    "github_issue_sync": "GitHub issue synchronization",
    "audit_anchor": "audit archive external anchor",
}

_DEFERRED_CAPABILITIES = (
    "Gitee issue synchronization",
    "Jira issue synchronization",
    "automatic inbound issue synchronization",
    "object-storage audit archive",
    "WORM audit retention",
    "RFC 3161 timestamping",
    "automatic destructive deletion",
    "mail delivery",
    "SMS delivery",
    "MFA enforcement",
)


def build_rc_external_scope_report(
    settings: Settings,
    *,
    selected_channels: Iterable[str] = (),
    staging_readback_confirmations: Iterable[str] = (),
    confirm_database_restore_evidence: bool = False,
    confirm_runtime_rollback_evidence: bool = False,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    selected = _validated_channel_set(selected_channels, field="selected_channels")
    readbacks = _validated_channel_set(
        staging_readback_confirmations,
        field="staging_readback_confirmations",
    )
    unexpected_readbacks = sorted(readbacks - selected)
    postures = {
        "alert_webhook": alert_delivery_posture(settings),
        "github_issue_sync": external_issue_sync_posture(settings),
        "audit_anchor": audit_anchor_posture(settings),
    }

    channels: dict[str, dict[str, Any]] = {}
    for channel in RC_EXTERNAL_CHANNELS:
        posture = postures[channel]
        is_selected = channel in selected
        enabled = bool(posture.get("enabled"))
        configured = bool(posture.get("configured"))
        readback_confirmed = channel in readbacks
        if not is_selected:
            ok = not enabled
            status = "passed" if ok else "blocked"
            reason = None if ok else "unselected_channel_enabled"
        elif not enabled:
            ok = False
            status = "blocked"
            reason = "selected_channel_disabled"
        elif not configured:
            ok = False
            status = "blocked"
            reason = "selected_channel_not_configured"
        elif not readback_confirmed:
            ok = False
            status = "missing_evidence"
            reason = "staging_readback_not_confirmed"
        else:
            ok = True
            status = "passed"
            reason = None
        channels[channel] = {
            "label": _CHANNEL_LABELS[channel],
            "selected_for_first_rc": is_selected,
            "enabled": enabled,
            "configured": configured,
            "provider": posture.get("provider"),
            "staging_readback_required": is_selected,
            "staging_readback_confirmed": readback_confirmed,
            "release_outbound_allowed": bool(is_selected and enabled and configured and readback_confirmed),
            "ok": ok,
            "status": status,
            "reason": reason,
        }

    long_term_evidence = {
        "database_backup_restore": _evidence_item(
            confirmed=confirm_database_restore_evidence,
            source_phase="V6.6.61",
        ),
        "runtime_service_and_binary_rollback": _evidence_item(
            confirmed=confirm_runtime_rollback_evidence,
            source_phase="V6.6.62",
        ),
    }
    blockers = [
        {"channel": channel, "reason": item["reason"]}
        for channel, item in channels.items()
        if item["status"] == "blocked"
    ]
    missing_evidence = [
        {"channel": channel, "reason": item["reason"]}
        for channel, item in channels.items()
        if item["status"] == "missing_evidence"
    ]
    missing_evidence.extend(
        {"evidence": name, "reason": item["reason"]}
        for name, item in long_term_evidence.items()
        if not item["ok"]
    )
    if unexpected_readbacks:
        blockers.append(
            {
                "scope": "staging_readback_confirmations",
                "reason": "readback_confirmed_for_unselected_channel",
                "channels": unexpected_readbacks,
            }
        )

    status = "ready"
    if blockers:
        status = "blocked"
    elif missing_evidence:
        status = "missing_evidence"
    generated = generated_at or datetime.now(UTC)
    unselected = [channel for channel in RC_EXTERNAL_CHANNELS if channel not in selected]
    return {
        "ok": status == "ready",
        "status": status,
        "phase": "V6.6.63",
        "generated_at": _datetime_value(generated),
        "mode": "read_only",
        "scope_frozen": True,
        "first_rc_external_channels": sorted(selected),
        "unselected_external_channels": unselected,
        "channels": channels,
        "long_term_evidence": long_term_evidence,
        "blockers": blockers,
        "missing_evidence": missing_evidence,
        "non_targets": [_CHANNEL_LABELS[channel] for channel in unselected] + list(_DEFERRED_CAPABILITIES),
        "network_requests_performed": 0,
        "side_effects_performed": [],
        "no_outbound_side_effects_expected": not any(
            item["release_outbound_allowed"] for item in channels.values()
        ),
        "sensitive_fields_returned": False,
        "sensitive_values_returned": False,
    }


def _validated_channel_set(values: Iterable[str], *, field: str) -> set[str]:
    normalized = {str(value).strip() for value in values if str(value).strip()}
    unknown = sorted(normalized - set(RC_EXTERNAL_CHANNELS))
    if unknown:
        raise ValueError(f"{field} contains unsupported channels: {', '.join(unknown)}")
    return normalized


def _evidence_item(*, confirmed: bool, source_phase: str) -> dict[str, Any]:
    return {
        "ok": confirmed,
        "status": "passed" if confirmed else "missing_evidence",
        "reason": None if confirmed else "historical_evidence_not_confirmed",
        "source_phase": source_phase,
        "confirmation_only": True,
    }


def _datetime_value(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat()
