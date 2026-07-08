import json

from scripts.deploy_topology_drill import run_topology_drill


def test_deploy_topology_drill_reports_ready_topology_without_real_network():
    report = run_topology_drill(
        static_url="https://astra.example/",
        proxied_api_url="https://astra.example/api/health",
        direct_api_url="http://127.0.0.1:8000/api/health",
        origin="https://astra.example",
        request_id="drill-1",
        fetcher=_FakeFetcher(
            {
                "https://astra.example/": _response(
                    200,
                    {"content-type": "text/html; charset=utf-8"},
                    "<!doctype html><html><body>Astra</body></html>",
                ),
                "https://astra.example/api/health": _response(
                    200,
                    {
                        "content-type": "application/json",
                        "cache-control": "no-store",
                        "x-request-id": "drill-1",
                        "access-control-allow-origin": "https://astra.example",
                    },
                    {"status": "ok", "service": "astra-backend", "database": {"ok": True}},
                ),
                "http://127.0.0.1:8000/api/health": _response(
                    200,
                    {
                        "content-type": "application/json",
                        "cache-control": "no-store",
                        "x-request-id": "drill-1",
                    },
                    {"status": "ok", "service": "astra-backend", "database": {"ok": True}},
                ),
            }
        ),
    )

    assert report["ok"] is True
    assert report["topology"]["proxied_api_path_ok"] is True
    assert report["static_site"]["html_detected"] is True
    assert report["proxied_api"]["cache_no_store_ok"] is True
    assert report["proxied_api"]["request_id_ok"] is True
    assert report["proxied_api"]["cors_ok"] is True
    assert report["direct_api"]["direct_api_host_private_or_loopback"] is True
    assert report["public_exposure"]["status"] == "skipped_no_public_direct_api_url"
    assert report["service_plan"]["static_service_name"] == "EngLab"
    assert report["service_plan"]["api_service_name"] == "AstraApi"
    assert report["service_plan"]["logs_configured"] is True


def test_deploy_topology_drill_flags_missing_api_no_store_and_request_id():
    report = run_topology_drill(
        static_url="https://astra.example/",
        proxied_api_url="https://astra.example/api/health",
        direct_api_url="http://127.0.0.1:8000/api/health",
        origin="https://astra.example",
        request_id="drill-1",
        fetcher=_FakeFetcher(
            {
                "https://astra.example/": _response(200, {"content-type": "text/html"}, "<html></html>"),
                "https://astra.example/api/health": _response(
                    200,
                    {
                        "content-type": "application/json",
                        "cache-control": "max-age=600",
                        "x-request-id": "different",
                        "access-control-allow-origin": "https://other.example",
                    },
                    {"status": "ok", "service": "astra-backend"},
                ),
                "http://127.0.0.1:8000/api/health": _response(
                    200,
                    {
                        "content-type": "application/json",
                        "cache-control": "no-store",
                        "x-request-id": "drill-1",
                    },
                    {"status": "ok", "service": "astra-backend"},
                ),
            }
        ),
    )

    assert report["ok"] is False
    assert report["proxied_api"]["ok"] is False
    assert report["proxied_api"]["cache_no_store_ok"] is False
    assert report["proxied_api"]["request_id_ok"] is False
    assert report["proxied_api"]["cors_ok"] is False


def test_deploy_topology_drill_rejects_legacy_cpp_health_response():
    report = run_topology_drill(
        static_url="https://astra.example/",
        proxied_api_url="https://astra.example/api/health",
        direct_api_url="http://127.0.0.1:8000/api/health",
        request_id="drill-1",
        fetcher=_FakeFetcher(
            {
                "https://astra.example/": _response(200, {"content-type": "text/html"}, "<html></html>"),
                "https://astra.example/api/health": _response(
                    200,
                    {
                        "content-type": "application/json",
                        "cache-control": "no-store",
                        "x-request-id": "drill-1",
                    },
                    {"status": "ok", "server": "englab-cpp"},
                ),
                "http://127.0.0.1:8000/api/health": _response(
                    200,
                    {
                        "content-type": "application/json",
                        "cache-control": "no-store",
                        "x-request-id": "drill-1",
                    },
                    {"status": "ok", "service": "astra-backend"},
                ),
            }
        ),
    )

    assert report["ok"] is False
    assert report["proxied_api"]["ok"] is False
    assert report["proxied_api"]["service"] is None
    assert report["proxied_api"]["service_ok"] is False


def test_deploy_topology_drill_detects_direct_api_public_exposure():
    report = run_topology_drill(
        static_url="https://astra.example/",
        proxied_api_url="https://astra.example/api/health",
        direct_api_url="http://127.0.0.1:8000/api/health",
        public_direct_api_url="http://8.8.8.8:8000/api/health",
        request_id="drill-1",
        fetcher=_FakeFetcher(
            {
                "https://astra.example/": _response(200, {"content-type": "text/html"}, "<html></html>"),
                "https://astra.example/api/health": _response(
                    200,
                    {
                        "content-type": "application/json",
                        "cache-control": "no-store",
                        "x-request-id": "drill-1",
                    },
                    {"status": "ok", "service": "astra-backend"},
                ),
                "http://127.0.0.1:8000/api/health": _response(
                    200,
                    {
                        "content-type": "application/json",
                        "cache-control": "no-store",
                        "x-request-id": "drill-1",
                    },
                    {"status": "ok", "service": "astra-backend"},
                ),
                "http://8.8.8.8:8000/api/health": _response(
                    200,
                    {
                        "content-type": "application/json",
                        "cache-control": "no-store",
                        "x-request-id": "drill-1",
                    },
                    {"status": "ok", "service": "astra-backend"},
                ),
            }
        ),
    )

    assert report["ok"] is False
    assert report["public_exposure"]["ok"] is False
    assert report["public_exposure"]["status"] == "reachable_public_direct_api_port"


def test_deploy_topology_drill_rejects_public_api_bind_host():
    report = run_topology_drill(
        static_url="https://astra.example/",
        proxied_api_url="https://astra.example/api/health",
        direct_api_url="http://127.0.0.1:8000/api/health",
        api_bind_host="0.0.0.0",
        request_id="drill-1",
        fetcher=_ready_fetcher(),
    )

    assert report["ok"] is False
    assert report["topology"]["api_bind_host_private_or_loopback"] is False
    assert report["direct_api"]["api_bind_host_private_or_loopback"] is False
    assert report["service_plan"]["api_bind_host_private_or_loopback"] is False


def test_deploy_topology_drill_handles_http_failures_as_report_items():
    report = run_topology_drill(
        static_url="https://astra.example/",
        proxied_api_url="https://astra.example/api/health",
        direct_api_url="http://127.0.0.1:8000/api/health",
        public_direct_api_url="http://8.8.8.8:8000/api/health",
        request_id="drill-1",
        fetcher=_FakeFetcher(
            {
                "https://astra.example/": _failure("TimeoutError"),
                "https://astra.example/api/health": _failure("ConnectionError"),
                "http://127.0.0.1:8000/api/health": _failure("ConnectionError"),
                "http://8.8.8.8:8000/api/health": _failure("TimeoutError"),
            }
        ),
    )

    assert report["ok"] is False
    assert report["static_site"]["status"] == "unavailable"
    assert report["proxied_api"]["status"] == "unavailable"
    assert report["direct_api"]["status"] == "unavailable"
    assert report["public_exposure"]["ok"] is True
    assert report["public_exposure"]["status"] == "not_reachable"


def _ready_fetcher() -> "_FakeFetcher":
    return _FakeFetcher(
        {
            "https://astra.example/": _response(200, {"content-type": "text/html"}, "<html></html>"),
            "https://astra.example/api/health": _response(
                200,
                {
                    "content-type": "application/json",
                    "cache-control": "no-store",
                    "x-request-id": "drill-1",
                },
                {"status": "ok", "service": "astra-backend"},
            ),
            "http://127.0.0.1:8000/api/health": _response(
                200,
                {
                    "content-type": "application/json",
                    "cache-control": "no-store",
                    "x-request-id": "drill-1",
                },
                {"status": "ok", "service": "astra-backend"},
            ),
        }
    )


class _FakeFetcher:
    def __init__(self, responses: dict[str, dict]) -> None:
        self.responses = responses

    def __call__(self, url: str, headers: dict[str, str], timeout_seconds: float) -> dict:
        assert timeout_seconds > 0
        return self.responses.get(url, _failure("NotFound"))


def _response(status_code: int, headers: dict[str, str], body: dict | str) -> dict:
    return {
        "ok": True,
        "status_code": status_code,
        "headers": {key.lower(): value for key, value in headers.items()},
        "body": json.dumps(body) if isinstance(body, dict) else body,
    }


def _failure(error: str) -> dict:
    return {
        "ok": False,
        "status_code": None,
        "headers": {},
        "body": "",
        "error": error,
    }
