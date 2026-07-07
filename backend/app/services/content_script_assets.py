from __future__ import annotations

from dataclasses import dataclass
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
        metadata = content_script_policy._external_script_asset_verification_metadata(reference.integrity, asset_bytes)
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


def _fetch_external_script_asset(url: str) -> bytes:
    try:
        payload = content_script_policy._default_external_script_fetcher(url)
    except Exception as exc:
        raise ContentScriptAssetMirrorError("External script asset could not be downloaded for mirroring") from exc
    if len(payload) > content_script_policy.MAX_EXTERNAL_SCRIPT_BYTES:
        raise ContentScriptAssetMirrorError("External script asset exceeds maximum mirror size")
    return payload
