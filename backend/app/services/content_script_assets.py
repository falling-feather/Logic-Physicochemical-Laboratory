from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any
from urllib.parse import urlsplit

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ContentPageRecord, ContentPageVersion, ContentScriptAsset, User
from app.schemas.content import ContentPage
from app.services import content_script_policy
from app.services.content_script_policy import collect_content_script_manifests


class ContentScriptAssetMirrorError(ValueError):
    pass


@dataclass(frozen=True)
class ExternalScriptReference:
    sandbox_id: str
    reference_key: str
    reference_value_sha256: str
    source_url: str
    source_host: str
    integrity: str
    crossorigin: str


@dataclass(frozen=True)
class ContentScriptAssetMirrorAuditIssue:
    code: str
    severity: str
    message: str
    page_id: int | None
    page_version_id: int | None
    slug: str
    sandbox_id: str | None = None
    reference_key: str | None = None
    reference_value_sha256: str | None = None
    source_host: str | None = None
    source_url_sha256: str | None = None
    asset_id: int | None = None
    asset_sha256: str | None = None
    published_at: datetime | None = None


@dataclass(frozen=True)
class ContentScriptAssetMirrorAuditReport:
    generated_at: datetime
    total_pages_scanned: int
    total_external_references: int
    total_issues: int
    issue_counts_by_code: dict[str, int]
    issue_counts_by_severity: dict[str, int]
    issues: list[ContentScriptAssetMirrorAuditIssue]


@dataclass(frozen=True)
class ContentScriptAssetRemoteDriftIssue:
    code: str
    severity: str
    message: str
    page_id: int | None
    page_version_id: int | None
    slug: str
    sandbox_id: str | None = None
    reference_key: str | None = None
    reference_value_sha256: str | None = None
    source_host: str | None = None
    source_url_sha256: str | None = None
    asset_id: int | None = None
    asset_sha256: str | None = None
    remote_asset_sha256: str | None = None
    remote_asset_size_bytes: int | None = None
    published_at: datetime | None = None


@dataclass(frozen=True)
class ContentScriptAssetRemoteDriftReport:
    generated_at: datetime
    total_pages_scanned: int
    total_external_references: int
    total_scanned_references: int
    total_remote_fetches: int
    total_skipped_references: int
    total_issues: int
    issue_counts_by_code: dict[str, int]
    issue_counts_by_severity: dict[str, int]
    issues: list[ContentScriptAssetRemoteDriftIssue]


def mirror_external_script_assets_for_version(
    db: Session,
    *,
    page: ContentPageRecord,
    version: ContentPageVersion,
    page_schema: ContentPage,
    publisher: User,
    policy_version: str,
    policy_context_hash: str,
) -> list[ContentScriptAsset]:
    mirrored: list[ContentScriptAsset] = []
    seen: set[tuple[str, str]] = set()
    for reference in external_script_references(page_schema):
        reference_key = (reference.sandbox_id, reference.reference_value_sha256)
        if reference_key in seen:
            continue
        seen.add(reference_key)
        asset_bytes = _fetch_external_script_asset(reference.source_url)
        metadata = content_script_policy.external_script_asset_verification_metadata(reference.integrity, asset_bytes)
        matched_algorithm = metadata.get("matched_algorithm")
        if not isinstance(matched_algorithm, str):
            raise ContentScriptAssetMirrorError("External script asset bytes do not match the declared SRI hash")
        asset = db.scalar(
            select(ContentScriptAsset).where(
                ContentScriptAsset.page_version_id == version.id,
                ContentScriptAsset.sandbox_id == reference.sandbox_id,
                ContentScriptAsset.reference_value_sha256 == reference.reference_value_sha256,
            )
        )
        if asset is None:
            asset = ContentScriptAsset(
                page_id=page.id,
                page_version_id=version.id,
                slug=page.slug,
                sandbox_id=reference.sandbox_id,
                reference_key=reference.reference_key,
                reference_value_sha256=reference.reference_value_sha256,
                source_url=reference.source_url,
                source_host=reference.source_host,
                integrity=reference.integrity,
                matched_algorithm=matched_algorithm,
                asset_sha256=str(metadata["asset_sha256"]),
                asset_size_bytes=int(metadata["asset_size_bytes"]),
                content_bytes=asset_bytes,
                policy_version=policy_version,
                policy_context_hash=policy_context_hash,
                published_by_user_id=publisher.id,
                published_at=version.published_at,
            )
            db.add(asset)
        else:
            asset.page_id = page.id
            asset.slug = page.slug
            asset.reference_key = reference.reference_key
            asset.source_url = reference.source_url
            asset.source_host = reference.source_host
            asset.integrity = reference.integrity
            asset.matched_algorithm = matched_algorithm
            asset.asset_sha256 = str(metadata["asset_sha256"])
            asset.asset_size_bytes = int(metadata["asset_size_bytes"])
            asset.content_bytes = asset_bytes
            asset.policy_version = policy_version
            asset.policy_context_hash = policy_context_hash
            asset.published_by_user_id = publisher.id
            asset.published_at = version.published_at
        mirrored.append(asset)
    return mirrored


def audit_current_content_script_asset_mirrors(
    db: Session,
    *,
    slug: str | None = None,
    source_host: str | None = None,
    issue_code: str | None = None,
    severity: str | None = None,
    generated_at: datetime | None = None,
) -> ContentScriptAssetMirrorAuditReport:
    normalized_slug = slug.strip("/") if slug is not None and slug.strip("/") else None
    normalized_host = source_host.strip().lower() if source_host is not None and source_host.strip() else None
    normalized_issue_code = issue_code.strip().lower() if issue_code is not None and issue_code.strip() else None
    normalized_severity = severity.strip().lower() if severity is not None and severity.strip() else None

    statement = select(ContentPageRecord).where(ContentPageRecord.status == "published").order_by(ContentPageRecord.slug)
    if normalized_slug is not None:
        statement = statement.where(ContentPageRecord.slug == normalized_slug)

    pages = list(db.scalars(statement).all())
    issues: list[ContentScriptAssetMirrorAuditIssue] = []
    total_external_references = 0
    for page in pages:
        if page.current_version_id is None:
            if normalized_host is None:
                _append_content_script_asset_audit_issue(
                    issues,
                    ContentScriptAssetMirrorAuditIssue(
                        code="missing_current_version",
                        severity="critical",
                        message="Published content page has no current version pointer.",
                        page_id=page.id,
                        page_version_id=None,
                        slug=page.slug,
                        published_at=page.published_at,
                    ),
                    issue_code=normalized_issue_code,
                    severity=normalized_severity,
                )
            continue

        version = db.get(ContentPageVersion, page.current_version_id)
        if version is None:
            if normalized_host is None:
                _append_content_script_asset_audit_issue(
                    issues,
                    ContentScriptAssetMirrorAuditIssue(
                        code="missing_current_version",
                        severity="critical",
                        message="Published content page points to a missing current version.",
                        page_id=page.id,
                        page_version_id=page.current_version_id,
                        slug=page.slug,
                        published_at=page.published_at,
                    ),
                    issue_code=normalized_issue_code,
                    severity=normalized_severity,
                )
            continue

        try:
            references = external_script_references(version.schema_json)
        except ContentScriptAssetMirrorError as exc:
            if normalized_host is None:
                _append_content_script_asset_audit_issue(
                    issues,
                    ContentScriptAssetMirrorAuditIssue(
                        code="invalid_external_reference",
                        severity="critical",
                        message=str(exc),
                        page_id=page.id,
                        page_version_id=version.id,
                        slug=page.slug,
                        published_at=version.published_at,
                    ),
                    issue_code=normalized_issue_code,
                    severity=normalized_severity,
                )
            continue

        seen_references: set[tuple[str, str]] = set()
        for reference in references:
            if normalized_host is not None and reference.source_host != normalized_host:
                continue
            total_external_references += 1
            reference_key = (reference.sandbox_id, reference.reference_value_sha256)
            if reference_key in seen_references:
                _append_content_script_asset_audit_issue(
                    issues,
                    _content_script_asset_audit_issue(
                        code="duplicate_reference",
                        severity="warning",
                        message="Published schema repeats the same sandbox/reference hash pair.",
                        page=page,
                        version=version,
                        reference=reference,
                    ),
                    issue_code=normalized_issue_code,
                    severity=normalized_severity,
                )
                continue
            seen_references.add(reference_key)
            asset = get_bound_content_script_asset(
                db,
                page_version_id=version.id,
                sandbox_id=reference.sandbox_id,
                reference_value_sha256=reference.reference_value_sha256,
            )
            if asset is None:
                _append_content_script_asset_audit_issue(
                    issues,
                    _content_script_asset_audit_issue(
                        code="missing_mirror",
                        severity="critical",
                        message="External script reference has no version-bound mirrored asset.",
                        page=page,
                        version=version,
                        reference=reference,
                    ),
                    issue_code=normalized_issue_code,
                    severity=normalized_severity,
                )
                continue
            _audit_bound_content_script_asset(
                issues,
                page=page,
                version=version,
                reference=reference,
                asset=asset,
                issue_code=normalized_issue_code,
                severity=normalized_severity,
            )

    return ContentScriptAssetMirrorAuditReport(
        generated_at=generated_at or datetime.now(UTC),
        total_pages_scanned=len(pages),
        total_external_references=total_external_references,
        total_issues=len(issues),
        issue_counts_by_code=_issue_counts(issues, "code"),
        issue_counts_by_severity=_issue_counts(issues, "severity"),
        issues=issues,
    )


def scan_current_content_script_asset_remote_drift(
    db: Session,
    *,
    slug: str | None = None,
    source_host: str | None = None,
    issue_code: str | None = None,
    severity: str | None = None,
    scan_limit: int = 25,
    scan_offset: int = 0,
    generated_at: datetime | None = None,
    external_script_fetcher: Callable[[str], bytes] | None = None,
) -> ContentScriptAssetRemoteDriftReport:
    normalized_slug = slug.strip("/") if slug is not None and slug.strip("/") else None
    normalized_host = source_host.strip().lower() if source_host is not None and source_host.strip() else None
    normalized_issue_code = issue_code.strip().lower() if issue_code is not None and issue_code.strip() else None
    normalized_severity = severity.strip().lower() if severity is not None and severity.strip() else None
    fetcher = external_script_fetcher or _fetch_external_script_asset

    statement = select(ContentPageRecord).where(ContentPageRecord.status == "published").order_by(ContentPageRecord.slug)
    if normalized_slug is not None:
        statement = statement.where(ContentPageRecord.slug == normalized_slug)

    pages = list(db.scalars(statement).all())
    issues: list[ContentScriptAssetRemoteDriftIssue] = []
    total_external_references = 0
    total_scanned_references = 0
    total_remote_fetches = 0
    total_skipped_references = 0
    for page in pages:
        if page.current_version_id is None:
            if normalized_host is None:
                _append_remote_drift_issue(
                    issues,
                    ContentScriptAssetRemoteDriftIssue(
                        code="missing_current_version",
                        severity="critical",
                        message="Published content page has no current version pointer.",
                        page_id=page.id,
                        page_version_id=None,
                        slug=page.slug,
                        published_at=page.published_at,
                    ),
                    issue_code=normalized_issue_code,
                    severity=normalized_severity,
                )
            continue

        version = db.get(ContentPageVersion, page.current_version_id)
        if version is None:
            if normalized_host is None:
                _append_remote_drift_issue(
                    issues,
                    ContentScriptAssetRemoteDriftIssue(
                        code="missing_current_version",
                        severity="critical",
                        message="Published content page points to a missing current version.",
                        page_id=page.id,
                        page_version_id=page.current_version_id,
                        slug=page.slug,
                        published_at=page.published_at,
                    ),
                    issue_code=normalized_issue_code,
                    severity=normalized_severity,
                )
            continue

        try:
            references = external_script_references(version.schema_json)
        except ContentScriptAssetMirrorError as exc:
            if normalized_host is None:
                _append_remote_drift_issue(
                    issues,
                    ContentScriptAssetRemoteDriftIssue(
                        code="invalid_external_reference",
                        severity="critical",
                        message=str(exc),
                        page_id=page.id,
                        page_version_id=version.id,
                        slug=page.slug,
                        published_at=version.published_at,
                    ),
                    issue_code=normalized_issue_code,
                    severity=normalized_severity,
                )
            continue

        seen_references: set[tuple[str, str]] = set()
        for reference in references:
            if normalized_host is not None and reference.source_host != normalized_host:
                continue
            total_external_references += 1
            reference_index = total_external_references - 1
            if reference_index < scan_offset:
                continue
            if total_scanned_references >= scan_limit:
                continue
            total_scanned_references += 1
            reference_key = (reference.sandbox_id, reference.reference_value_sha256)
            if reference_key in seen_references:
                total_skipped_references += 1
                _append_remote_drift_issue(
                    issues,
                    _remote_drift_issue(
                        code="duplicate_reference",
                        severity="warning",
                        message="Published schema repeats the same sandbox/reference hash pair.",
                        page=page,
                        version=version,
                        reference=reference,
                    ),
                    issue_code=normalized_issue_code,
                    severity=normalized_severity,
                )
                continue
            seen_references.add(reference_key)
            asset = get_bound_content_script_asset(
                db,
                page_version_id=version.id,
                sandbox_id=reference.sandbox_id,
                reference_value_sha256=reference.reference_value_sha256,
            )
            if asset is None:
                total_skipped_references += 1
                _append_remote_drift_issue(
                    issues,
                    _remote_drift_issue(
                        code="missing_mirror",
                        severity="critical",
                        message="External script reference has no version-bound mirrored asset to compare with remote bytes.",
                        page=page,
                        version=version,
                        reference=reference,
                    ),
                    issue_code=normalized_issue_code,
                    severity=normalized_severity,
                )
                continue
            _scan_bound_content_script_asset_remote_drift(
                issues,
                page=page,
                version=version,
                reference=reference,
                asset=asset,
                fetcher=fetcher,
                issue_code=normalized_issue_code,
                severity=normalized_severity,
            )
            total_remote_fetches += 1

    return ContentScriptAssetRemoteDriftReport(
        generated_at=generated_at or datetime.now(UTC),
        total_pages_scanned=len(pages),
        total_external_references=total_external_references,
        total_scanned_references=total_scanned_references,
        total_remote_fetches=total_remote_fetches,
        total_skipped_references=total_skipped_references,
        total_issues=len(issues),
        issue_counts_by_code=_issue_counts(issues, "code"),
        issue_counts_by_severity=_issue_counts(issues, "severity"),
        issues=issues,
    )


def external_script_references(page_schema: ContentPage | dict[str, Any]) -> list[ExternalScriptReference]:
    references: list[ExternalScriptReference] = []
    for manifest in collect_content_script_manifests(page_schema, include_private_values=True):
        sandbox_id = manifest.get("sandboxId")
        manifest_references = manifest.get("references")
        if not isinstance(sandbox_id, str) or not isinstance(manifest_references, list):
            continue
        for reference in manifest_references:
            if not isinstance(reference, dict):
                continue
            source_url = _reference_source_url(reference)
            if source_url is None:
                continue
            value_sha256 = reference.get("valueSha256")
            integrity = reference.get("integrity")
            crossorigin = reference.get("crossorigin")
            if not isinstance(value_sha256, str) or len(value_sha256) != 64:
                raise ContentScriptAssetMirrorError("External script reference hash is missing")
            if not isinstance(integrity, str) or not integrity.strip():
                raise ContentScriptAssetMirrorError("External script integrity metadata is missing")
            if not isinstance(crossorigin, str) or crossorigin.strip().lower() != "anonymous":
                raise ContentScriptAssetMirrorError("External script crossorigin metadata is missing")
            parsed = urlsplit(source_url)
            if parsed.scheme != "https" or not parsed.hostname or parsed.query or parsed.fragment:
                raise ContentScriptAssetMirrorError("External script source URL is not mirrorable")
            references.append(
                ExternalScriptReference(
                    sandbox_id=sandbox_id,
                    reference_key=str(reference.get("key", "")),
                    reference_value_sha256=value_sha256.lower(),
                    source_url=source_url,
                    source_host=parsed.hostname.lower(),
                    integrity=integrity.strip(),
                    crossorigin=crossorigin.strip().lower(),
                )
            )
    return references


def get_bound_content_script_asset(
    db: Session,
    *,
    page_version_id: int,
    sandbox_id: str,
    reference_value_sha256: str,
) -> ContentScriptAsset | None:
    return db.scalar(
        select(ContentScriptAsset).where(
            ContentScriptAsset.page_version_id == page_version_id,
            ContentScriptAsset.sandbox_id == sandbox_id,
            ContentScriptAsset.reference_value_sha256 == reference_value_sha256.lower(),
        )
    )


def _reference_source_url(reference: dict[str, Any]) -> str | None:
    value = reference.get("value")
    if not isinstance(value, str):
        return None
    source = value.strip()
    lowered = source.lower()
    if lowered.startswith("https://") or lowered.startswith("http://") or lowered.startswith("//"):
        return source
    return None


def _audit_bound_content_script_asset(
    issues: list[ContentScriptAssetMirrorAuditIssue],
    *,
    page: ContentPageRecord,
    version: ContentPageVersion,
    reference: ExternalScriptReference,
    asset: ContentScriptAsset,
    issue_code: str | None,
    severity: str | None,
) -> None:
    if asset.page_id != page.id or asset.slug != page.slug:
        _append_content_script_asset_audit_issue(
            issues,
            _content_script_asset_audit_issue(
                code="stale_binding",
                severity="critical",
                message="Mirrored asset no longer matches the published page binding.",
                page=page,
                version=version,
                reference=reference,
                asset=asset,
            ),
            issue_code=issue_code,
            severity=severity,
        )
    if asset.source_url != reference.source_url or asset.source_host != reference.source_host:
        _append_content_script_asset_audit_issue(
            issues,
            _content_script_asset_audit_issue(
                code="source_mismatch",
                severity="critical",
                message="Mirrored asset source metadata differs from the published schema reference.",
                page=page,
                version=version,
                reference=reference,
                asset=asset,
            ),
            issue_code=issue_code,
            severity=severity,
        )
    if asset.integrity != reference.integrity:
        _append_content_script_asset_audit_issue(
            issues,
            _content_script_asset_audit_issue(
                code="integrity_mismatch",
                severity="critical",
                message="Mirrored asset integrity metadata differs from the published schema reference.",
                page=page,
                version=version,
                reference=reference,
                asset=asset,
            ),
            issue_code=issue_code,
            severity=severity,
        )

    try:
        metadata = content_script_policy.external_script_asset_verification_metadata(
            reference.integrity,
            asset.content_bytes,
        )
    except Exception:
        _append_content_script_asset_audit_issue(
            issues,
            _content_script_asset_audit_issue(
                code="invalid_integrity_metadata",
                severity="critical",
                message="Published SRI metadata cannot be parsed for local mirror verification.",
                page=page,
                version=version,
                reference=reference,
                asset=asset,
            ),
            issue_code=issue_code,
            severity=severity,
        )
        return
    computed_sha256 = str(metadata["asset_sha256"])
    computed_size = int(metadata["asset_size_bytes"])
    matched_algorithm = metadata.get("matched_algorithm")
    if computed_sha256 != asset.asset_sha256:
        _append_content_script_asset_audit_issue(
            issues,
            _content_script_asset_audit_issue(
                code="asset_hash_mismatch",
                severity="critical",
                message="Mirrored asset bytes do not match the stored SHA-256 fingerprint.",
                page=page,
                version=version,
                reference=reference,
                asset=asset,
            ),
            issue_code=issue_code,
            severity=severity,
        )
    if computed_size != asset.asset_size_bytes:
        _append_content_script_asset_audit_issue(
            issues,
            _content_script_asset_audit_issue(
                code="asset_size_mismatch",
                severity="critical",
                message="Mirrored asset bytes do not match the stored byte size.",
                page=page,
                version=version,
                reference=reference,
                asset=asset,
            ),
            issue_code=issue_code,
            severity=severity,
        )
    if not isinstance(matched_algorithm, str):
        _append_content_script_asset_audit_issue(
            issues,
            _content_script_asset_audit_issue(
                code="sri_mismatch",
                severity="critical",
                message="Mirrored asset bytes do not satisfy the published SRI metadata.",
                page=page,
                version=version,
                reference=reference,
                asset=asset,
            ),
            issue_code=issue_code,
            severity=severity,
        )
    elif matched_algorithm != asset.matched_algorithm:
        _append_content_script_asset_audit_issue(
            issues,
            _content_script_asset_audit_issue(
                code="matched_algorithm_mismatch",
                severity="warning",
                message="Mirrored asset matched SRI with a different algorithm than the stored metadata.",
                page=page,
                version=version,
                reference=reference,
                asset=asset,
            ),
            issue_code=issue_code,
            severity=severity,
        )


def _content_script_asset_audit_issue(
    *,
    code: str,
    severity: str,
    message: str,
    page: ContentPageRecord,
    version: ContentPageVersion,
    reference: ExternalScriptReference,
    asset: ContentScriptAsset | None = None,
) -> ContentScriptAssetMirrorAuditIssue:
    return ContentScriptAssetMirrorAuditIssue(
        code=code,
        severity=severity,
        message=message,
        page_id=page.id,
        page_version_id=version.id,
        slug=page.slug,
        sandbox_id=reference.sandbox_id,
        reference_key=reference.reference_key,
        reference_value_sha256=reference.reference_value_sha256,
        source_host=reference.source_host,
        source_url_sha256=sha256(reference.source_url.encode("utf-8")).hexdigest(),
        asset_id=asset.id if asset is not None else None,
        asset_sha256=asset.asset_sha256 if asset is not None else None,
        published_at=version.published_at,
    )


def _append_content_script_asset_audit_issue(
    issues: list[ContentScriptAssetMirrorAuditIssue],
    issue: ContentScriptAssetMirrorAuditIssue,
    *,
    issue_code: str | None,
    severity: str | None,
) -> None:
    if issue_code is not None and issue.code != issue_code:
        return
    if severity is not None and issue.severity != severity:
        return
    issues.append(issue)


def _issue_counts(issues: list[ContentScriptAssetMirrorAuditIssue], field: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for issue in issues:
        key = getattr(issue, field)
        counts[key] = counts.get(key, 0) + 1
    return counts


def _scan_bound_content_script_asset_remote_drift(
    issues: list[ContentScriptAssetRemoteDriftIssue],
    *,
    page: ContentPageRecord,
    version: ContentPageVersion,
    reference: ExternalScriptReference,
    asset: ContentScriptAsset,
    fetcher: Callable[[str], bytes],
    issue_code: str | None,
    severity: str | None,
) -> None:
    if asset.page_id != page.id or asset.slug != page.slug:
        _append_remote_drift_issue(
            issues,
            _remote_drift_issue(
                code="stale_binding",
                severity="critical",
                message="Mirrored asset no longer matches the published page binding.",
                page=page,
                version=version,
                reference=reference,
                asset=asset,
            ),
            issue_code=issue_code,
            severity=severity,
        )
    if asset.source_url != reference.source_url or asset.source_host != reference.source_host:
        _append_remote_drift_issue(
            issues,
            _remote_drift_issue(
                code="source_mismatch",
                severity="critical",
                message="Mirrored asset source metadata differs from the published schema reference.",
                page=page,
                version=version,
                reference=reference,
                asset=asset,
            ),
            issue_code=issue_code,
            severity=severity,
        )
    if asset.integrity != reference.integrity:
        _append_remote_drift_issue(
            issues,
            _remote_drift_issue(
                code="integrity_mismatch",
                severity="critical",
                message="Mirrored asset integrity metadata differs from the published schema reference.",
                page=page,
                version=version,
                reference=reference,
                asset=asset,
            ),
            issue_code=issue_code,
            severity=severity,
        )

    try:
        remote_bytes = fetcher(reference.source_url)
    except Exception:
        _append_remote_drift_issue(
            issues,
            _remote_drift_issue(
                code="remote_asset_unavailable",
                severity="critical",
                message="Remote external script asset could not be downloaded for drift scanning.",
                page=page,
                version=version,
                reference=reference,
                asset=asset,
            ),
            issue_code=issue_code,
            severity=severity,
        )
        return
    if len(remote_bytes) > content_script_policy.MAX_EXTERNAL_SCRIPT_BYTES:
        _append_remote_drift_issue(
            issues,
            _remote_drift_issue(
                code="remote_asset_too_large",
                severity="critical",
                message="Remote external script asset exceeds the maximum drift scan size.",
                page=page,
                version=version,
                reference=reference,
                asset=asset,
                remote_asset_size_bytes=len(remote_bytes),
            ),
            issue_code=issue_code,
            severity=severity,
        )
        return
    try:
        metadata = content_script_policy.external_script_asset_verification_metadata(reference.integrity, remote_bytes)
    except Exception:
        _append_remote_drift_issue(
            issues,
            _remote_drift_issue(
                code="invalid_integrity_metadata",
                severity="critical",
                message="Published SRI metadata cannot be parsed for remote drift scanning.",
                page=page,
                version=version,
                reference=reference,
                asset=asset,
            ),
            issue_code=issue_code,
            severity=severity,
        )
        return

    remote_sha256 = str(metadata["asset_sha256"])
    remote_size = int(metadata["asset_size_bytes"])
    matched_algorithm = metadata.get("matched_algorithm")
    if remote_sha256 != asset.asset_sha256:
        _append_remote_drift_issue(
            issues,
            _remote_drift_issue(
                code="remote_hash_mismatch",
                severity="critical",
                message="Remote external script bytes no longer match the mirrored SHA-256 fingerprint.",
                page=page,
                version=version,
                reference=reference,
                asset=asset,
                remote_asset_sha256=remote_sha256,
                remote_asset_size_bytes=remote_size,
            ),
            issue_code=issue_code,
            severity=severity,
        )
    if remote_size != asset.asset_size_bytes:
        _append_remote_drift_issue(
            issues,
            _remote_drift_issue(
                code="remote_size_mismatch",
                severity="critical",
                message="Remote external script bytes no longer match the mirrored byte size.",
                page=page,
                version=version,
                reference=reference,
                asset=asset,
                remote_asset_sha256=remote_sha256,
                remote_asset_size_bytes=remote_size,
            ),
            issue_code=issue_code,
            severity=severity,
        )
    if not isinstance(matched_algorithm, str):
        _append_remote_drift_issue(
            issues,
            _remote_drift_issue(
                code="remote_sri_mismatch",
                severity="critical",
                message="Remote external script bytes no longer satisfy the published SRI metadata.",
                page=page,
                version=version,
                reference=reference,
                asset=asset,
                remote_asset_sha256=remote_sha256,
                remote_asset_size_bytes=remote_size,
            ),
            issue_code=issue_code,
            severity=severity,
        )
    elif matched_algorithm != asset.matched_algorithm:
        _append_remote_drift_issue(
            issues,
            _remote_drift_issue(
                code="remote_matched_algorithm_mismatch",
                severity="warning",
                message="Remote external script matched SRI with a different algorithm than the mirrored metadata.",
                page=page,
                version=version,
                reference=reference,
                asset=asset,
                remote_asset_sha256=remote_sha256,
                remote_asset_size_bytes=remote_size,
            ),
            issue_code=issue_code,
            severity=severity,
        )


def _remote_drift_issue(
    *,
    code: str,
    severity: str,
    message: str,
    page: ContentPageRecord,
    version: ContentPageVersion,
    reference: ExternalScriptReference,
    asset: ContentScriptAsset | None = None,
    remote_asset_sha256: str | None = None,
    remote_asset_size_bytes: int | None = None,
) -> ContentScriptAssetRemoteDriftIssue:
    return ContentScriptAssetRemoteDriftIssue(
        code=code,
        severity=severity,
        message=message,
        page_id=page.id,
        page_version_id=version.id,
        slug=page.slug,
        sandbox_id=reference.sandbox_id,
        reference_key=reference.reference_key,
        reference_value_sha256=reference.reference_value_sha256,
        source_host=reference.source_host,
        source_url_sha256=sha256(reference.source_url.encode("utf-8")).hexdigest(),
        asset_id=asset.id if asset is not None else None,
        asset_sha256=asset.asset_sha256 if asset is not None else None,
        remote_asset_sha256=remote_asset_sha256,
        remote_asset_size_bytes=remote_asset_size_bytes,
        published_at=version.published_at,
    )


def _append_remote_drift_issue(
    issues: list[ContentScriptAssetRemoteDriftIssue],
    issue: ContentScriptAssetRemoteDriftIssue,
    *,
    issue_code: str | None,
    severity: str | None,
) -> None:
    if issue_code is not None and issue.code != issue_code:
        return
    if severity is not None and issue.severity != severity:
        return
    issues.append(issue)


def _fetch_external_script_asset(url: str) -> bytes:
    try:
        payload = content_script_policy._default_external_script_fetcher(url)
    except Exception as exc:
        raise ContentScriptAssetMirrorError("External script asset could not be downloaded for mirroring") from exc
    if len(payload) > content_script_policy.MAX_EXTERNAL_SCRIPT_BYTES:
        raise ContentScriptAssetMirrorError("External script asset exceeds maximum mirror size")
    return payload
