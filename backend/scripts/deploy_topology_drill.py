from __future__ import annotations

import argparse
import json
from ipaddress import ip_address
from pathlib import PureWindowsPath
import re
import subprocess
import sys
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


FetchResult = dict[str, Any]
Fetcher = Callable[[str, dict[str, str], float], FetchResult]
ServiceQuery = Callable[[tuple[str, ...]], dict[str, Any]]


DEFAULT_REQUEST_ID = "astra-topology-drill"


def run_topology_drill(
    *,
    static_url: str = "http://127.0.0.1:910/",
    proxied_api_url: str = "http://127.0.0.1/api/health",
    direct_api_url: str = "http://127.0.0.1:8000/api/health",
    public_direct_api_url: str | None = None,
    origin: str | None = None,
    request_id: str = DEFAULT_REQUEST_ID,
    api_bind_host: str = "127.0.0.1",
    api_bind_port: int = 8000,
    static_service_name: str = "EngLab",
    api_service_name: str = "AstraApi",
    worker_service_name: str = "AstraWorker",
    proxy_service_name: str = "AstraProxy",
    static_log_path: str = r"C:\englab\logs\stdout.log",
    api_stdout_log_path: str = r"C:\englab\logs\astra-api-stdout.log",
    api_stderr_log_path: str = r"C:\englab\logs\astra-api-stderr.log",
    worker_log_path: str = r"C:\englab\logs\astra-worker.log",
    proxy_log_path: str = r"C:\englab\logs\astra-proxy.log",
    verify_windows_services: bool = False,
    timeout_seconds: float = 5.0,
    fetcher: Fetcher | None = None,
    service_query: ServiceQuery | None = None,
) -> dict[str, Any]:
    fetch = fetcher or _fetch_url
    topology = _topology_report(
        static_url=static_url,
        proxied_api_url=proxied_api_url,
        direct_api_url=direct_api_url,
        public_direct_api_url=public_direct_api_url,
        api_bind_host=api_bind_host,
        api_bind_port=api_bind_port,
    )
    static_site = _static_site_report(static_url, fetch=fetch, timeout_seconds=timeout_seconds)
    proxied_api = _api_health_report(
        proxied_api_url,
        fetch=fetch,
        timeout_seconds=timeout_seconds,
        request_id=request_id,
        origin=origin,
        require_no_store=True,
        require_request_id=True,
        require_cors=bool(origin),
    )
    direct_api = _direct_api_report(
        direct_api_url,
        fetch=fetch,
        timeout_seconds=timeout_seconds,
        request_id=request_id,
        api_bind_host=api_bind_host,
    )
    public_exposure = _public_exposure_report(
        public_direct_api_url,
        fetch=fetch,
        timeout_seconds=timeout_seconds,
        request_id=request_id,
    )
    service_plan = _service_plan_report(
        static_service_name=static_service_name,
        api_service_name=api_service_name,
        worker_service_name=worker_service_name,
        proxy_service_name=proxy_service_name,
        static_log_path=static_log_path,
        api_stdout_log_path=api_stdout_log_path,
        api_stderr_log_path=api_stderr_log_path,
        worker_log_path=worker_log_path,
        proxy_log_path=proxy_log_path,
        api_bind_host=api_bind_host,
        api_bind_port=api_bind_port,
    )
    windows_services = _windows_services_report(
        service_names=(static_service_name, api_service_name, worker_service_name, proxy_service_name),
        verify=verify_windows_services,
        query=service_query or _query_windows_services,
    )
    sections = {
        "topology": topology,
        "static_site": static_site,
        "proxied_api": proxied_api,
        "direct_api": direct_api,
        "public_exposure": public_exposure,
        "service_plan": service_plan,
        "windows_services": windows_services,
    }
    return {
        "ok": all(bool(section["ok"]) for section in sections.values()),
        **sections,
    }


def _topology_report(
    *,
    static_url: str,
    proxied_api_url: str,
    direct_api_url: str,
    public_direct_api_url: str | None,
    api_bind_host: str,
    api_bind_port: int,
) -> dict[str, Any]:
    parsed_static = urlparse(static_url)
    parsed_proxy_api = urlparse(proxied_api_url)
    parsed_direct_api = urlparse(direct_api_url)
    api_path_ok = parsed_proxy_api.path.startswith("/api/")
    static_path_ok = not parsed_static.path.startswith("/api/")
    direct_host_private = _host_is_private_or_loopback(parsed_direct_api.hostname or "")
    bind_host_private = _host_is_private_or_loopback(api_bind_host)
    bind_host_ok = bind_host_private and api_bind_host not in {"0.0.0.0", "::"}
    return {
        "ok": api_path_ok and static_path_ok and direct_host_private and bind_host_ok,
        "static_url": static_url,
        "proxied_api_url": proxied_api_url,
        "direct_api_url": direct_api_url,
        "public_direct_api_url": public_direct_api_url,
        "api_bind_host": api_bind_host,
        "api_bind_port": api_bind_port,
        "proxied_api_path_ok": api_path_ok,
        "static_path_ok": static_path_ok,
        "direct_api_host_private_or_loopback": direct_host_private,
        "api_bind_host_private_or_loopback": bind_host_private,
        "api_bind_host_policy": "must_not_be_0.0.0.0_or_public",
    }


def _static_site_report(url: str, *, fetch: Fetcher, timeout_seconds: float) -> dict[str, Any]:
    response = fetch(url, {"Accept": "text/html"}, timeout_seconds)
    if not response["ok"]:
        return {
            "ok": False,
            "status": "unavailable",
            "url": url,
            "error": response.get("error"),
        }
    content_type = _header(response, "content-type")
    body_preview = str(response.get("body", ""))[:2048].lower()
    html_ok = "text/html" in content_type.lower() or "<html" in body_preview
    status_code = int(response["status_code"])
    ok = 200 <= status_code < 300 and html_ok
    status = "ready" if ok else "unexpected_response"
    return {
        "ok": ok,
        "status": status,
        "url": url,
        "status_code": status_code,
        "content_type": content_type,
        "html_detected": html_ok,
    }


def _api_health_report(
    url: str,
    *,
    fetch: Fetcher,
    timeout_seconds: float,
    request_id: str,
    origin: str | None,
    require_no_store: bool,
    require_request_id: bool,
    require_cors: bool,
) -> dict[str, Any]:
    headers = {
        "Accept": "application/json",
        "X-Request-ID": request_id,
    }
    if origin:
        headers["Origin"] = origin
    response = fetch(url, headers, timeout_seconds)
    if not response["ok"]:
        return {
            "ok": False,
            "status": "unavailable",
            "url": url,
            "error": response.get("error"),
        }
    payload = _json_payload(response.get("body", ""))
    status_code = int(response["status_code"])
    cache_control = _header(response, "cache-control")
    response_request_id = _header(response, "x-request-id")
    cors_origin = _header(response, "access-control-allow-origin")
    no_store_ok = (not require_no_store) or "no-store" in cache_control.lower()
    request_id_ok = (not require_request_id) or response_request_id == request_id
    cors_ok = (not require_cors) or cors_origin == origin
    service = payload.get("service") if isinstance(payload, dict) else None
    service_ok = service == "astra-backend"
    database = payload.get("database") if isinstance(payload, dict) else None
    database_url_returned = isinstance(database, dict) and "url" in database
    database_url_policy_ok = not database_url_returned
    health_ok = 200 <= status_code < 300 and isinstance(payload, dict) and payload.get("status") in {"ok", "degraded"}
    ok = health_ok and service_ok and database_url_policy_ok and no_store_ok and request_id_ok and cors_ok
    status = "ready" if ok else "unexpected_response"
    return {
        "ok": ok,
        "status": status,
        "url": url,
        "status_code": status_code,
        "health_status": payload.get("status") if isinstance(payload, dict) else None,
        "service": service,
        "service_ok": service_ok,
        "database_url_returned": database_url_returned,
        "database_url_policy_ok": database_url_policy_ok,
        "cache_control": cache_control,
        "cache_no_store_ok": no_store_ok,
        "request_id": response_request_id,
        "request_id_ok": request_id_ok,
        "cors_origin": cors_origin,
        "cors_ok": cors_ok,
    }


def _direct_api_report(
    url: str,
    *,
    fetch: Fetcher,
    timeout_seconds: float,
    request_id: str,
    api_bind_host: str,
) -> dict[str, Any]:
    api_health = _api_health_report(
        url,
        fetch=fetch,
        timeout_seconds=timeout_seconds,
        request_id=request_id,
        origin=None,
        require_no_store=True,
        require_request_id=True,
        require_cors=False,
    )
    parsed = urlparse(url)
    direct_host_private = _host_is_private_or_loopback(parsed.hostname or "")
    bind_host_private = _host_is_private_or_loopback(api_bind_host)
    bind_host_ok = bind_host_private and api_bind_host not in {"0.0.0.0", "::"}
    ok = bool(api_health["ok"] and direct_host_private and bind_host_ok)
    return {
        **api_health,
        "ok": ok,
        "direct_api_host": parsed.hostname,
        "direct_api_host_private_or_loopback": direct_host_private,
        "api_bind_host": api_bind_host,
        "api_bind_host_private_or_loopback": bind_host_private,
        "api_bind_host_policy": "must_not_be_0.0.0.0_or_public",
    }


def _public_exposure_report(
    url: str | None,
    *,
    fetch: Fetcher,
    timeout_seconds: float,
    request_id: str,
) -> dict[str, Any]:
    if not url:
        return {
            "ok": True,
            "status": "skipped_no_public_direct_api_url",
            "url": None,
            "policy": "provide_public_direct_api_url_to_verify_public_port_is_not_reachable",
        }
    response = fetch(url, {"Accept": "application/json", "X-Request-ID": request_id}, timeout_seconds)
    if not response["ok"]:
        return {
            "ok": True,
            "status": "not_reachable",
            "url": url,
            "error": response.get("error"),
            "policy": "public_direct_fastapi_port_must_not_be_reachable",
        }
    return {
        "ok": False,
        "status": "reachable_public_direct_api_port",
        "url": url,
        "status_code": response["status_code"],
        "policy": "public_direct_fastapi_port_must_not_be_reachable",
    }


def _service_plan_report(
    *,
    static_service_name: str,
    api_service_name: str,
    worker_service_name: str,
    proxy_service_name: str,
    static_log_path: str,
    api_stdout_log_path: str,
    api_stderr_log_path: str,
    worker_log_path: str,
    proxy_log_path: str,
    api_bind_host: str,
    api_bind_port: int,
) -> dict[str, Any]:
    log_paths = [static_log_path, api_stdout_log_path, api_stderr_log_path, worker_log_path, proxy_log_path]
    logs_configured = all(_looks_like_windows_path(path) for path in log_paths)
    service_names = (static_service_name, api_service_name, worker_service_name, proxy_service_name)
    names_configured = all(_valid_service_name(name) for name in service_names) and len(set(service_names)) == 4
    bind_host_ok = _host_is_private_or_loopback(api_bind_host) and api_bind_host not in {"0.0.0.0", "::"}
    ok = logs_configured and names_configured and bind_host_ok
    return {
        "ok": ok,
        "status": "ready" if ok else "incomplete",
        "static_service_name": static_service_name,
        "api_service_name": api_service_name,
        "worker_service_name": worker_service_name,
        "proxy_service_name": proxy_service_name,
        "static_log_path": static_log_path,
        "api_stdout_log_path": api_stdout_log_path,
        "api_stderr_log_path": api_stderr_log_path,
        "worker_log_path": worker_log_path,
        "proxy_log_path": proxy_log_path,
        "api_command": f"python -m uvicorn app.main:app --host {api_bind_host} --port {api_bind_port}",
        "service_commands": {
            "start": [f"Start-Service {name}" for name in service_names],
            "stop": [f"Stop-Service {name}" for name in reversed(service_names)],
            "restart": [f"Restart-Service {name}" for name in service_names],
        },
        "logs_configured": logs_configured,
        "names_configured": names_configured,
        "api_bind_host_private_or_loopback": bind_host_ok,
    }


def _windows_services_report(
    *,
    service_names: tuple[str, ...],
    verify: bool,
    query: ServiceQuery,
) -> dict[str, Any]:
    if not verify:
        return {
            "ok": True,
            "status": "skipped_not_requested",
            "verification_requested": False,
            "expected_services": list(service_names),
            "services": [],
        }
    if not all(_valid_service_name(name) for name in service_names):
        return {
            "ok": False,
            "status": "invalid_service_name",
            "verification_requested": True,
            "expected_services": list(service_names),
            "services": [],
        }
    raw = query(service_names)
    if not raw.get("ok"):
        return {
            "ok": False,
            "status": "query_failed",
            "verification_requested": True,
            "expected_services": list(service_names),
            "services": [],
            "error": str(raw.get("error", "ServiceQueryError")),
        }
    source_services = raw.get("services", {})
    services: list[dict[str, Any]] = []
    for name in service_names:
        source = source_services.get(name)
        if not isinstance(source, dict):
            services.append({"name": name, "exists": False, "ok": False})
            continue
        state = str(source.get("state", ""))
        start_mode = str(source.get("start_mode", ""))
        account = str(source.get("account", ""))
        process_id = int(source.get("process_id") or 0)
        running = state.lower() == "running"
        automatic = start_mode.lower() in {"auto", "automatic"}
        process_id_present = process_id > 0
        minimal_account = account.lower().replace(" ", "") in {
            "ntauthority\\localservice",
            "ntauthority\\networkservice",
        }
        services.append(
            {
                "name": name,
                "exists": True,
                "state": state,
                "start_mode": start_mode,
                "account": account,
                "process_id": process_id,
                "running": running,
                "automatic": automatic,
                "process_id_present": process_id_present,
                "minimal_account": minimal_account,
                "ok": running and automatic and process_id_present and minimal_account,
            }
        )
    missing = [item["name"] for item in services if not item["exists"]]
    unhealthy = [item["name"] for item in services if item["exists"] and not item["ok"]]
    ok = not missing and not unhealthy
    return {
        "ok": ok,
        "status": "ready" if ok else "services_not_ready",
        "verification_requested": True,
        "expected_services": list(service_names),
        "services": services,
        "missing_services": missing,
        "unhealthy_services": unhealthy,
        "sensitive_values_returned": False,
    }


def _query_windows_services(service_names: tuple[str, ...]) -> dict[str, Any]:
    if sys.platform != "win32":
        return {"ok": False, "error": "WindowsRequired", "services": {}}
    services: dict[str, dict[str, Any]] = {}
    for service_name in service_names:
        try:
            query = _run_sc("queryex", service_name)
            config = _run_sc("qc", service_name)
        except (OSError, subprocess.SubprocessError) as exc:
            return {"ok": False, "error": exc.__class__.__name__, "services": {}}
        if query.returncode != 0 or config.returncode != 0:
            continue
        parsed = _parse_sc_service_outputs(query.stdout, config.stdout)
        if parsed is None:
            return {"ok": False, "error": "InvalidScQueryOutput", "services": {}}
        services[service_name] = parsed
    return {"ok": True, "services": services}


def _parse_sc_service_outputs(query_output: str, config_output: str) -> dict[str, Any] | None:
    state_match = re.search(r"STATE\s*:\s*\d+\s+([A-Z_]+)", query_output, re.IGNORECASE)
    pid_match = re.search(r"PID\s*:\s*(\d+)", query_output, re.IGNORECASE)
    start_match = re.search(r"START_TYPE\s*:\s*\d+\s+([A-Z_-]+)", config_output, re.IGNORECASE)
    account_match = re.search(r"SERVICE_START_NAME\s*:\s*([^\r\n]+)", config_output, re.IGNORECASE)
    if not all((state_match, pid_match, start_match, account_match)):
        return None
    state_token = state_match.group(1).upper()
    start_token = start_match.group(1).upper()
    return {
        "state": "Running" if state_token == "RUNNING" else state_token.title(),
        "start_mode": "Auto" if start_token == "AUTO_START" else start_token.title(),
        "account": account_match.group(1).strip(),
        "process_id": int(pid_match.group(1)),
    }


def _run_sc(action: str, service_name: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["sc.exe", action, service_name],
        capture_output=True,
        text=True,
        errors="replace",
        timeout=10,
        check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


def _fetch_url(url: str, headers: dict[str, str], timeout_seconds: float) -> FetchResult:
    request = Request(url, headers=headers, method="GET")
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            body = response.read(256 * 1024).decode("utf-8", errors="replace")
            return {
                "ok": True,
                "status_code": response.status,
                "headers": {key.lower(): value for key, value in response.headers.items()},
                "body": body,
            }
    except HTTPError as exc:
        body = exc.read(256 * 1024).decode("utf-8", errors="replace")
        return {
            "ok": True,
            "status_code": exc.code,
            "headers": {key.lower(): value for key, value in exc.headers.items()},
            "body": body,
        }
    except (TimeoutError, URLError, OSError) as exc:
        return {
            "ok": False,
            "status_code": None,
            "headers": {},
            "body": "",
            "error": exc.__class__.__name__,
        }


def _header(response: FetchResult, name: str) -> str:
    headers = response.get("headers", {})
    return str(headers.get(name.lower(), ""))


def _json_payload(body: object) -> object:
    try:
        return json.loads(str(body))
    except json.JSONDecodeError:
        return None


def _host_is_private_or_loopback(host: str) -> bool:
    normalized = host.strip().lower().strip("[]")
    if normalized == "localhost":
        return True
    if not normalized:
        return False
    try:
        address = ip_address(normalized)
    except ValueError:
        return normalized.endswith(".local") or normalized.endswith(".internal")
    if address.is_unspecified:
        return False
    return address.is_loopback or address.is_private


def _looks_like_windows_path(value: str) -> bool:
    if not value.strip():
        return False
    path = PureWindowsPath(value)
    return bool(path.drive and path.parts)


def _valid_service_name(value: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z][A-Za-z0-9._-]{1,63}", value.strip()))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run reverse-proxy and service topology drill checks.")
    parser.add_argument("--static-url", default="http://127.0.0.1:910/", help="Public or local static site URL.")
    parser.add_argument("--proxied-api-url", default="http://127.0.0.1/api/health", help="API health URL through reverse proxy.")
    parser.add_argument("--direct-api-url", default="http://127.0.0.1:8000/api/health", help="Direct local FastAPI health URL.")
    parser.add_argument("--public-direct-api-url", default=None, help="Optional public direct FastAPI URL that should be unreachable.")
    parser.add_argument("--origin", default=None, help="Optional Origin header used to verify CORS through the proxy.")
    parser.add_argument("--request-id", default=DEFAULT_REQUEST_ID, help="Request ID expected to round-trip through FastAPI.")
    parser.add_argument("--api-bind-host", default="127.0.0.1", help="Configured FastAPI bind host.")
    parser.add_argument("--api-bind-port", type=int, default=8000, help="Configured FastAPI bind port.")
    parser.add_argument("--static-service-name", default="EngLab", help="Static service name.")
    parser.add_argument("--api-service-name", default="AstraApi", help="FastAPI service name.")
    parser.add_argument("--worker-service-name", default="AstraWorker", help="Background worker service name.")
    parser.add_argument("--proxy-service-name", default="AstraProxy", help="Reverse proxy service name.")
    parser.add_argument("--static-log-path", default=r"C:\englab\logs\stdout.log", help="Static service stdout log path.")
    parser.add_argument("--api-stdout-log-path", default=r"C:\englab\logs\astra-api-stdout.log", help="FastAPI stdout log path.")
    parser.add_argument("--api-stderr-log-path", default=r"C:\englab\logs\astra-api-stderr.log", help="FastAPI stderr log path.")
    parser.add_argument("--worker-log-path", default=r"C:\englab\logs\astra-worker.log", help="Worker log path.")
    parser.add_argument("--proxy-log-path", default=r"C:\englab\logs\astra-proxy.log", help="Proxy log path.")
    parser.add_argument(
        "--verify-windows-services",
        action="store_true",
        help="Require all four Windows services to be installed, automatic, running, and minimally privileged.",
    )
    parser.add_argument("--timeout-seconds", type=float, default=5.0, help="HTTP timeout for each check.")
    args = parser.parse_args(argv)
    report = run_topology_drill(
        static_url=args.static_url,
        proxied_api_url=args.proxied_api_url,
        direct_api_url=args.direct_api_url,
        public_direct_api_url=args.public_direct_api_url,
        origin=args.origin,
        request_id=args.request_id,
        api_bind_host=args.api_bind_host,
        api_bind_port=args.api_bind_port,
        static_service_name=args.static_service_name,
        api_service_name=args.api_service_name,
        worker_service_name=args.worker_service_name,
        proxy_service_name=args.proxy_service_name,
        static_log_path=args.static_log_path,
        api_stdout_log_path=args.api_stdout_log_path,
        api_stderr_log_path=args.api_stderr_log_path,
        worker_log_path=args.worker_log_path,
        proxy_log_path=args.proxy_log_path,
        verify_windows_services=args.verify_windows_services,
        timeout_seconds=args.timeout_seconds,
    )
    print(json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
