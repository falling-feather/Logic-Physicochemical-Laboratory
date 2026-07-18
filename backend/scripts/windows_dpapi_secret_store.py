from __future__ import annotations

import argparse
import base64
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
from typing import Any
from uuid import uuid4

if sys.platform == "win32":
    import msvcrt
else:
    msvcrt = None


SCHEMA_VERSION = "astra-windows-dpapi-v1"
MAX_STORE_BYTES = 1024 * 1024
MAX_SECRET_VALUE_BYTES = 64 * 1024
KEY_PATTERN = re.compile(r"^ASTRA_[A-Z0-9_]+$")
SERVICE_ACCOUNT_SIDS = {
    "NT AUTHORITY\\LocalService": "S-1-5-19",
    "NT AUTHORITY\\NetworkService": "S-1-5-20",
}
_ENTROPY = b"astra-windows-dpapi-v1"
_CRYPTPROTECT_UI_FORBIDDEN = 0x1
_CRYPTPROTECT_LOCAL_MACHINE = 0x4


class _DataBlob(ctypes.Structure):
    _fields_ = (("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_ubyte)))


class _SidAndAttributes(ctypes.Structure):
    _fields_ = (("Sid", wintypes.LPVOID), ("Attributes", wintypes.DWORD))


class _TokenUser(ctypes.Structure):
    _fields_ = (("User", _SidAndAttributes),)


class _SecurityAttributes(ctypes.Structure):
    _fields_ = (
        ("nLength", wintypes.DWORD),
        ("lpSecurityDescriptor", wintypes.LPVOID),
        ("bInheritHandle", wintypes.BOOL),
    )


def seal_secret_store(
    path: Path,
    secrets: dict[str, str],
    *,
    replace: bool = False,
    service_account: str = "NT AUTHORITY\\LocalService",
) -> dict[str, Any]:
    normalized = _normalize_secrets(secrets)
    service_account = _normalize_service_account(service_account)
    operator_sid = _current_process_user_sid()
    cleartext = json.dumps(
        {
            "schema_version": SCHEMA_VERSION,
            "service_account": service_account,
            "operator_sid": operator_sid,
            "secrets": normalized,
        },
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    ciphertext = _protect_data(cleartext)
    envelope = json.dumps(
        {
            "schema_version": SCHEMA_VERSION,
            "scope": "local_machine",
            "service_account": service_account,
            "operator_sid": operator_sid,
            "acl_protected": True,
            "parent_acl_protected": True,
            "ciphertext": base64.b64encode(ciphertext).decode("ascii"),
        },
        ensure_ascii=True,
        indent=2,
        sort_keys=True,
    ).encode("ascii") + b"\n"
    if len(envelope) > MAX_STORE_BYTES:
        raise ValueError("encrypted secret store exceeds the maximum size")
    _atomic_write(
        path,
        envelope,
        replace=replace,
        service_account=service_account,
        operator_sid=operator_sid,
    )
    return _safe_metadata(normalized, service_account=service_account)


def load_secret_store(path: Path) -> dict[str, str]:
    secrets, _service_account, _operator_sid = _load_secret_store_payload(path)
    return secrets


def _load_secret_store_payload(path: Path) -> tuple[dict[str, str], str, str]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise ValueError("secret store cannot be read") from exc
    if not raw or len(raw) > MAX_STORE_BYTES:
        raise ValueError("secret store size is invalid")
    try:
        envelope = json.loads(raw.decode("ascii"))
        if not isinstance(envelope, dict) or envelope.get("schema_version") != SCHEMA_VERSION:
            raise ValueError("secret store schema is invalid")
        if envelope.get("scope") != "local_machine":
            raise ValueError("secret store scope is invalid")
        service_account = _normalize_service_account(envelope.get("service_account"))
        operator_sid = str(envelope.get("operator_sid") or "")
        if not re.fullmatch(r"S-\d+(?:-\d+)+", operator_sid):
            raise ValueError("secret store operator binding is invalid")
        if envelope.get("acl_protected") is not True or envelope.get("parent_acl_protected") is not True:
            raise ValueError("secret store ACL policy is invalid")
        ciphertext = base64.b64decode(envelope.get("ciphertext"), validate=True)
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
        raise ValueError("secret store envelope is invalid") from exc
    try:
        payload = json.loads(_unprotect_data(ciphertext).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, OSError, ValueError) as exc:
        raise ValueError("secret store payload cannot be decrypted") from exc
    if not isinstance(payload, dict) or payload.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("secret store payload schema is invalid")
    if payload.get("service_account") != service_account:
        raise ValueError("secret store service account binding is invalid")
    if payload.get("operator_sid") != operator_sid:
        raise ValueError("secret store operator binding is invalid")
    secrets = payload.get("secrets")
    if not isinstance(secrets, dict):
        raise ValueError("secret store payload is invalid")
    normalized = _normalize_secrets(secrets)
    _verify_restricted_acl(path.parent, service_account=service_account, operator_sid=operator_sid)
    _verify_restricted_acl(path, service_account=service_account, operator_sid=operator_sid)
    return normalized, service_account, operator_sid


def inspect_secret_store(path: Path) -> dict[str, Any]:
    secrets, service_account, _operator_sid = _load_secret_store_payload(path)
    return _safe_metadata(secrets, service_account=service_account)


def run_with_secret_store(
    path: Path,
    required_keys: list[str],
    command: list[str],
    *,
    executable: Path | None = None,
) -> int:
    if not command:
        raise ValueError("child command is required")
    secrets = load_secret_store(path)
    normalized_required = [_normalize_key(value) for value in required_keys]
    if not normalized_required:
        raise ValueError("at least one required secret key is required")
    missing = sorted({value for value in normalized_required if value not in secrets})
    if missing:
        raise ValueError("secret store is missing required keys")
    environment = os.environ.copy()
    for key in secrets:
        environment.pop(key, None)
    environment.update({key: secrets[key] for key in normalized_required})
    child_executable = (executable or Path(sys.executable)).resolve()
    if not child_executable.is_file():
        raise ValueError("child executable must identify an existing file")
    child = subprocess.Popen([str(child_executable), *command], env=environment)

    def stop_child(_signum: int, _frame: Any) -> None:
        if child.poll() is None:
            child.terminate()

    previous_handlers: dict[int, Any] = {}
    for signum in (signal.SIGINT, signal.SIGTERM):
        try:
            previous_handlers[signum] = signal.signal(signum, stop_child)
        except (OSError, ValueError):
            continue
    try:
        return child.wait()
    finally:
        for signum, handler in previous_handlers.items():
            signal.signal(signum, handler)


def _normalize_secrets(value: dict[str, Any]) -> dict[str, str]:
    if not isinstance(value, dict) or not value:
        raise ValueError("at least one secret is required")
    normalized: dict[str, str] = {}
    for raw_key, raw_value in value.items():
        key = _normalize_key(raw_key)
        if key in normalized:
            raise ValueError("duplicate secret key")
        if not isinstance(raw_value, str) or not raw_value or "\x00" in raw_value:
            raise ValueError("secret values must be non-empty strings without NUL bytes")
        if len(raw_value.encode("utf-8")) > MAX_SECRET_VALUE_BYTES:
            raise ValueError("secret value exceeds the maximum size")
        normalized[key] = raw_value
    return dict(sorted(normalized.items()))


def _normalize_key(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("secret keys must be strings")
    key = value.strip().upper()
    if not KEY_PATTERN.fullmatch(key):
        raise ValueError("secret keys must use the ASTRA_ namespace")
    return key


def _normalize_service_account(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("service account must be LocalService or NetworkService")
    normalized = value.strip().replace("/", "\\").lower()
    for account in SERVICE_ACCOUNT_SIDS:
        if account.lower() == normalized:
            return account
    raise ValueError("service account must be LocalService or NetworkService")


def _safe_metadata(
    secrets: dict[str, str],
    *,
    service_account: str,
) -> dict[str, Any]:
    return {
        "ok": True,
        "status": "ready",
        "schema_version": SCHEMA_VERSION,
        "scope": "local_machine",
        "acl_protected": True,
        "parent_acl_protected": True,
        "service_account": service_account,
        "operator_sid_bound": True,
        "operator_sid_returned": False,
        "store_path_returned": False,
        "keys": sorted(secrets),
        "secret_count": len(secrets),
        "sensitive_values_returned": False,
    }


def _atomic_write(
    path: Path,
    data: bytes,
    *,
    replace: bool,
    service_account: str,
    operator_sid: str,
) -> None:
    path = path.resolve()
    _ensure_restricted_directory(
        path.parent,
        service_account=service_account,
        operator_sid=operator_sid,
    )
    if path.exists() and not replace:
        raise FileExistsError("secret store already exists; pass --replace explicitly")
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        _write_restricted_file(
            temporary,
            data,
            service_account=service_account,
            operator_sid=operator_sid,
        )
        if replace:
            os.replace(temporary, path)
        else:
            os.rename(temporary, path)
        _verify_restricted_acl(path, service_account=service_account, operator_sid=operator_sid)
    finally:
        temporary.unlink(missing_ok=True)


def _ensure_restricted_directory(
    path: Path,
    *,
    service_account: str,
    operator_sid: str,
) -> None:
    if path.exists():
        if not path.is_dir():
            raise ValueError("secret store parent must be a dedicated directory")
        _verify_restricted_acl(path, service_account=service_account, operator_sid=operator_sid)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    service_sid = SERVICE_ACCOUNT_SIDS[service_account]
    security_descriptor = _security_descriptor_from_sddl(
        "D:P"
        "(A;;FA;;;SY)"
        "(A;;FA;;;BA)"
        f"(A;;FA;;;{operator_sid})"
        f"(A;;FR;;;{service_sid})"
    )
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateDirectoryW.argtypes = (
        wintypes.LPCWSTR,
        ctypes.POINTER(_SecurityAttributes),
    )
    kernel32.CreateDirectoryW.restype = wintypes.BOOL
    attributes = _SecurityAttributes(
        ctypes.sizeof(_SecurityAttributes),
        security_descriptor,
        False,
    )
    try:
        if not kernel32.CreateDirectoryW(str(path), ctypes.byref(attributes)):
            error = ctypes.get_last_error()
            if error != 183:
                raise ctypes.WinError(error)
    finally:
        _local_free(security_descriptor)
    _verify_restricted_acl(path, service_account=service_account, operator_sid=operator_sid)


def _write_restricted_file(
    path: Path,
    data: bytes,
    *,
    service_account: str,
    operator_sid: str,
) -> None:
    if sys.platform != "win32":
        raise OSError("Windows DPAPI is required")
    if msvcrt is None:
        raise OSError("Windows file-descriptor support is required")
    service_sid = SERVICE_ACCOUNT_SIDS[service_account]
    security_descriptor = _security_descriptor_from_sddl(
        "D:P"
        "(A;;FA;;;SY)"
        "(A;;FA;;;BA)"
        f"(A;;FA;;;{operator_sid})"
        f"(A;;FR;;;{service_sid})"
    )
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateFileW.argtypes = (
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.POINTER(_SecurityAttributes),
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    )
    kernel32.CreateFileW.restype = wintypes.HANDLE
    attributes = _SecurityAttributes(
        ctypes.sizeof(_SecurityAttributes),
        security_descriptor,
        False,
    )
    handle = kernel32.CreateFileW(
        str(path),
        0x40000000,
        0,
        ctypes.byref(attributes),
        1,
        0x80,
        None,
    )
    invalid_handle = ctypes.c_void_p(-1).value
    if handle == invalid_handle:
        _local_free(security_descriptor)
        raise ctypes.WinError(ctypes.get_last_error())
    descriptor_freed = False
    try:
        descriptor_freed = True
        _local_free(security_descriptor)
        file_descriptor = msvcrt.open_osfhandle(handle, os.O_WRONLY | os.O_BINARY)
        handle = None
        with os.fdopen(file_descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
    finally:
        if not descriptor_freed:
            _local_free(security_descriptor)
        if handle not in (None, invalid_handle):
            kernel32.CloseHandle(handle)


def _verify_restricted_acl(
    path: Path,
    *,
    service_account: str,
    operator_sid: str,
) -> None:
    sddl = _file_dacl_sddl(path)
    if not sddl.startswith("D:P"):
        raise ValueError("secret store ACL inheritance is not protected")
    aliases = {
        "S-1-5-18": "SY",
        "S-1-5-19": "LS",
        "S-1-5-20": "NS",
        "S-1-5-32-544": "BA",
    }
    expected = {
        ("FA", "SY"),
        ("FA", "BA"),
        ("FA", operator_sid),
        ("FR", aliases[SERVICE_ACCOUNT_SIDS[service_account]]),
    }
    actual_entries: list[tuple[str, str]] = []
    for raw_ace in re.findall(r"\(([^()]*)\)", sddl):
        fields = raw_ace.split(";")
        if len(fields) != 6 or fields[0] != "A" or fields[1] or fields[3] or fields[4]:
            raise ValueError("secret store ACL contains an unexpected access rule")
        rights = {"0x1f01ff": "FA", "0x120089": "FR"}.get(fields[2].lower(), fields[2])
        trustee = aliases.get(fields[5], fields[5])
        actual_entries.append((rights, trustee))
    if len(actual_entries) != len(expected) or set(actual_entries) != expected:
        raise ValueError("secret store ACL does not match the restricted service policy")


def _file_dacl_sddl(path: Path) -> str:
    advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
    security_descriptor = wintypes.LPVOID()
    advapi32.GetNamedSecurityInfoW.argtypes = (
        wintypes.LPWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.LPVOID),
        ctypes.POINTER(wintypes.LPVOID),
        ctypes.POINTER(wintypes.LPVOID),
        ctypes.POINTER(wintypes.LPVOID),
        ctypes.POINTER(wintypes.LPVOID),
    )
    advapi32.GetNamedSecurityInfoW.restype = wintypes.DWORD
    result = advapi32.GetNamedSecurityInfoW(
        str(path),
        1,
        0x4,
        None,
        None,
        None,
        None,
        ctypes.byref(security_descriptor),
    )
    if result != 0:
        raise OSError(result, "secret store ACL cannot be read")
    output = wintypes.LPWSTR()
    output_length = wintypes.DWORD()
    advapi32.ConvertSecurityDescriptorToStringSecurityDescriptorW.argtypes = (
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.LPWSTR),
        ctypes.POINTER(wintypes.DWORD),
    )
    advapi32.ConvertSecurityDescriptorToStringSecurityDescriptorW.restype = wintypes.BOOL
    try:
        if not advapi32.ConvertSecurityDescriptorToStringSecurityDescriptorW(
            security_descriptor,
            1,
            0x4,
            ctypes.byref(output),
            ctypes.byref(output_length),
        ):
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            return output.value
        finally:
            _local_free(output)
    finally:
        _local_free(security_descriptor)


def _security_descriptor_from_sddl(value: str) -> wintypes.LPVOID:
    advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
    descriptor = wintypes.LPVOID()
    length = wintypes.DWORD()
    advapi32.ConvertStringSecurityDescriptorToSecurityDescriptorW.argtypes = (
        wintypes.LPCWSTR,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.LPVOID),
        ctypes.POINTER(wintypes.DWORD),
    )
    advapi32.ConvertStringSecurityDescriptorToSecurityDescriptorW.restype = wintypes.BOOL
    if not advapi32.ConvertStringSecurityDescriptorToSecurityDescriptorW(
        value,
        1,
        ctypes.byref(descriptor),
        ctypes.byref(length),
    ):
        raise ctypes.WinError(ctypes.get_last_error())
    return descriptor


def _current_process_user_sid() -> str:
    advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    token = wintypes.HANDLE()
    advapi32.OpenProcessToken.argtypes = (
        wintypes.HANDLE,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.HANDLE),
    )
    advapi32.OpenProcessToken.restype = wintypes.BOOL
    advapi32.GetTokenInformation.argtypes = (
        wintypes.HANDLE,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
    )
    advapi32.GetTokenInformation.restype = wintypes.BOOL
    kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
    kernel32.CloseHandle.restype = wintypes.BOOL
    if not advapi32.OpenProcessToken(kernel32.GetCurrentProcess(), 0x8, ctypes.byref(token)):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        size = wintypes.DWORD()
        advapi32.GetTokenInformation(token, 1, None, 0, ctypes.byref(size))
        if ctypes.get_last_error() != 122 or not size.value:
            raise ctypes.WinError(ctypes.get_last_error())
        buffer = ctypes.create_string_buffer(size.value)
        if not advapi32.GetTokenInformation(token, 1, buffer, size.value, ctypes.byref(size)):
            raise ctypes.WinError(ctypes.get_last_error())
        token_user = ctypes.cast(buffer, ctypes.POINTER(_TokenUser)).contents
        output = wintypes.LPWSTR()
        advapi32.ConvertSidToStringSidW.argtypes = (
            wintypes.LPVOID,
            ctypes.POINTER(wintypes.LPWSTR),
        )
        advapi32.ConvertSidToStringSidW.restype = wintypes.BOOL
        if not advapi32.ConvertSidToStringSidW(token_user.User.Sid, ctypes.byref(output)):
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            return output.value
        finally:
            _local_free(output)
    finally:
        kernel32.CloseHandle(token)


def _local_free(value: Any) -> None:
    if not value:
        return
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.LocalFree.argtypes = (wintypes.HLOCAL,)
    kernel32.LocalFree.restype = wintypes.HLOCAL
    kernel32.LocalFree(value)


def _protect_data(value: bytes) -> bytes:
    crypt32, kernel32 = _windows_crypto_libraries()
    value_blob, value_buffer = _blob(value)
    entropy_blob, entropy_buffer = _blob(_ENTROPY)
    output_blob = _DataBlob()
    _ = value_buffer, entropy_buffer
    if not crypt32.CryptProtectData(
        ctypes.byref(value_blob),
        None,
        ctypes.byref(entropy_blob),
        None,
        None,
        _CRYPTPROTECT_UI_FORBIDDEN | _CRYPTPROTECT_LOCAL_MACHINE,
        ctypes.byref(output_blob),
    ):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        return ctypes.string_at(output_blob.pbData, output_blob.cbData)
    finally:
        kernel32.LocalFree(output_blob.pbData)


def _unprotect_data(value: bytes) -> bytes:
    crypt32, kernel32 = _windows_crypto_libraries()
    value_blob, value_buffer = _blob(value)
    entropy_blob, entropy_buffer = _blob(_ENTROPY)
    output_blob = _DataBlob()
    _ = value_buffer, entropy_buffer
    if not crypt32.CryptUnprotectData(
        ctypes.byref(value_blob),
        None,
        ctypes.byref(entropy_blob),
        None,
        None,
        _CRYPTPROTECT_UI_FORBIDDEN,
        ctypes.byref(output_blob),
    ):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        return ctypes.string_at(output_blob.pbData, output_blob.cbData)
    finally:
        kernel32.LocalFree(output_blob.pbData)


def _blob(value: bytes) -> tuple[_DataBlob, Any]:
    buffer = ctypes.create_string_buffer(value)
    return (
        _DataBlob(len(value), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte))),
        buffer,
    )


def _windows_crypto_libraries() -> tuple[Any, Any]:
    if sys.platform != "win32":
        raise OSError("Windows DPAPI is required")
    crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    crypt32.CryptProtectData.argtypes = (
        ctypes.POINTER(_DataBlob),
        wintypes.LPCWSTR,
        ctypes.POINTER(_DataBlob),
        wintypes.LPVOID,
        wintypes.LPVOID,
        wintypes.DWORD,
        ctypes.POINTER(_DataBlob),
    )
    crypt32.CryptProtectData.restype = wintypes.BOOL
    crypt32.CryptUnprotectData.argtypes = (
        ctypes.POINTER(_DataBlob),
        ctypes.POINTER(wintypes.LPWSTR),
        ctypes.POINTER(_DataBlob),
        wintypes.LPVOID,
        wintypes.LPVOID,
        wintypes.DWORD,
        ctypes.POINTER(_DataBlob),
    )
    crypt32.CryptUnprotectData.restype = wintypes.BOOL
    kernel32.LocalFree.argtypes = (wintypes.HLOCAL,)
    kernel32.LocalFree.restype = wintypes.HLOCAL
    return crypt32, kernel32


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Seal or consume an Astra Windows DPAPI secret store.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    seal_parser = subparsers.add_parser("seal", help="Read an ASTRA_* JSON mapping from stdin and seal it.")
    seal_parser.add_argument("--output", type=Path, required=True)
    seal_parser.add_argument("--replace", action="store_true")
    seal_parser.add_argument(
        "--service-account",
        choices=sorted(SERVICE_ACCOUNT_SIDS),
        default="NT AUTHORITY\\LocalService",
    )

    inspect_parser = subparsers.add_parser("inspect", help="Return only non-sensitive store metadata.")
    inspect_parser.add_argument("--store", type=Path, required=True)

    run_parser = subparsers.add_parser("run", help="Inject selected secrets into one child process.")
    run_parser.add_argument("--store", type=Path, required=True)
    run_parser.add_argument("--required-key", action="append", default=[])
    run_parser.add_argument("--executable", type=Path, default=None)
    run_parser.add_argument("child_command", nargs=argparse.REMAINDER)

    args = parser.parse_args(argv)
    try:
        if args.command == "seal":
            raw = sys.stdin.buffer.read(MAX_STORE_BYTES + 1)
            if len(raw) > MAX_STORE_BYTES:
                raise ValueError("secret input exceeds the maximum size")
            payload = json.loads(raw.decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("secret input must be a JSON object")
            report = seal_secret_store(
                args.output,
                payload,
                replace=args.replace,
                service_account=args.service_account,
            )
            print(json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True))
            return 0
        if args.command == "inspect":
            print(json.dumps(inspect_secret_store(args.store), ensure_ascii=True, indent=2, sort_keys=True))
            return 0
        child_command = list(args.child_command)
        if child_command and child_command[0] == "--":
            child_command.pop(0)
        return run_with_secret_store(
            args.store,
            args.required_key,
            child_command,
            executable=args.executable,
        )
    except (FileExistsError, json.JSONDecodeError, OSError, ValueError) as exc:
        print(
            json.dumps(
                {
                    "ok": False,
                    "status": "secret_store_error",
                    "error": exc.__class__.__name__,
                    "sensitive_values_returned": False,
                },
                ensure_ascii=True,
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
