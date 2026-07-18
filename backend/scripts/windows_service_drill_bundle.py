from __future__ import annotations

import argparse
from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path, PureWindowsPath
import shutil
import sys
from xml.etree import ElementTree as ET

from scripts.target_release_evidence import normalize_public_https_origin
from scripts.windows_dpapi_secret_store import inspect_secret_store


SERVICE_NAMES = ("EngLab", "AstraApi", "AstraWorker", "AstraProxy")
ALLOWED_SERVICE_ACCOUNTS = {
    "NT AUTHORITY\\LocalService",
    "NT AUTHORITY\\NetworkService",
}
SERVICE_ACCOUNT_PARTS = {
    "NT AUTHORITY\\LocalService": ("NT AUTHORITY", "LocalService"),
    "NT AUTHORITY\\NetworkService": ("NT AUTHORITY", "NetworkService"),
}
@dataclass(frozen=True)
class ServiceSpec:
    service_id: str
    description: str
    executable: str
    arguments: str
    working_directory: str
    environment: tuple[tuple[str, str], ...] = ()
    dependencies: tuple[str, ...] = ()


def build_windows_service_drill_bundle(
    *,
    output_dir: Path,
    winsw_path: Path,
    static_executable: Path,
    python_executable: Path,
    caddy_executable: Path,
    install_root: Path,
    database_url_value: str = "%ASTRA_DATABASE_URL%",
    secret_store_path: Path | None = None,
    public_origin: str | None = None,
    environment: str = "production",
    admin_bootstrap_enabled: bool = False,
    service_account: str = "NT AUTHORITY\\LocalService",
    static_port: int = 9010,
    api_port: int = 9011,
    proxy_port: int = 9012,
) -> dict[str, object]:
    binaries = {
        "winsw": winsw_path,
        "static": static_executable,
        "python": python_executable,
        "caddy": caddy_executable,
    }
    missing = sorted(name for name, path in binaries.items() if not path.is_file())
    if missing:
        raise ValueError(f"missing required executable(s): {', '.join(missing)}")
    if not install_root.is_dir() or not (install_root / "backend").is_dir():
        raise ValueError("install_root must contain the backend directory")
    if service_account not in ALLOWED_SERVICE_ACCOUNTS:
        raise ValueError("service_account is not in the approved built-in account allowlist")
    if environment not in {"staging", "production"}:
        raise ValueError("environment must be staging or production")
    ports = (static_port, api_port, proxy_port)
    if len(set(ports)) != len(ports) or any(port < 1024 or port > 65535 for port in ports):
        raise ValueError("service ports must be unique and between 1024 and 65535")
    if database_url_value != "%ASTRA_DATABASE_URL%" and not database_url_value.startswith(
        "sqlite+pysqlite:///"
    ):
        raise ValueError("only the environment placeholder or a non-secret SQLite drill URL may be written")
    if secret_store_path is not None:
        if not secret_store_path.is_file():
            raise ValueError("secret_store_path must identify an existing Windows DPAPI store")
        if database_url_value != "%ASTRA_DATABASE_URL%":
            raise ValueError("secret_store_path cannot be combined with an inline database URL")
        secret_store_metadata = inspect_secret_store(secret_store_path)
        if secret_store_metadata["service_account"] != service_account:
            raise ValueError("secret store service account does not match the Windows service account")
    credentialed_origin = (
        _validated_public_origin(public_origin)
        if public_origin is not None
        else f"http://127.0.0.1:{proxy_port}"
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    bin_dir = output_dir / "bin"
    config_dir = output_dir / "config"
    logs_dir = output_dir / "logs"
    data_dir = output_dir / "data"
    for directory in (bin_dir, config_dir, logs_dir, data_dir):
        directory.mkdir(parents=True, exist_ok=True)

    static_target = bin_dir / "englab_server.exe"
    caddy_target = bin_dir / "caddy.exe"
    shutil.copy2(static_executable, static_target)
    shutil.copy2(caddy_executable, caddy_target)
    for service_name in SERVICE_NAMES:
        shutil.copy2(winsw_path, output_dir / f"{service_name}.exe")

    caddyfile = _caddyfile(
        static_port=static_port,
        api_port=api_port,
        proxy_port=proxy_port,
        hsts_enabled=public_origin is not None,
    )
    (config_dir / "Caddyfile").write_text(caddyfile, encoding="utf-8", newline="\n")

    base_environment = [
        ("PYTHONIOENCODING", "utf-8"),
        ("ASTRA_AUTO_CREATE_TABLES", "false"),
        ("ASTRA_ENVIRONMENT", environment),
        ("ASTRA_CORS_ORIGINS", credentialed_origin),
        ("ASTRA_BACKGROUND_TASK_WORKER_ENABLED", "false"),
    ]
    if secret_store_path is None:
        base_environment.append(("ASTRA_DATABASE_URL", database_url_value))
    api_environment = [
        *base_environment,
        ("ASTRA_ADMIN_BOOTSTRAP_ENABLED", "true" if admin_bootstrap_enabled else "false"),
    ]
    worker_environment = [
        *base_environment,
        ("ASTRA_ADMIN_BOOTSTRAP_ENABLED", "false"),
    ]
    install_root_windows = str(PureWindowsPath(install_root))
    backend_root_windows = str(PureWindowsPath(install_root / "backend"))
    python_windows = str(PureWindowsPath(python_executable))
    api_secret_prefix = ""
    worker_secret_prefix = ""
    if secret_store_path is not None:
        secret_store_windows = str(PureWindowsPath(secret_store_path))
        worker_secret_prefix = (
            '-m scripts.windows_dpapi_secret_store run '
            f'--store "{secret_store_windows}" '
            '--required-key ASTRA_DATABASE_URL '
            '--required-key ASTRA_AUDIT_IP_HASH_SALT '
        )
        api_secret_prefix = worker_secret_prefix
        if admin_bootstrap_enabled:
            api_secret_prefix += '--required-key ASTRA_ADMIN_BOOTSTRAP_TOKEN '
        api_secret_prefix += '-- '
        worker_secret_prefix += '-- '
    specs = (
        ServiceSpec(
            service_id="EngLab",
            description="Astra reviewed static fallback service",
            executable=r"%BASE%\bin\englab_server.exe",
            arguments=f'--host 127.0.0.1 -p {static_port} -r "{install_root_windows}"',
            working_directory=install_root_windows,
        ),
        ServiceSpec(
            service_id="AstraApi",
            description="Astra FastAPI business API service",
            executable=python_windows,
            arguments=f"{api_secret_prefix}-m uvicorn app.main:app --host 127.0.0.1 --port {api_port}",
            working_directory=backend_root_windows,
            environment=tuple(api_environment),
        ),
        ServiceSpec(
            service_id="AstraWorker",
            description="Astra independent background task worker",
            executable=python_windows,
            arguments=(
                f"{worker_secret_prefix}-m scripts.run_background_tasks --worker-id astra-windows-worker"
            ),
            working_directory=backend_root_windows,
            environment=tuple(worker_environment),
        ),
        ServiceSpec(
            service_id="AstraProxy",
            description="Astra Caddy same-origin reverse proxy",
            executable=r"%BASE%\bin\caddy.exe",
            arguments=r'run --config "%BASE%\config\Caddyfile" --adapter caddyfile',
            working_directory=r"%BASE%",
        ),
    )
    for spec in specs:
        xml_text = _service_xml(spec, service_account=service_account)
        (output_dir / f"{spec.service_id}.xml").write_text(xml_text, encoding="utf-8", newline="\n")

    artifact_hashes = {
        path.relative_to(output_dir).as_posix(): _file_sha256(path)
        for path in sorted(output_dir.rglob("*"))
        if path.is_file() and (path.suffix.lower() in {".exe", ".xml"} or path.name == "Caddyfile")
    }
    commands = {
        "install": [f'"{output_dir / name}.exe" install' for name in SERVICE_NAMES],
        "start": [f'Start-Service {name}' for name in SERVICE_NAMES],
        "stop": [f'Stop-Service {name}' for name in reversed(SERVICE_NAMES)],
        "restart": [f'Restart-Service {name}' for name in SERVICE_NAMES],
        "uninstall": [f'"{output_dir / name}.exe" uninstall' for name in reversed(SERVICE_NAMES)],
    }
    return {
        "ok": True,
        "status": "ready",
        "services": list(SERVICE_NAMES),
        "service_account": service_account,
        "service_account_is_minimal": True,
        "ports": {"static": static_port, "api": api_port, "proxy": proxy_port},
        "proxy_bind_host": "127.0.0.1",
        "api_bind_host": "127.0.0.1",
        "static_bind_host": "127.0.0.1",
        "database_url_returned": False,
        "database_url_source": (
            "windows_dpapi_local_machine"
            if secret_store_path is not None
            else (
                "service_environment"
                if database_url_value == "%ASTRA_DATABASE_URL%"
                else "non_secret_sqlite_drill"
            )
        ),
        "secret_store_enabled": secret_store_path is not None,
        "secret_store_provider": "WindowsDPAPI-LocalMachine" if secret_store_path is not None else None,
        "secret_store_required_keys": (
            sorted(
                {
                    "ASTRA_AUDIT_IP_HASH_SALT",
                    "ASTRA_DATABASE_URL",
                    *({"ASTRA_ADMIN_BOOTSTRAP_TOKEN"} if admin_bootstrap_enabled else set()),
                }
            )
            if secret_store_path is not None
            else []
        ),
        "secret_store_path_returned": False,
        "credentialed_origin": credentialed_origin,
        "environment": environment,
        "admin_bootstrap_enabled": admin_bootstrap_enabled,
        "artifact_hashes": artifact_hashes,
        "commands": commands,
        "sensitive_values_returned": False,
    }


def _service_xml(spec: ServiceSpec, *, service_account: str) -> str:
    root = ET.Element("service")
    _text_element(root, "id", spec.service_id)
    _text_element(root, "name", spec.service_id)
    _text_element(root, "description", spec.description)
    _text_element(root, "executable", spec.executable)
    _text_element(root, "arguments", spec.arguments)
    _text_element(root, "workingdirectory", spec.working_directory)
    _text_element(root, "startmode", "Automatic")
    _text_element(root, "delayedAutoStart", "true")
    _text_element(root, "stoptimeout", "15 sec")
    _text_element(root, "hidewindow", "true")
    _text_element(root, "logpath", r"%BASE%\logs")
    ET.SubElement(root, "log", {"mode": "roll"})
    ET.SubElement(root, "onfailure", {"action": "restart", "delay": "3 sec"})
    _text_element(root, "resetfailure", "1 hour")
    for dependency in spec.dependencies:
        _text_element(root, "depend", dependency)
    service_account_element = ET.SubElement(root, "serviceaccount")
    domain, user = SERVICE_ACCOUNT_PARTS[service_account]
    # WinSW stable 2.x uses domain + user. WinSW 3.x pre-releases replace
    # these with username; using the 3.x shape on 2.12 silently falls back to
    # LocalSystem, so keep the stable schema explicit here.
    _text_element(service_account_element, "domain", domain)
    _text_element(service_account_element, "user", user)
    if service_account != "LocalSystem":
        _text_element(service_account_element, "allowservicelogon", "true")
    for name, value in spec.environment:
        ET.SubElement(root, "env", {"name": name, "value": value})
    ET.indent(root, space="  ")
    return ET.tostring(root, encoding="unicode", xml_declaration=True) + "\n"


def _text_element(parent: ET.Element, name: str, value: str) -> ET.Element:
    element = ET.SubElement(parent, name)
    element.text = value
    return element


def _caddyfile(
    *,
    static_port: int,
    api_port: int,
    proxy_port: int,
    hsts_enabled: bool,
) -> str:
    hsts = (
        '\theader Strict-Transport-Security "max-age=31536000; includeSubDomains"\n'
        if hsts_enabled
        else ""
    )
    return (
        "{\n"
        "\tadmin off\n"
        "\tauto_https off\n"
        "}\n\n"
        f"http://127.0.0.1:{proxy_port} {{\n"
        "\tbind 127.0.0.1\n"
        f"{hsts}"
        "\t@api path /api/*\n"
        "\thandle @api {\n"
        f"\t\treverse_proxy 127.0.0.1:{api_port}\n"
        "\t}\n"
        "\thandle {\n"
        f"\t\treverse_proxy 127.0.0.1:{static_port}\n"
        "\t}\n"
        "}\n"
    )


def _validated_public_origin(value: str) -> str:
    normalized, _ = normalize_public_https_origin(value)
    if normalized is None:
        raise ValueError("public_origin must be an exact HTTPS origin")
    return normalized


def _file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate a reversible WinSW/Caddy Windows service drill bundle.")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--winsw-path", type=Path, required=True)
    parser.add_argument("--static-executable", type=Path, required=True)
    parser.add_argument("--python-executable", type=Path, default=Path(sys.executable))
    parser.add_argument("--caddy-executable", type=Path, required=True)
    parser.add_argument("--install-root", type=Path, required=True)
    parser.add_argument("--database-url-value", default="%ASTRA_DATABASE_URL%")
    parser.add_argument("--secret-store-path", type=Path, default=None)
    parser.add_argument("--public-origin", default=None)
    parser.add_argument("--environment", choices=("staging", "production"), default="production")
    parser.add_argument("--enable-admin-bootstrap", action="store_true")
    parser.add_argument("--service-account", default="NT AUTHORITY\\LocalService")
    parser.add_argument("--static-port", type=int, default=9010)
    parser.add_argument("--api-port", type=int, default=9011)
    parser.add_argument("--proxy-port", type=int, default=9012)
    args = parser.parse_args(argv)
    try:
        report = build_windows_service_drill_bundle(
            output_dir=args.output_dir.resolve(),
            winsw_path=args.winsw_path.resolve(),
            static_executable=args.static_executable.resolve(),
            python_executable=args.python_executable.resolve(),
            caddy_executable=args.caddy_executable.resolve(),
            install_root=args.install_root.resolve(),
            database_url_value=args.database_url_value,
            secret_store_path=args.secret_store_path.resolve() if args.secret_store_path else None,
            public_origin=args.public_origin,
            environment=args.environment,
            admin_bootstrap_enabled=args.enable_admin_bootstrap,
            service_account=args.service_account,
            static_port=args.static_port,
            api_port=args.api_port,
            proxy_port=args.proxy_port,
        )
    except (OSError, ValueError) as exc:
        report = {
            "ok": False,
            "status": "invalid_bundle_input",
            "error": exc.__class__.__name__,
            "database_url_returned": False,
            "sensitive_values_returned": False,
        }
    print(json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
