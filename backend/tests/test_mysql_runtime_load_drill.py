from scripts.mysql_runtime_load_drill import _latency_report, _split_work, run_mysql_runtime_load_drill


def test_load_drill_helpers_keep_exact_work_and_percentiles():
    assert _split_work(10, 3) == [4, 3, 3]
    assert _split_work(2, 4) == [1, 1, 0, 0]
    report = _latency_report([5.0, 1.0, 4.0, 2.0, 3.0])
    assert report == {
        "count": 5,
        "average_ms": 3.0,
        "p50_ms": 3.0,
        "p95_ms": 5.0,
        "p99_ms": 5.0,
        "maximum_ms": 5.0,
    }


def test_load_drill_rejects_non_mysql_without_returning_database_url():
    report = run_mysql_runtime_load_drill(
        "sqlite+pysqlite:///:memory:",
        confirmed_database="astra_release_drill",
        api_requests=1,
        worker_tasks=1,
        concurrency=2,
    )
    assert report == {
        "ok": False,
        "status": "rejected",
        "reason": "mysql_required",
        "database_url_returned": False,
        "sensitive_values_returned": False,
    }
