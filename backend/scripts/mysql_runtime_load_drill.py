from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import json
import os
from statistics import mean
import sys
from time import perf_counter
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.core.config import get_settings
from app.db.session import get_session_factory, make_engine, reset_database_state
from app.main import create_app
from app.models import BackgroundTask
from app.models.base import utc_now
from app.services.background_tasks import claim_next_background_task, complete_background_task, enqueue_background_task


def run_mysql_runtime_load_drill(
    database_url: str,
    *,
    confirmed_database: str,
    api_requests: int,
    worker_tasks: int,
    concurrency: int,
) -> dict[str, object]:
    engine = make_engine(database_url)
    try:
        database_name = str(engine.url.database or "")
        if engine.dialect.name != "mysql":
            return _rejected_report("mysql_required")
        if database_name != confirmed_database:
            return _rejected_report("database_confirmation_mismatch")
        if not database_name.startswith("astra_") or not database_name.endswith("_drill"):
            return _rejected_report("isolated_drill_database_required")
        with engine.connect() as connection:
            server_version = str(connection.exec_driver_sql("SELECT VERSION()").scalar_one())[:80]
    finally:
        engine.dispose()
        reset_database_state()

    os.environ["ASTRA_DATABASE_URL"] = database_url
    os.environ["ASTRA_AUTO_CREATE_TABLES"] = "false"
    get_settings.cache_clear()
    reset_database_state()
    session_factory = get_session_factory(database_url)
    run_token = uuid4().hex
    task_type = f"mysql_load_{run_token[:12]}"
    now = utc_now().replace(microsecond=0)
    with session_factory() as db:
        for index in range(worker_tasks):
            enqueue_background_task(
                db,
                task_type=task_type,
                idempotency_key=f"mysql-load:{run_token}:{index}",
                source_type="mysql_runtime_load_drill",
                source_id=index,
                payload={"evidence": True},
                priority=index % 10,
                max_attempts=2,
                available_at=now - timedelta(seconds=1),
            )
        db.commit()

    api_durations: list[float] = []
    worker_durations: list[float] = []
    errors: list[str] = []
    api_workers = max(1, concurrency // 2)
    task_workers = max(1, concurrency - api_workers)
    api_counts = _split_work(api_requests, api_workers)
    task_counts = _split_work(worker_tasks, task_workers)

    with TestClient(create_app()) as client:
        def run_api_batch(count: int) -> None:
            for _ in range(count):
                started = perf_counter()
                response = client.get("/api/health")
                api_durations.append((perf_counter() - started) * 1000)
                if response.status_code != 200 or response.json().get("status") != "ok":
                    errors.append("api_health_failed")

        def run_worker_batch(count: int, worker_index: int) -> None:
            completed = 0
            empty_polls = 0
            while completed < count and empty_polls < 20:
                started = perf_counter()
                with session_factory() as db:
                    lease = claim_next_background_task(
                        db,
                        worker_id=f"mysql-load-worker-{worker_index}",
                        lease_seconds=60,
                        task_types={task_type},
                        now=utc_now(),
                    )
                    if lease is None:
                        empty_polls += 1
                        continue
                    if not complete_background_task(db, lease, now=utc_now()):
                        errors.append("worker_completion_rejected")
                        continue
                worker_durations.append((perf_counter() - started) * 1000)
                completed += 1
                empty_polls = 0
            if completed != count:
                errors.append("worker_batch_incomplete")

        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            futures = [executor.submit(run_api_batch, count) for count in api_counts]
            futures.extend(
                executor.submit(run_worker_batch, count, index)
                for index, count in enumerate(task_counts)
            )
            for future in futures:
                try:
                    future.result()
                except Exception as exc:  # keep the drill report redacted and machine-readable
                    errors.append(f"worker_exception_{exc.__class__.__name__}")

    with session_factory() as db:
        status_counts = dict(
            db.execute(
                select(BackgroundTask.status, func.count())
                .where(BackgroundTask.task_type == task_type)
                .group_by(BackgroundTask.status)
            ).all()
        )
    completed_tasks = int(status_counts.get("succeeded", 0))
    ok = (
        not errors
        and len(api_durations) == api_requests
        and len(worker_durations) == worker_tasks
        and completed_tasks == worker_tasks
    )
    return {
        "ok": ok,
        "status": "ready" if ok else "issues_found",
        "database": {
            "dialect": "mysql",
            "driver": "pymysql",
            "server_version": server_version,
            "database_name_sha256": _sha256_text(database_name),
            "database_name_returned": False,
            "database_url_returned": False,
        },
        "parameters": {
            "api_requests": api_requests,
            "worker_tasks": worker_tasks,
            "concurrency": concurrency,
            "api_workers": api_workers,
            "task_workers": task_workers,
        },
        "api_health": _latency_report(api_durations),
        "background_worker": {
            **_latency_report(worker_durations),
            "completed_tasks": completed_tasks,
            "duplicate_side_effects": max(0, len(worker_durations) - completed_tasks),
            "status_counts": {str(key): int(value) for key, value in status_counts.items()},
        },
        "error_counts": {code: errors.count(code) for code in sorted(set(errors))},
        "sensitive_values_returned": False,
    }


def _latency_report(durations: list[float]) -> dict[str, object]:
    sorted_values = sorted(durations)
    return {
        "count": len(sorted_values),
        "average_ms": round(mean(sorted_values), 2) if sorted_values else 0.0,
        "p50_ms": round(_percentile(sorted_values, 0.50), 2),
        "p95_ms": round(_percentile(sorted_values, 0.95), 2),
        "p99_ms": round(_percentile(sorted_values, 0.99), 2),
        "maximum_ms": round(max(sorted_values, default=0.0), 2),
    }


def _percentile(sorted_values: list[float], quantile: float) -> float:
    if not sorted_values:
        return 0.0
    index = round((len(sorted_values) - 1) * quantile)
    return sorted_values[max(0, min(len(sorted_values) - 1, index))]


def _split_work(total: int, workers: int) -> list[int]:
    base, remainder = divmod(total, workers)
    return [base + (1 if index < remainder else 0) for index in range(workers)]


def _sha256_text(value: str) -> str:
    from hashlib import sha256

    return sha256(value.encode("utf-8")).hexdigest()


def _rejected_report(reason: str) -> dict[str, object]:
    return {
        "ok": False,
        "status": "rejected",
        "reason": reason,
        "database_url_returned": False,
        "sensitive_values_returned": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run bounded concurrent API/worker load evidence on isolated MySQL.")
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--confirm-database", required=True)
    parser.add_argument("--api-requests", type=int, default=100, choices=range(1, 1001))
    parser.add_argument("--worker-tasks", type=int, default=100, choices=range(1, 1001))
    parser.add_argument("--concurrency", type=int, default=8, choices=range(2, 33))
    args = parser.parse_args(argv)
    report = run_mysql_runtime_load_drill(
        args.database_url,
        confirmed_database=args.confirm_database,
        api_requests=args.api_requests,
        worker_tasks=args.worker_tasks,
        concurrency=args.concurrency,
    )
    print(json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
