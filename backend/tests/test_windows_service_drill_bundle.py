from contextlib import contextmanager
from pathlib import Path
import shutil
from uuid import uuid4
from xml.etree import ElementTree as ET

import pytest

from scripts.windows_service_drill_bundle import build_windows_service_drill_bundle


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
        assert api_environment["ASTRA_DATABASE_URL"].startswith("sqlite+pysqlite:///")
        assert api_environment["ASTRA_ADMIN_BOOTSTRAP_ENABLED"] == "false"
        assert api_environment["ASTRA_CORS_ORIGINS"] == "http://127.0.0.1:9012"
        proxy_root = ET.parse(output / "AstraProxy.xml").getroot()
        assert proxy_root.findall("depend") == []
        caddyfile = (output / "config" / "Caddyfile").read_text(encoding="utf-8")
        assert "bind 127.0.0.1" in caddyfile
        assert caddyfile.index("@api path /api/*") < caddyfile.index("reverse_proxy 127.0.0.1:9010")
        assert "reverse_proxy 127.0.0.1:9011" in caddyfile


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
