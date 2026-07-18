from contextlib import contextmanager
from pathlib import Path
import shutil
import sys
from uuid import uuid4

import pytest
import scripts.windows_dpapi_secret_store as secret_store_module

from scripts.windows_dpapi_secret_store import (
    _file_dacl_sddl,
    inspect_secret_store,
    load_secret_store,
    run_with_secret_store,
    seal_secret_store,
)


pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows DPAPI is required")


def test_dpapi_store_round_trip_returns_metadata_without_secret_values(monkeypatch):
    with _runtime_dir() as runtime:
        store = runtime / "secrets" / "astra-staging.dpapi"
        secrets = {
            "ASTRA_DATABASE_URL": "mysql+pymysql://service:private-value@127.0.0.1:3307/astra",
            "ASTRA_AUDIT_IP_HASH_SALT": "audit-private-value",
            "ASTRA_ADMIN_BOOTSTRAP_TOKEN": "bootstrap-private-value",
        }

        report = seal_secret_store(store, secrets)
        encrypted = store.read_text(encoding="ascii")

        assert report["ok"] is True
        assert report["scope"] == "local_machine"
        assert report["acl_protected"] is True
        assert report["parent_acl_protected"] is True
        assert report["service_account"] == "NT AUTHORITY\\LocalService"
        assert report["operator_sid_bound"] is True
        assert report["operator_sid_returned"] is False
        assert report["store_path_returned"] is False
        assert report["keys"] == sorted(secrets)
        assert report["sensitive_values_returned"] is False
        assert all(secret not in encrypted for secret in secrets.values())
        monkeypatch.setattr(secret_store_module, "_current_process_user_sid", lambda: "S-1-5-19")
        assert load_secret_store(store) == secrets
        assert inspect_secret_store(store) == report
        assert _file_dacl_sddl(store).startswith("D:P")
        assert _file_dacl_sddl(store.parent).startswith("D:P")


def test_dpapi_store_refuses_implicit_replace_and_non_astra_namespace():
    with _runtime_dir() as runtime:
        store = runtime / "secrets" / "astra-staging.dpapi"
        seal_secret_store(store, {"ASTRA_DATABASE_URL": "first"})

        with pytest.raises(FileExistsError, match="--replace"):
            seal_secret_store(store, {"ASTRA_DATABASE_URL": "second"})
        with pytest.raises(ValueError, match="ASTRA_ namespace"):
            seal_secret_store(runtime / "secrets" / "invalid.dpapi", {"PATH": "not-allowed"})
        with pytest.raises(ValueError, match="LocalService or NetworkService"):
            seal_secret_store(
                runtime / "secrets" / "unsafe-account.dpapi",
                {"ASTRA_DATABASE_URL": "private"},
                service_account="LocalSystem",
            )


def test_dpapi_runner_injects_only_required_keys_into_python_child(monkeypatch):
    with _runtime_dir() as runtime:
        store = runtime / "secrets" / "astra-staging.dpapi"
        seal_secret_store(
            store,
            {
                "ASTRA_DATABASE_URL": "private-database-value",
                "ASTRA_AUDIT_IP_HASH_SALT": "private-audit-value",
                "ASTRA_ADMIN_BOOTSTRAP_TOKEN": "must-not-be-injected",
            },
        )
        child = [
            "-c",
            (
                "import os,sys; "
                "sys.exit(0 if os.environ.get('ASTRA_DATABASE_URL') "
                "and os.environ.get('ASTRA_AUDIT_IP_HASH_SALT') "
                "and 'ASTRA_ADMIN_BOOTSTRAP_TOKEN' not in os.environ else 3)"
            ),
        ]
        monkeypatch.setenv("ASTRA_ADMIN_BOOTSTRAP_TOKEN", "must-also-be-removed-from-parent")

        exit_code = run_with_secret_store(
            store,
            ["ASTRA_DATABASE_URL", "ASTRA_AUDIT_IP_HASH_SALT"],
            child,
            executable=Path(sys.executable),
        )

        assert exit_code == 0


def test_dpapi_runner_rejects_missing_required_key_without_naming_values():
    with _runtime_dir() as runtime:
        store = runtime / "secrets" / "astra-staging.dpapi"
        seal_secret_store(store, {"ASTRA_DATABASE_URL": "private-database-value"})

        with pytest.raises(ValueError, match="missing required keys"):
            run_with_secret_store(store, ["ASTRA_AUDIT_IP_HASH_SALT"], ["-c", "pass"])


@contextmanager
def _runtime_dir():
    backend_root = Path(__file__).resolve().parents[1]
    runtime = backend_root / "pytest-cache-files-dpapi-secret-store" / uuid4().hex
    runtime.mkdir(parents=True)
    try:
        yield runtime
    finally:
        shutil.rmtree(runtime, ignore_errors=True)
