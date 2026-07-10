from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from time import perf_counter
from typing import Any

from sqlalchemy import inspect
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.session import database_engine_posture


@dataclass(frozen=True)
class QueryProfile:
    name: str
    table: str
    required_index: str
    explain_sql: str
    pagination_max: int
    purpose: str


QUERY_PROFILES = (
    QueryProfile(
        name="audit_recent",
        table="audit_logs",
        required_index="ix_audit_logs_created_id",
        explain_sql="SELECT id FROM audit_logs ORDER BY created_at DESC, id DESC LIMIT 50",
        pagination_max=200,
        purpose="admin audit list and bounded export timeline",
    ),
    QueryProfile(
        name="audit_resource_timeline",
        table="audit_logs",
        required_index="ix_audit_logs_resource_created",
        explain_sql=(
            "SELECT id FROM audit_logs WHERE resource_type = 'bug_record' AND resource_id = '1' "
            "ORDER BY created_at DESC, id DESC LIMIT 50"
        ),
        pagination_max=200,
        purpose="resource-scoped audit trace",
    ),
    QueryProfile(
        name="knowledge_run_recent",
        table="knowledge_snapshot_runs",
        required_index="ix_knowledge_runs_started_id",
        explain_sql=(
            "SELECT id FROM knowledge_snapshot_runs ORDER BY started_at DESC, id DESC LIMIT 50"
        ),
        pagination_max=200,
        purpose="knowledge snapshot run list",
    ),
    QueryProfile(
        name="knowledge_run_status",
        table="knowledge_snapshot_runs",
        required_index="ix_knowledge_runs_status_started",
        explain_sql=(
            "SELECT id FROM knowledge_snapshot_runs WHERE status = 'running' "
            "ORDER BY started_at DESC, id DESC LIMIT 50"
        ),
        pagination_max=200,
        purpose="knowledge run health/status filter",
    ),
    QueryProfile(
        name="script_scan_recent",
        table="content_script_asset_scan_runs",
        required_index="ix_script_scan_type_started",
        explain_sql=(
            "SELECT id FROM content_script_asset_scan_runs WHERE scan_type = 'remote_drift' "
            "ORDER BY started_at DESC, id DESC LIMIT 50"
        ),
        pagination_max=200,
        purpose="content script scan run list",
    ),
    QueryProfile(
        name="script_scan_status",
        table="content_script_asset_scan_runs",
        required_index="ix_script_scan_status_started",
        explain_sql=(
            "SELECT id FROM content_script_asset_scan_runs WHERE status = 'running' "
            "ORDER BY started_at DESC, id DESC LIMIT 50"
        ),
        pagination_max=200,
        purpose="content script scan health/status filter",
    ),
    QueryProfile(
        name="pending_submissions",
        table="submissions",
        required_index="ix_submissions_status_submitted_id",
        explain_sql=(
            "SELECT id FROM submissions WHERE status IN ('submitted', 'returned') "
            "ORDER BY submitted_at ASC, id ASC LIMIT 50"
        ),
        pagination_max=200,
        purpose="global pending submission queue",
    ),
    QueryProfile(
        name="class_pending_submissions",
        table="submissions",
        required_index="ix_submissions_class_status_submitted",
        explain_sql=(
            "SELECT id FROM submissions WHERE class_id = 1 AND status IN ('submitted', 'returned') "
            "ORDER BY submitted_at ASC, id ASC LIMIT 50"
        ),
        pagination_max=200,
        purpose="teacher class-scoped pending queue",
    ),
    QueryProfile(
        name="background_task_claim",
        table="background_tasks",
        required_index="ix_background_tasks_claim",
        explain_sql=(
            "SELECT id FROM background_tasks WHERE status = 'pending' "
            "AND available_at <= CURRENT_TIMESTAMP "
            "ORDER BY priority DESC, available_at ASC, id ASC LIMIT 50"
        ),
        pagination_max=50,
        purpose="worker claim candidate scan",
    ),
    QueryProfile(
        name="bug_status_list",
        table="bug_records",
        required_index="ix_bug_records_status_id",
        explain_sql="SELECT id FROM bug_records WHERE status = 'open' ORDER BY id ASC LIMIT 50",
        pagination_max=200,
        purpose="admin bug status list",
    ),
    QueryProfile(
        name="bug_external_operation_list",
        table="bug_external_sync_operations",
        required_index="ix_bug_external_sync_bug_id_id",
        explain_sql=(
            "SELECT id FROM bug_external_sync_operations WHERE bug_record_id = 1 "
            "ORDER BY id DESC LIMIT 50"
        ),
        pagination_max=200,
        purpose="external issue operation ledger",
    ),
)


def performance_posture(settings: Settings) -> dict[str, Any]:
    total_pool_capacity = settings.database_pool_size + settings.database_max_overflow
    return {
        "budgets_ms": {
            "core_api": settings.performance_core_api_budget_ms,
            "admin_list": settings.performance_admin_api_budget_ms,
            "bounded_export": settings.performance_export_budget_ms,
        },
        "slow_request": {
            "enabled": settings.performance_slow_request_logging_enabled,
            "threshold_ms": settings.performance_slow_request_threshold_ms,
            "route_template_logged": True,
            "query_string_logged": False,
            "request_body_logged": False,
            "server_timing_header": True,
        },
        "database": database_engine_posture(settings),
        "worker_isolation": {
            "recommended_mode": "independent_service",
            "embedded_worker_enabled": settings.background_task_worker_enabled,
            "worker_batch_size": settings.background_task_worker_batch_size,
            "pool_capacity_per_process": total_pool_capacity,
            "automatic_write_retry": False,
            "claim_candidate_limit": 50,
        },
        "pagination": {
            "admin_lists_max": 200,
            "audit_export_max": 5000,
            "audit_chain_verify_max": 20000,
            "query_profiles": len(QUERY_PROFILES),
            "unbounded_list_allowed": False,
        },
        "probe_iterations": settings.performance_probe_iterations,
        "sensitive_values_returned": False,
    }


def build_backend_performance_report(
    db: Session,
    *,
    settings: Settings,
    include_explain: bool = True,
    include_benchmark: bool = True,
    require_mysql: bool = False,
) -> dict[str, Any]:
    engine = db.get_bind()
    dialect = engine.dialect.name
    inspector = inspect(engine)
    table_indexes: dict[str, set[str]] = {}
    for profile in QUERY_PROFILES:
        if profile.table not in table_indexes:
            table_indexes[profile.table] = {
                str(item.get("name"))
                for item in inspector.get_indexes(profile.table)
                if item.get("name")
            }

    profiles = []
    missing_indexes = []
    explain_errors = []
    benchmark_errors = []
    budget_exceeded = []
    for profile in QUERY_PROFILES:
        index_present = profile.required_index in table_indexes[profile.table]
        if not index_present:
            missing_indexes.append(profile.required_index)
        explain = _explain_profile(db, profile, dialect=dialect) if include_explain else {
            "executed": False,
            "status": "skipped",
            "access": [],
            "full_scan_detected": None,
        }
        if explain["status"] == "error":
            explain_errors.append(profile.name)
        benchmark = (
            _benchmark_profile(
                db,
                profile,
                iterations=settings.performance_probe_iterations,
                budget_ms=settings.performance_admin_api_budget_ms,
            )
            if include_benchmark
            else {
                "executed": False,
                "status": "skipped",
                "iterations": 0,
                "within_budget": None,
            }
        )
        if benchmark["status"] == "error":
            benchmark_errors.append(profile.name)
        elif benchmark.get("within_budget") is False:
            budget_exceeded.append(profile.name)
        profiles.append(
            {
                "name": profile.name,
                "table": profile.table,
                "purpose": profile.purpose,
                "required_index": profile.required_index,
                "index_present": index_present,
                "pagination_max": profile.pagination_max,
                "explain": explain,
                "benchmark": benchmark,
                "sql_text_returned": False,
            }
        )

    mysql_required_but_missing = require_mysql and dialect != "mysql"
    ok = (
        not missing_indexes
        and not explain_errors
        and not benchmark_errors
        and not budget_exceeded
        and not mysql_required_but_missing
    )
    if mysql_required_but_missing:
        status = "mysql_required"
    elif missing_indexes:
        status = "missing_indexes"
    elif explain_errors:
        status = "explain_failed"
    elif benchmark_errors:
        status = "benchmark_failed"
    elif budget_exceeded:
        status = "performance_budget_exceeded"
    elif dialect == "mysql":
        status = "mysql_query_plan_ready"
    else:
        status = "local_contract_ready_mysql_evidence_pending"
    return {
        "ok": ok,
        "status": status,
        "dialect": dialect,
        "require_mysql": require_mysql,
        "posture": performance_posture(settings),
        "summary": {
            "profile_count": len(profiles),
            "index_present_count": sum(1 for item in profiles if item["index_present"]),
            "explain_analyze_count": sum(
                1 for item in profiles if item["explain"].get("analyze", {}).get("status") == "ok"
            ),
            "missing_index_count": len(missing_indexes),
            "explain_error_count": len(explain_errors),
            "benchmark_error_count": len(benchmark_errors),
            "budget_exceeded_count": len(budget_exceeded),
        },
        "profiles": profiles,
        "missing_indexes": sorted(missing_indexes),
        "budget_exceeded_profiles": sorted(budget_exceeded),
        "deferred_risks": [
            {
                "code": "mysql_runtime_evidence_captured" if dialect == "mysql" else "mysql_runtime_evidence_pending",
                "detail": (
                    "MySQL EXPLAIN ANALYZE and bounded benchmarks were executed; production cardinality and load must "
                    "still be compared with the captured release dataset."
                    if dialect == "mysql"
                    else "SQLite plans do not prove MySQL cardinality, lock, buffer-pool, or filesort behavior."
                ),
            },
            {
                "code": "leading_wildcard_search",
                "detail": "Bug/content keyword contains-search remains bounded but may require a dedicated search index later.",
            },
            {
                "code": "deep_offset_pagination",
                "detail": "Offset pagination is capped; large production offsets should migrate to keyset cursors after measurement.",
            },
            {
                "code": "dynamic_audit_aggregation",
                "detail": "Arbitrary audit filter combinations and reports require real MySQL EXPLAIN ANALYZE evidence.",
            },
        ],
        "sql_text_returned": False,
        "database_url_returned": False,
        "parameters_returned": False,
    }


def _explain_profile(db: Session, profile: QueryProfile, *, dialect: str) -> dict[str, Any]:
    if dialect not in {"sqlite", "mysql"}:
        return {
            "executed": False,
            "status": "unsupported_dialect",
            "access": [],
            "full_scan_detected": None,
        }
    try:
        rows = db.connection().exec_driver_sql(f"EXPLAIN {'QUERY PLAN ' if dialect == 'sqlite' else ''}{profile.explain_sql}")
        if dialect == "sqlite":
            access = [str(row[3])[:240] for row in rows.fetchall()]
            full_scan = any(
                f"SCAN {profile.table}".upper() in detail.upper() and "USING" not in detail.upper()
                for detail in access
            )
            analyze = {
                "executed": False,
                "status": "not_applicable",
                "plan_sha256": None,
                "plan_line_count": 0,
            }
        else:
            mappings = rows.mappings().all()
            access = [
                {
                    "table": str(row.get("table") or "")[:80],
                    "access_type": str(row.get("type") or "")[:32],
                    "key": str(row.get("key") or "")[:80],
                    "rows": int(row.get("rows") or 0),
                    "extra": str(row.get("Extra") or "")[:160],
                }
                for row in mappings
            ]
            full_scan = any(item["access_type"].upper() == "ALL" for item in access)
            analyze = _mysql_explain_analyze(db, profile)
            if analyze["status"] != "ok":
                return {
                    "executed": True,
                    "status": "error",
                    "error": analyze.get("error", "ExplainAnalyzeError"),
                    "access": access,
                    "full_scan_detected": full_scan,
                    "analyze": analyze,
                }
        return {
            "executed": True,
            "status": "ok",
            "access": access,
            "full_scan_detected": full_scan,
            "analyze": analyze,
        }
    except Exception as exc:
        return {
            "executed": True,
            "status": "error",
            "error": exc.__class__.__name__,
            "access": [],
            "full_scan_detected": None,
            "analyze": {
                "executed": dialect == "mysql",
                "status": "error" if dialect == "mysql" else "not_applicable",
                "error": exc.__class__.__name__ if dialect == "mysql" else None,
                "plan_sha256": None,
                "plan_line_count": 0,
            },
        }


def _mysql_explain_analyze(db: Session, profile: QueryProfile) -> dict[str, Any]:
    try:
        rows = db.connection().exec_driver_sql(f"EXPLAIN ANALYZE {profile.explain_sql}").fetchall()
        plan_lines = [str(row[0]) for row in rows]
        plan_text = "\n".join(plan_lines)
        return {
            "executed": True,
            "status": "ok",
            "plan_sha256": sha256(plan_text.encode("utf-8")).hexdigest(),
            "plan_line_count": len(plan_lines),
            "plan_text_returned": False,
        }
    except Exception as exc:
        return {
            "executed": True,
            "status": "error",
            "error": exc.__class__.__name__,
            "plan_sha256": None,
            "plan_line_count": 0,
            "plan_text_returned": False,
        }


def _benchmark_profile(
    db: Session,
    profile: QueryProfile,
    *,
    iterations: int,
    budget_ms: int,
) -> dict[str, Any]:
    durations = []
    row_counts = []
    try:
        connection = db.connection()
        for _ in range(iterations):
            started_at = perf_counter()
            rows = connection.exec_driver_sql(profile.explain_sql).fetchall()
            durations.append((perf_counter() - started_at) * 1000)
            row_counts.append(len(rows))
    except Exception as exc:
        return {
            "executed": True,
            "status": "error",
            "error": exc.__class__.__name__,
            "iterations": len(durations),
            "within_budget": False,
            "sql_text_returned": False,
        }
    sorted_durations = sorted(durations)
    maximum_ms = max(durations, default=0.0)
    return {
        "executed": True,
        "status": "ok",
        "iterations": iterations,
        "budget_ms": budget_ms,
        "average_ms": round(sum(durations) / max(1, len(durations)), 2),
        "p50_ms": round(_percentile(sorted_durations, 0.50), 2),
        "p95_ms": round(_percentile(sorted_durations, 0.95), 2),
        "p99_ms": round(_percentile(sorted_durations, 0.99), 2),
        "maximum_ms": round(maximum_ms, 2),
        "maximum_rows": max(row_counts, default=0),
        "within_budget": maximum_ms <= budget_ms,
        "result_values_returned": False,
        "sql_text_returned": False,
    }


def _percentile(sorted_values: list[float], quantile: float) -> float:
    if not sorted_values:
        return 0.0
    index = round((len(sorted_values) - 1) * quantile)
    return sorted_values[max(0, min(len(sorted_values) - 1, index))]
