from typing import Any

from app.models import AdminAlertOutboxEntry
from app.schemas.admin import AdminAlertOutboxEntryRead, AdminAlertOutboxWriteResponse


def admin_alert_outbox_entry_read(entry: AdminAlertOutboxEntry) -> AdminAlertOutboxEntryRead:
    return AdminAlertOutboxEntryRead(
        id=entry.id,
        source_type=entry.source_type,
        source_id=entry.source_id,
        source_key=entry.source_key,
        event_code=entry.event_code,
        severity=entry.severity,
        action_hint=entry.action_hint,
        status=entry.status,
        dispatch_mode=entry.dispatch_mode,
        delivery_target=entry.delivery_target,
        external_delivery=entry.external_delivery,
        payload_hash_prefix=entry.payload_hash[:12],
        payload_redacted=True,
        first_seen_at=entry.first_seen_at,
        last_seen_at=entry.last_seen_at,
        available_at=entry.available_at,
        expires_at=entry.expires_at,
        seen_count=entry.seen_count,
        attempt_count=entry.attempt_count,
        last_error_code=entry.last_error_code,
        created_by_user_id=entry.created_by_user_id,
        reviewed_by_user_id=entry.reviewed_by_user_id,
        reviewed_at=entry.reviewed_at,
        review_note_present=bool(entry.review_note),
        created_at=entry.created_at,
        updated_at=entry.updated_at,
    )


def admin_alert_outbox_write_response(write_result: Any) -> AdminAlertOutboxWriteResponse:
    return AdminAlertOutboxWriteResponse(
        generated_at=write_result.generated_at,
        source_type=write_result.source_type,
        status=write_result.status,
        dispatch_mode=write_result.dispatch_mode,
        delivery_target=write_result.delivery_target,
        external_delivery=write_result.external_delivery,
        candidate_count=write_result.candidate_count,
        created_count=write_result.created_count,
        refreshed_count=write_result.refreshed_count,
        skipped_count=write_result.skipped_count,
        items=[admin_alert_outbox_entry_read(entry) for entry in write_result.entries],
    )
