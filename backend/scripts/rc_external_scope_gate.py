from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
import sys

from app.core.config import get_settings
from app.services.rc_external_scope import RC_EXTERNAL_CHANNELS, build_rc_external_scope_report


def run_rc_external_scope_gate(
    *,
    selected_channels: tuple[str, ...] = (),
    staging_readback_confirmations: tuple[str, ...] = (),
    confirm_database_restore_evidence: bool = False,
    confirm_runtime_rollback_evidence: bool = False,
    generated_at: datetime | None = None,
) -> dict[str, object]:
    return build_rc_external_scope_report(
        get_settings(),
        selected_channels=selected_channels,
        staging_readback_confirmations=staging_readback_confirmations,
        confirm_database_restore_evidence=confirm_database_restore_evidence,
        confirm_runtime_rollback_evidence=confirm_runtime_rollback_evidence,
        generated_at=generated_at,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the read-only V6.6.63 first-RC external-scope gate.")
    parser.add_argument(
        "--select-channel",
        action="append",
        choices=RC_EXTERNAL_CHANNELS,
        default=[],
        help="Select a default-disabled outbound channel for the first RC. Repeat when needed.",
    )
    parser.add_argument(
        "--confirm-staging-readback",
        action="append",
        choices=RC_EXTERNAL_CHANNELS,
        default=[],
        help="Confirm real staging readback/fault evidence for a selected channel.",
    )
    parser.add_argument("--confirm-database-restore-evidence", action="store_true")
    parser.add_argument("--confirm-runtime-rollback-evidence", action="store_true")
    parser.add_argument("--now", default=None, help="Override generated_at for deterministic reports.")
    args = parser.parse_args(argv)
    try:
        generated_at = _parse_datetime(args.now) if args.now else None
        report = run_rc_external_scope_gate(
            selected_channels=tuple(args.select_channel),
            staging_readback_confirmations=tuple(args.confirm_staging_readback),
            confirm_database_restore_evidence=args.confirm_database_restore_evidence,
            confirm_runtime_rollback_evidence=args.confirm_runtime_rollback_evidence,
            generated_at=generated_at,
        )
    except (ValueError, TypeError) as exc:
        report = {
            "ok": False,
            "status": "invalid_argument",
            "error": exc.__class__.__name__,
            "detail": str(exc),
            "sensitive_fields_returned": False,
            "sensitive_values_returned": False,
        }
    print(json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True))
    return 0 if report.get("ok") else 1


def _parse_datetime(value: str) -> datetime:
    text = value.strip()
    if len(text) == 10:
        return datetime.fromisoformat(text).replace(tzinfo=UTC)
    parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
