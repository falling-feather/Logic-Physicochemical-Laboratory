from contextlib import contextmanager
from pathlib import Path
import shutil
import sys
from uuid import uuid4
from xml.etree import ElementTree as ET

import pytest

import scripts.windows_service_drill_bundle as bundle_module
from scripts.windows_service_drill_bundle import build_windows_service_drill_bundle


def test_root_deploy_wrapper_forwards_reviewed_generator_contract_and_exit_code():
    root = Path(__file__).resolve().parents[2]
    source = (root / "deploy.ps1").read_text(encoding="utf-8")

    assert '"backend\\scripts\\windows_service_drill_bundle.py"' in source
    for parameter, option in (
        ("$OutputDir", '"--output-dir"'),
        ("$WinSwPath", '"--winsw-path"'),
        ("$StaticExecutable", '"--static-executable"'),
        ("$CaddyExecutable", '"--caddy-executable"'),
        ("$InstallRoot", '"--install-root"'),
        ("$DatabaseUrlValue", '"--database-url-value"'),
        ("$SecretStorePath", '"--secret-store-path"'),
        ("$PublicOrigin", '"--public-origin"'),
        ("$Environment", '"--environment"'),
        ("$EnableAdminBootstrap", '"--enable-admin-bootstrap"'),
        ("$ServiceAccount", '"--service-account"'),
        ("$StaticPort", '"--static-port"'),
        ("$ApiPort", '"--api-port"'),
        ("$ProxyPort", '"--proxy-port"'),
    ):
        assert option in source
        assert parameter in source
    assert "if ($LASTEXITCODE -ne 0)" in source
    assert "New-NetFirewallRule" not in source
    assert "Invoke-WebRequest" not in source


def test_windows_service_bundle_is_loopback_minimal_and_reversible():
    with _runtime_dir() as runtime:
        install_root = runtime / "install"
        (install_root / "backend").mkdir(parents=True)
        winsw = _fake_binary(runtime / "WinSW.exe", b"winsw")
        static = _fake_binary(runtime / "englab_server.exe", b"static")
        python = _fake_binary(runtime / "python.exe", b"python")
        caddy = _fake_binary(runtime / "caddy.exe", b"caddy")
        output = runtime / "bundle"

        report = build_windows_service_drill_bundle(
            output_dir=output,
            winsw_path=winsw,
            static_executable=static,
            python_executable=python,
            caddy_executable=caddy,
            install_root=install_root,
            database_url_value="sqlite+pysqlite:///C:/astra-v62-drill.sqlite",
        )

        assert report["ok"] is True
        assert report["services"] == ["EngLab", "AstraApi", "AstraWorker", "AstraProxy"]
        assert report["service_account"] == "NT AUTHORITY\\LocalService"
        assert report["service_account_is_minimal"] is True
        assert report["environment"] == "production"
        assert report["database_url_returned"] is False
        assert report["sensitive_values_returned"] is False
        assert "config/Caddyfile" in report["artifact_hashes"]
        assert len(report["commands"]["uninstall"]) == 4
        for service_name in report["services"]:
            assert (output / f"{service_name}.exe").read_bytes() == b"winsw"
            root = ET.parse(output / f"{service_name}.xml").getroot()
            assert root.findtext("id") == service_name
            assert root.findtext("serviceaccount/domain") == "NT AUTHORITY"
            assert root.findtext("serviceaccount/user") == "LocalService"
            assert root.find("serviceaccount/username") is None
            assert root.findtext("serviceaccount/allowservicelogon") == "true"
            assert root.findtext("startmode") == "Automatic"
            assert root.find("onfailure").attrib == {"action": "restart", "delay": "3 sec"}

        api_root = ET.parse(output / "AstraApi.xml").getroot()
        api_environment = {element.attrib["name"]: element.attrib["value"] for element in api_root.findall("env")}
        assert api_environment["ASTRA_ENVIRONMENT"] == "production"
        assert api_environment["ASTRA_DATABASE_URL"].startswith("sqlite+pysqlite:///")
        assert api_environment["ASTRA_ADMIN_BOOTSTRAP_ENABLED"] == "false"
        assert api_environment["ASTRA_CORS_ORIGINS"] == "http://127.0.0.1:9012"
        proxy_root = ET.parse(output / "AstraProxy.xml").getroot()
        assert proxy_root.findall("depend") == []
        caddyfile = (output / "config" / "Caddyfile").read_text(encoding="utf-8")
        assert "bind 127.0.0.1" in caddyfile
        assert caddyfile.index("@api path /api/*") < caddyfile.index("reverse_proxy 127.0.0.1:9010")
        assert "reverse_proxy 127.0.0.1:9011" in caddyfile


def test_windows_service_bundle_uses_dpapi_store_without_embedding_secrets(monkeypatch):
    with _runtime_dir() as runtime:
        install_root = runtime / "install"
        (install_root / "backend").mkdir(parents=True)
        binary = _fake_binary(runtime / "tool.exe", b"tool")
        secret_store = runtime / "secrets" / "astra-staging.dpapi"
        if sys.platform == "win32":
            from scripts.windows_dpapi_secret_store import seal_secret_store

            seal_secret_store(
                secret_store,
                {
                    "ASTRA_DATABASE_URL": "private-database-value",
                    "ASTRA_AUDIT_IP_HASH_SALT": "private-audit-value",
                    "ASTRA_ADMIN_BOOTSTRAP_TOKEN": "private-bootstrap-value",
                },
            )
        else:
            secret_store.parent.mkdir(parents=True)
            secret_store.write_bytes(b"encrypted-test-placeholder")
            monkeypatch.setattr(
                bundle_module,
                "inspect_secret_store",
                lambda _path: {"service_account": "NT AUTHORITY\\LocalService"},
            )
        output = runtime / "bundle"

        report = build_windows_service_drill_bundle(
            output_dir=output,
            winsw_path=binary,
            static_executable=binary,
            python_executable=binary,
            caddy_executable=binary,
            install_root=install_root,
            secret_store_path=secret_store,
            public_origin="https://astra-staging.trycloudflare.com",
            admin_bootstrap_enabled=True,
        )

        assert report["ok"] is True
        assert report["database_url_source"] == "windows_dpapi_local_machine"
        assert report["secret_store_enabled"] is True
        assert report["secret_store_provider"] == "WindowsDPAPI-LocalMachine"
        assert report["secret_store_path_returned"] is False
        assert report["credentialed_origin"] == "https://astra-staging.trycloudflare.com"
        assert report["admin_bootstrap_enabled"] is True
        api_root = ET.parse(output / "AstraApi.xml").getroot()
        api_environment = {element.attrib["name"]: element.attrib["value"] for element in api_root.findall("env")}
        assert "ASTRA_DATABASE_URL" not in api_environment
        assert api_environment["ASTRA_ENVIRONMENT"] == "production"
        assert api_environment["ASTRA_CORS_ORIGINS"] == "https://astra-staging.trycloudflare.com"
        assert 'Strict-Transport-Security "max-age=31536000; includeSubDomains"' in (
            output / "config" / "Caddyfile"
        ).read_text(encoding="utf-8")
        arguments = api_root.findtext("arguments") or ""
        assert "scripts.windows_dpapi_secret_store run" in arguments
        assert "--required-key ASTRA_DATABASE_URL" in arguments
        assert "--required-key ASTRA_AUDIT_IP_HASH_SALT" in arguments
        assert "--required-key ASTRA_ADMIN_BOOTSTRAP_TOKEN" in arguments
        assert "mysql+pymysql" not in arguments
        worker_root = ET.parse(output / "AstraWorker.xml").getroot()
        worker_environment = {
            element.attrib["name"]: element.attrib["value"] for element in worker_root.findall("env")
        }
        worker_arguments = worker_root.findtext("arguments") or ""
        assert worker_environment["ASTRA_ADMIN_BOOTSTRAP_ENABLED"] == "false"
        assert "--required-key ASTRA_ADMIN_BOOTSTRAP_TOKEN" not in worker_arguments

        with pytest.raises(ValueError, match="does not match the Windows service account"):
            build_windows_service_drill_bundle(
                output_dir=runtime / "mismatched-bundle",
                winsw_path=binary,
                static_executable=binary,
                python_executable=binary,
                caddy_executable=binary,
                install_root=install_root,
                secret_store_path=secret_store,
                public_origin="https://astra-staging.trycloudflare.com",
                service_account="NT AUTHORITY\\NetworkService",
            )


def test_windows_service_bundle_preserves_staging_environment_semantics():
    with _runtime_dir() as runtime:
        install_root = runtime / "install"
        (install_root / "backend").mkdir(parents=True)
        binary = _fake_binary(runtime / "tool.exe", b"tool")

        report = build_windows_service_drill_bundle(
            output_dir=runtime / "bundle",
            winsw_path=binary,
            static_executable=binary,
            python_executable=binary,
            caddy_executable=binary,
            install_root=install_root,
            database_url_value="sqlite+pysqlite:///C:/astra-staging-drill.sqlite",
            environment="staging",
        )

        assert report["environment"] == "staging"
        api_root = ET.parse(runtime / "bundle" / "AstraApi.xml").getroot()
        environment = {element.attrib["name"]: element.attrib["value"] for element in api_root.findall("env")}
        assert environment["ASTRA_ENVIRONMENT"] == "staging"


def test_windows_service_bundle_rejects_unknown_environment():
    with _runtime_dir() as runtime:
        install_root = runtime / "install"
        (install_root / "backend").mkdir(parents=True)
        binary = _fake_binary(runtime / "tool.exe", b"tool")

        with pytest.raises(ValueError, match="environment must be staging or production"):
            build_windows_service_drill_bundle(
                output_dir=runtime / "bundle",
                winsw_path=binary,
                static_executable=binary,
                python_executable=binary,
                caddy_executable=binary,
                install_root=install_root,
                environment="development",
            )


@pytest.mark.parametrize(
    "origin",
    [
        "http://127.0.0.1:9012",
        "https://127.0.0.1",
        "https://10.0.0.8",
        "https://staging",
        "https://staging.invalid",
        "https://learn.example",
        "https://example.com",
        "https://learn.example.net",
        "https://learn.example.org",
        "https://learn.example.edu",
        "https://learn.astra.school:444",
    ],
)
def test_windows_service_bundle_rejects_non_public_https_origin(origin):
    with _runtime_dir() as runtime:
        install_root = runtime / "install"
        (install_root / "backend").mkdir(parents=True)
        binary = _fake_binary(runtime / "tool.exe", b"tool")

        with pytest.raises(ValueError, match="exact HTTPS origin"):
            build_windows_service_drill_bundle(
                output_dir=runtime / "bundle",
                winsw_path=binary,
                static_executable=binary,
                python_executable=binary,
                caddy_executable=binary,
                install_root=install_root,
                public_origin=origin,
            )


def test_windows_service_bundle_rejects_secret_bearing_database_url():
    with _runtime_dir() as runtime:
        install_root = runtime / "install"
        (install_root / "backend").mkdir(parents=True)
        binary = _fake_binary(runtime / "tool.exe", b"tool")

        with pytest.raises(ValueError, match="non-secret SQLite"):
            build_windows_service_drill_bundle(
                output_dir=runtime / "bundle",
                winsw_path=binary,
                static_executable=binary,
                python_executable=binary,
                caddy_executable=binary,
                install_root=install_root,
                database_url_value="mysql+pymysql://user:secret@127.0.0.1/astra",
            )


def test_windows_service_bundle_rejects_localsystem_account():
    with _runtime_dir() as runtime:
        install_root = runtime / "install"
        (install_root / "backend").mkdir(parents=True)
        binary = _fake_binary(runtime / "tool.exe", b"tool")

        with pytest.raises(ValueError, match="built-in account allowlist"):
            build_windows_service_drill_bundle(
                output_dir=runtime / "bundle",
                winsw_path=binary,
                static_executable=binary,
                python_executable=binary,
                caddy_executable=binary,
                install_root=install_root,
                service_account="LocalSystem",
            )


def _fake_binary(path: Path, content: bytes) -> Path:
    path.write_bytes(content)
    return path


@contextmanager
def _runtime_dir():
    backend_root = Path(__file__).resolve().parents[1]
    runtime = backend_root / "pytest-cache-files-service-bundle" / uuid4().hex
    runtime.mkdir(parents=True)
    try:
        yield runtime
    finally:
        shutil.rmtree(runtime, ignore_errors=True)
