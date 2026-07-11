from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any, Protocol
from urllib import error as urllib_error
from urllib import request as urllib_request
from urllib.parse import urljoin, urlparse

from app.core.config import Settings
from app.models import BugRecord


_REPOSITORY_PART_PATTERN = re.compile(r"^[A-Za-z0-9_.-]{1,100}$")
_API_VERSION_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_SENSITIVE_TEXT_MARKERS = (
    "-----begin",
    "api_key",
    "authorization:",
    "bearer ",
    "client_secret",
    "cookie:",
    "password=",
    "password:",
    "private_key",
    "secret=",
    "secret:",
    "session_token",
    "token=",
    "token:",
)


@dataclass(frozen=True)
class ExternalIssueReceipt:
    provider: str
    issue_id: str
    issue_url: str
    state: str
    updated_at: datetime | None
    response_hash: str


@dataclass(frozen=True)
class ExternalCommentReceipt:
    provider: str
    comment_id: str
    comment_url: str
    response_hash: str


class IssueProviderError(RuntimeError):
    def __init__(self, code: str, *, retryable: bool, ambiguous: bool = False) -> None:
        super().__init__(code)
        self.code = code
        self.retryable = retryable
        self.ambiguous = ambiguous


class IssueProviderAdapter(Protocol):
    provider: str

    def create_issue(self, *, title: str, body: str) -> ExternalIssueReceipt: ...

    def update_issue_state(self, issue_id: str, *, state: str) -> ExternalIssueReceipt: ...

    def create_comment(self, issue_id: str, *, body: str) -> ExternalCommentReceipt: ...


class GitHubIssueProviderAdapter:
    provider = "github"

    def __init__(
        self,
        *,
        api_url: str,
        web_url: str,
        owner: str,
        repo: str,
        token: str,
        api_version: str,
        timeout_seconds: int,
    ) -> None:
        self._api_url = api_url.rstrip("/") + "/"
        self._web_url = web_url.rstrip("/") + "/"
        self._owner = owner
        self._repo = repo
        self._token = token
        self._api_version = api_version
        self._timeout_seconds = timeout_seconds

    def create_issue(self, *, title: str, body: str) -> ExternalIssueReceipt:
        payload, response_hash = self._request_json(
            "POST",
            f"repos/{self._owner}/{self._repo}/issues",
            {"title": title, "body": body},
            expected_status=201,
            ambiguous_on_transport=True,
        )
        return self._issue_receipt(payload, response_hash=response_hash)

    def update_issue_state(self, issue_id: str, *, state: str) -> ExternalIssueReceipt:
        issue_number = _positive_issue_number(issue_id)
        payload, response_hash = self._request_json(
            "PATCH",
            f"repos/{self._owner}/{self._repo}/issues/{issue_number}",
            {"state": state},
            expected_status=200,
            ambiguous_on_transport=False,
        )
        return self._issue_receipt(payload, response_hash=response_hash)

    def create_comment(self, issue_id: str, *, body: str) -> ExternalCommentReceipt:
        issue_number = _positive_issue_number(issue_id)
        payload, response_hash = self._request_json(
            "POST",
            f"repos/{self._owner}/{self._repo}/issues/{issue_number}/comments",
            {"body": body},
            expected_status=201,
            ambiguous_on_transport=True,
        )
        try:
            comment_id = str(int(payload["id"]))
            comment_url = str(payload["html_url"])
        except (KeyError, TypeError, ValueError):
            raise IssueProviderError("provider_invalid_comment_response", retryable=False, ambiguous=True) from None
        if not _safe_repository_issue_url(
            comment_url,
            base_url=self._web_url,
            owner=self._owner,
            repo=self._repo,
            issue_id=str(issue_number),
            allow_comment_fragment=True,
        ):
            raise IssueProviderError("provider_invalid_comment_response", retryable=False, ambiguous=True)
        return ExternalCommentReceipt(
            provider=self.provider,
            comment_id=comment_id,
            comment_url=comment_url,
            response_hash=response_hash,
        )

    def _request_json(
        self,
        method: str,
        path: str,
        payload: dict[str, Any],
        *,
        expected_status: int,
        ambiguous_on_transport: bool,
    ) -> tuple[dict[str, Any], str]:
        body = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        request = urllib_request.Request(
            urljoin(self._api_url, path),
            data=body,
            method=method,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {self._token}",
                "Content-Type": "application/json; charset=utf-8",
                "User-Agent": "Astra-External-Issue-Sync/1",
                "X-GitHub-Api-Version": self._api_version,
            },
        )
        try:
            with _open_github_request(
                request,
                timeout=self._timeout_seconds,
                allowed_origin=self._api_url,
            ) as response:
                response_status = getattr(response, "status", None)
                status_code = int(response_status if response_status is not None else response.getcode())
                response_body = response.read(64 * 1024)
        except urllib_error.HTTPError as exc:
            code = int(exc.code)
            retryable = code == 429 or code >= 500 or _github_rate_limited(exc.headers)
            raise IssueProviderError(
                _http_error_code(code),
                retryable=retryable,
                ambiguous=ambiguous_on_transport and code >= 500,
            ) from None
        except (TimeoutError, urllib_error.URLError):
            raise IssueProviderError(
                "provider_network_error",
                retryable=True,
                ambiguous=ambiguous_on_transport,
            ) from None
        except Exception:
            raise IssueProviderError(
                "provider_unexpected_error",
                retryable=True,
                ambiguous=ambiguous_on_transport,
            ) from None
        if status_code != expected_status:
            raise IssueProviderError(
                _http_error_code(status_code),
                retryable=status_code == 429 or status_code >= 500,
                ambiguous=ambiguous_on_transport and status_code >= 500,
            )
        try:
            decoded = json.loads(response_body)
        except json.JSONDecodeError:
            raise IssueProviderError("provider_invalid_json_response", retryable=False, ambiguous=True) from None
        if not isinstance(decoded, dict):
            raise IssueProviderError("provider_invalid_json_response", retryable=False, ambiguous=True)
        response_hash = sha256(f"{status_code}:".encode("ascii") + response_body).hexdigest()
        return decoded, response_hash

    def _issue_receipt(self, payload: dict[str, Any], *, response_hash: str) -> ExternalIssueReceipt:
        try:
            issue_id = str(int(payload["number"]))
            issue_url = str(payload["html_url"])
            state = str(payload["state"]).strip().lower()
            updated_at = _optional_datetime(payload.get("updated_at"))
        except (KeyError, TypeError, ValueError):
            raise IssueProviderError("provider_invalid_issue_response", retryable=False, ambiguous=True) from None
        if state not in {"open", "closed"} or not _safe_repository_issue_url(
            issue_url,
            base_url=self._web_url,
            owner=self._owner,
            repo=self._repo,
            issue_id=issue_id,
        ):
            raise IssueProviderError("provider_invalid_issue_response", retryable=False, ambiguous=True)
        return ExternalIssueReceipt(
            provider=self.provider,
            issue_id=issue_id,
            issue_url=issue_url,
            state=state,
            updated_at=updated_at,
            response_hash=response_hash,
        )


class _SameOriginRedirectHandler(urllib_request.HTTPRedirectHandler):
    def __init__(self, allowed_origin: str) -> None:
        super().__init__()
        parsed = urlparse(allowed_origin)
        self._scheme = parsed.scheme.lower()
        self._netloc = parsed.netloc.lower()

    def redirect_request(self, request, file_pointer, code, message, headers, new_url):
        parsed = urlparse(new_url)
        if (
            code not in {307, 308}
            or parsed.scheme.lower() != self._scheme
            or parsed.netloc.lower() != self._netloc
        ):
            return None
        return super().redirect_request(request, file_pointer, code, message, headers, new_url)


def _open_github_request(request: urllib_request.Request, *, timeout: int, allowed_origin: str):
    return urllib_request.build_opener(_SameOriginRedirectHandler(allowed_origin)).open(request, timeout=timeout)


def external_issue_sync_posture(settings: Settings) -> dict[str, Any]:
    api_url = urlparse(settings.external_issue_sync_github_api_url.strip())
    web_url = urlparse(settings.external_issue_sync_github_web_url.strip())
    owner = (settings.external_issue_sync_github_owner or "").strip()
    repo = (settings.external_issue_sync_github_repo or "").strip()
    token = settings.external_issue_sync_github_token
    configured = bool(
        settings.external_issue_sync_provider == "github"
        and api_url.scheme == "https"
        and api_url.netloc
        and web_url.scheme == "https"
        and web_url.netloc
        and _REPOSITORY_PART_PATTERN.fullmatch(owner)
        and _REPOSITORY_PART_PATTERN.fullmatch(repo)
        and token is not None
        and token.get_secret_value().strip()
        and _API_VERSION_PATTERN.fullmatch(settings.external_issue_sync_github_api_version.strip())
    )
    return {
        "enabled": settings.external_issue_sync_enabled,
        "provider": settings.external_issue_sync_provider,
        "configured": configured,
        "transport": "github_rest_https",
        "api_version": settings.external_issue_sync_github_api_version,
        "credentials_source": "environment_or_secure_settings",
        "timeout_seconds": settings.external_issue_sync_timeout_seconds,
        "local_authority": True,
        "automatic_inbound_sync": False,
        "create_and_comment_ambiguous_retry": False,
        "sensitive_fields_sent": False,
    }


def build_issue_provider_adapter(settings: Settings) -> IssueProviderAdapter:
    posture = external_issue_sync_posture(settings)
    if not posture["enabled"]:
        raise IssueProviderError("external_issue_sync_disabled", retryable=False)
    if not posture["configured"]:
        raise IssueProviderError("external_issue_sync_not_configured", retryable=False)
    token = settings.external_issue_sync_github_token
    assert token is not None
    return GitHubIssueProviderAdapter(
        api_url=settings.external_issue_sync_github_api_url.strip(),
        web_url=settings.external_issue_sync_github_web_url.strip(),
        owner=(settings.external_issue_sync_github_owner or "").strip(),
        repo=(settings.external_issue_sync_github_repo or "").strip(),
        token=token.get_secret_value().strip(),
        api_version=settings.external_issue_sync_github_api_version.strip(),
        timeout_seconds=settings.external_issue_sync_timeout_seconds,
    )


def external_issue_create_content(bug: BugRecord, *, operation_key: str) -> tuple[str, str]:
    if external_sync_text_contains_sensitive_marker(bug.title) or external_sync_text_contains_sensitive_marker(
        bug.category
    ):
        raise IssueProviderError("external_issue_title_sensitive", retryable=False)
    title = f"[{bug.severity}] {bug.title}"[:256]
    body = "\n".join(
        (
            f"Synced from Astra BugRecord #{bug.id}.",
            "",
            f"- Category: {bug.category}",
            f"- Severity: {bug.severity}",
            f"- Local status: {bug.status}",
            "- Authority: Astra local BugRecord",
            "",
            f"<!-- astra-external-issue-sync:{sha256(operation_key.encode('utf-8')).hexdigest()} -->",
        )
    )
    return title, body


def external_issue_comment_content(comment: str, *, operation_key: str) -> str:
    normalized = comment.strip()
    if not normalized:
        raise IssueProviderError("external_issue_comment_empty", retryable=False)
    if external_sync_text_contains_sensitive_marker(normalized):
        raise IssueProviderError("external_issue_comment_sensitive", retryable=False)
    marker = sha256(operation_key.encode("utf-8")).hexdigest()
    return f"{normalized}\n\n<!-- astra-external-issue-comment:{marker} -->"


def validate_external_issue_binding(settings: Settings, bug: BugRecord) -> str:
    provider = settings.external_issue_sync_provider
    if bug.external_issue_provider != provider:
        raise IssueProviderError("external_issue_provider_mismatch", retryable=False)
    if not bug.external_issue_id or not bug.external_issue_url:
        raise IssueProviderError("external_issue_not_bound", retryable=False)
    issue_number = _positive_issue_number(bug.external_issue_id)
    if provider == "github" and not _safe_repository_issue_url(
        bug.external_issue_url,
        base_url=settings.external_issue_sync_github_web_url,
        owner=(settings.external_issue_sync_github_owner or "").strip(),
        repo=(settings.external_issue_sync_github_repo or "").strip(),
        issue_id=str(issue_number),
    ):
        raise IssueProviderError("external_issue_binding_invalid", retryable=False)
    return str(issue_number)


def external_sync_text_contains_sensitive_marker(value: str) -> bool:
    lowered = value.lower()
    return any(marker in lowered for marker in _SENSITIVE_TEXT_MARKERS)


def _positive_issue_number(value: str) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise IssueProviderError("external_issue_id_invalid", retryable=False) from None
    if number < 1:
        raise IssueProviderError("external_issue_id_invalid", retryable=False)
    return number


def _safe_external_url(value: str, *, base_url: str) -> bool:
    parsed = urlparse(value)
    expected = urlparse(base_url)
    return bool(
        parsed.scheme == "https"
        and parsed.netloc.lower() == expected.netloc.lower()
        and not parsed.username
        and not parsed.password
    )


def _safe_repository_issue_url(
    value: str,
    *,
    base_url: str,
    owner: str,
    repo: str,
    issue_id: str,
    allow_comment_fragment: bool = False,
) -> bool:
    if not _safe_external_url(value, base_url=base_url):
        return False
    parsed = urlparse(value)
    expected_path = f"/{owner}/{repo}/issues/{issue_id}".lower()
    if parsed.query or parsed.path.rstrip("/").lower() != expected_path:
        return False
    if allow_comment_fragment:
        return bool(re.fullmatch(r"issuecomment-\d+", parsed.fragment))
    return not parsed.fragment


def _optional_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _github_rate_limited(headers: Any) -> bool:
    if headers is None:
        return False
    return bool(headers.get("retry-after") or str(headers.get("x-ratelimit-remaining") or "") == "0")


def _http_error_code(status_code: int) -> str:
    if status_code == 429:
        return "provider_rate_limited"
    if status_code >= 500:
        return "provider_http_5xx"
    if status_code >= 400:
        return "provider_http_4xx"
    return "provider_unexpected_status"
