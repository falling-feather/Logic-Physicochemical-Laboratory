import json
from html import escape
from pathlib import Path
from typing import Any
from urllib.parse import quote, unquote

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.schemas.content import ContentPage
from app.services.content_catalog import get_page_schema, get_published_page_schema
from app.services.content_script_policy import collect_content_script_manifests


router = APIRouter()
PROJECT_ROOT = Path(__file__).resolve().parents[4]
LOCAL_SCRIPT_ASSET_ROOTS = (
    PROJECT_ROOT / "pages",
    PROJECT_ROOT / "shared" / "js",
    PROJECT_ROOT / "codevis" / "shared" / "js",
    PROJECT_ROOT / "drafts",
)


@router.get("/script-sandboxes/{sandbox_id}/page/{slug:path}", response_class=HTMLResponse)
def render_script_sandbox_document(sandbox_id: str, slug: str, response: Response, db: Session = Depends(get_db)) -> str:
    page = get_published_page_schema(db, slug)
    if page is None:
        raise HTTPException(status_code=404, detail="Renderable page not found")
    manifest = _find_script_sandbox_manifest(page, sandbox_id)
    sandbox = manifest["sandbox"]
    references = _script_manifest_references(manifest)
    for reference in references:
        _local_script_asset_path(reference)
    csp = _harden_sandbox_csp(str(sandbox["csp"]))
    response.headers["Content-Security-Policy"] = csp
    response.headers["X-Astra-Content-Script-Sandbox-Id"] = sandbox_id
    response.headers["X-Astra-Content-Script-Iframe-Sandbox"] = str(sandbox["iframeSandbox"])
    response.headers["X-Astra-Content-Script-Reference-Count"] = str(len(references))
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    return _script_sandbox_html(slug=page.slug, sandbox_id=sandbox_id, references=references)


@router.get("/script-sandboxes/{sandbox_id}/bootstrap/page/{slug:path}")
def render_script_sandbox_bootstrap(
    sandbox_id: str,
    slug: str,
    response: Response,
    db: Session = Depends(get_db),
) -> Response:
    page = get_published_page_schema(db, slug)
    if page is None:
        raise HTTPException(status_code=404, detail="Renderable page not found")
    manifest = _find_script_sandbox_manifest(page, sandbox_id)
    references = _script_manifest_references(manifest)
    for reference in references:
        _local_script_asset_path(reference)
    asset_urls = [
        _script_sandbox_asset_url(slug=page.slug, sandbox_id=sandbox_id, asset_sha256=str(reference["valueSha256"]))
        for reference in references
    ]
    payload = _script_sandbox_bootstrap_js(slug=page.slug, sandbox_id=sandbox_id, asset_urls=asset_urls)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Astra-Content-Script-Sandbox-Id"] = sandbox_id
    response.headers["X-Astra-Content-Script-Bootstrap-Version"] = "bootstrap-v1"
    response.headers["X-Astra-Content-Script-Asset-Count"] = str(len(asset_urls))
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
    response.headers["Referrer-Policy"] = "no-referrer"
    return Response(
        content=payload,
        media_type="application/javascript; charset=utf-8",
        headers=dict(response.headers),
    )


@router.get("/script-sandboxes/{sandbox_id}/assets/{asset_sha256}/page/{slug:path}")
def render_script_sandbox_asset(
    sandbox_id: str,
    asset_sha256: str,
    slug: str,
    response: Response,
    db: Session = Depends(get_db),
) -> Response:
    page = get_published_page_schema(db, slug)
    if page is None:
        raise HTTPException(status_code=404, detail="Renderable page not found")
    manifest = _find_script_sandbox_manifest(page, sandbox_id)
    references = _script_manifest_references(manifest)
    reference = _script_reference_by_sha256(references, asset_sha256)
    if reference is None:
        raise HTTPException(status_code=404, detail="Script sandbox asset not found")
    asset_path = _local_script_asset_path(reference)
    payload = asset_path.read_bytes()
    response.headers["X-Astra-Content-Script-Sandbox-Id"] = sandbox_id
    response.headers["X-Astra-Content-Script-Asset-Sha256"] = asset_sha256
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    return Response(
        content=payload,
        media_type="application/javascript; charset=utf-8",
        headers=dict(response.headers),
    )


@router.get("/page/{slug:path}", response_model=ContentPage)
def render_page(slug: str, response: Response, db: Session = Depends(get_db)) -> ContentPage:
    page = get_page_schema(db, slug)
    if page is None:
        raise HTTPException(status_code=404, detail="Renderable page not found")
    _apply_script_contract_headers(response, page)
    return page


def _apply_script_contract_headers(response: Response, page: ContentPage) -> None:
    manifests = _collect_script_manifests(page.model_dump(mode="json"))
    response.headers["X-Astra-Content-Script-Sandbox"] = "required" if manifests else "not-required"
    response.headers["X-Astra-Content-Script-Manifest-Count"] = str(len(manifests))
    if not manifests:
        return
    iframe_sandbox = _uniform_script_contract_value(manifests, "iframeSandbox")
    if iframe_sandbox is not None:
        response.headers["X-Astra-Content-Script-Iframe-Sandbox"] = iframe_sandbox
    content_security_policy = _uniform_script_contract_value(manifests, "csp")
    if content_security_policy is not None:
        response.headers["X-Astra-Content-Script-CSP"] = content_security_policy


def _uniform_script_contract_value(manifests: list[dict[str, Any]], key: str) -> str | None:
    values = []
    for manifest in manifests:
        sandbox = manifest.get("sandbox")
        if not isinstance(sandbox, dict):
            return None
        value = sandbox.get(key)
        if not isinstance(value, str):
            return None
        values.append(value)
    unique_values = set(values)
    if len(unique_values) != 1:
        return None
    return values[0]


def _collect_script_manifests(value: Any) -> list[dict[str, Any]]:
    manifests: list[dict[str, Any]] = []
    if isinstance(value, list):
        for item in value:
            manifests.extend(_collect_script_manifests(item))
        return manifests
    if not isinstance(value, dict):
        return manifests
    manifest = value.get("scriptManifest")
    if isinstance(manifest, dict):
        manifests.append(manifest)
    for item in value.values():
        manifests.extend(_collect_script_manifests(item))
    return manifests


def _find_script_sandbox_manifest(page: ContentPage, sandbox_id: str) -> dict[str, Any]:
    manifests = [
        manifest
        for manifest in collect_content_script_manifests(page, include_private_values=True)
        if manifest.get("sandboxId") == sandbox_id
    ]
    if not manifests:
        raise HTTPException(status_code=404, detail="Script sandbox manifest not found")
    if len(manifests) > 1:
        raise HTTPException(status_code=409, detail="Script sandbox manifest is ambiguous")
    manifest = manifests[0]
    sandbox = manifest.get("sandbox")
    if not isinstance(sandbox, dict) or sandbox.get("status") != "isolated":
        raise HTTPException(status_code=409, detail="Script sandbox manifest is not executable")
    if not isinstance(sandbox.get("csp"), str) or not isinstance(sandbox.get("iframeSandbox"), str):
        raise HTTPException(status_code=409, detail="Script sandbox manifest is incomplete")
    references = manifest.get("references")
    if not isinstance(references, list) or not references:
        raise HTTPException(status_code=409, detail="Script sandbox manifest has no executable references")
    return manifest


def _script_manifest_references(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    references = manifest.get("references")
    if not isinstance(references, list) or not references:
        raise HTTPException(status_code=409, detail="Script sandbox manifest has no executable references")
    if not all(isinstance(reference, dict) for reference in references):
        raise HTTPException(status_code=409, detail="Script sandbox manifest references are invalid")
    if not all(_is_valid_sha256(reference.get("valueSha256")) for reference in references):
        raise HTTPException(status_code=409, detail="Script sandbox manifest references are invalid")
    return references


def _script_reference_by_sha256(references: list[dict[str, Any]], asset_sha256: str) -> dict[str, Any] | None:
    normalized_asset_sha256 = asset_sha256.strip().lower()
    if not _is_valid_sha256(normalized_asset_sha256):
        return None
    for reference in references:
        value_sha256 = reference.get("valueSha256")
        if isinstance(value_sha256, str) and value_sha256.lower() == normalized_asset_sha256:
            return reference
    return None


def _is_valid_sha256(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    normalized = value.strip().lower()
    return len(normalized) == 64 and all(char in "0123456789abcdef" for char in normalized)


def _local_script_source_from_reference(reference: dict[str, Any]) -> str:
    key = str(reference.get("key", ""))
    normalized_key = key.replace("_", "").replace("-", "").lower()
    if normalized_key == "inlinescript":
        raise HTTPException(status_code=409, detail="Inline scripts cannot be rendered in a sandbox document")
    value = reference.get("value")
    if not isinstance(value, str) or not value.strip():
        raise HTTPException(status_code=409, detail="Script sandbox reference is missing a source")
    source = value.strip()
    lowered = source.lower()
    if lowered.startswith(("http://", "https://", "//")):
        raise HTTPException(status_code=409, detail="External script sandbox documents require mirrored assets")
    if lowered.startswith(("javascript:", "data:", "vbscript:", "blob:")):
        raise HTTPException(status_code=409, detail="Script sandbox reference uses a blocked protocol")
    decoded = unquote(source).replace("\\", "/")
    normalized_path = decoded.lstrip("/")
    if not normalized_path or any(part in {"", ".", ".."} for part in normalized_path.split("/")):
        raise HTTPException(status_code=409, detail="Script sandbox reference path is unsafe")
    path = f"/{normalized_path}"
    if not path.endswith(".js"):
        raise HTTPException(status_code=409, detail="Script sandbox reference must point to a JavaScript asset")
    return path


def _local_script_asset_path(reference: dict[str, Any]) -> Path:
    source = _local_script_source_from_reference(reference)
    asset_path = _script_asset_path(source)
    if not asset_path.is_file():
        raise HTTPException(status_code=404, detail="Script sandbox asset file not found")
    return asset_path


def _script_asset_path(source: str) -> Path:
    relative_source = source.lstrip("/")
    candidate = (PROJECT_ROOT / relative_source).resolve()
    try:
        candidate.relative_to(PROJECT_ROOT)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail="Script sandbox reference path is outside the project") from exc
    if not _is_allowed_local_script_asset(candidate):
        raise HTTPException(status_code=409, detail="Script sandbox asset path is outside allowed roots")
    return candidate


def _is_allowed_local_script_asset(candidate: Path) -> bool:
    for root in LOCAL_SCRIPT_ASSET_ROOTS:
        try:
            candidate.relative_to(root.resolve())
            return True
        except ValueError:
            continue
    return False


def _harden_sandbox_csp(csp: str) -> str:
    hardening_directives = [
        "base-uri 'none'",
        "object-src 'none'",
        "frame-ancestors 'self'",
        "form-action 'none'",
    ]
    return "; ".join([csp.rstrip("; "), *hardening_directives])


def _script_sandbox_html(*, slug: str, sandbox_id: str, references: list[dict[str, Any]]) -> str:
    bootstrap_url = _script_sandbox_bootstrap_url(slug=slug, sandbox_id=sandbox_id)
    return (
        "<!doctype html>\n"
        '<html lang="zh-CN">\n'
        "  <head>\n"
        '    <meta charset="utf-8">\n'
        '    <meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f'    <meta name="astra-content-slug" content="{escape(slug, quote=True)}">\n'
        f'    <meta name="astra-script-sandbox-id" content="{escape(sandbox_id, quote=True)}">\n'
        "    <title>Astra Script Sandbox</title>\n"
        "  </head>\n"
        "  <body>\n"
        f'    <div id="astra-sandbox-root" data-slug="{escape(slug, quote=True)}" '
        f'data-sandbox-id="{escape(sandbox_id, quote=True)}"></div>\n'
        f'    <script src="{escape(bootstrap_url, quote=True)}" defer></script>\n'
        "  </body>\n"
        "</html>\n"
    )


def _script_sandbox_bootstrap_js(*, slug: str, sandbox_id: str, asset_urls: list[str]) -> str:
    slug_literal = _js_string_literal(slug)
    sandbox_id_literal = _js_string_literal(sandbox_id)
    asset_urls_literal = json.dumps(asset_urls)
    return (
        "(() => {\n"
        '  "use strict";\n'
        "  const metadata = Object.freeze({\n"
        "    protocolVersion: \"astra-script-sandbox-bootstrap-v1\",\n"
        f"    slug: {slug_literal},\n"
        f"    sandboxId: {sandbox_id_literal},\n"
        f"    assetCount: {len(asset_urls)},\n"
        "  });\n"
        f"  const assetUrls = Object.freeze({asset_urls_literal});\n"
        "  const nonce = document.currentScript && document.currentScript.nonce ? document.currentScript.nonce : \"\";\n"
        "  const post = (type, payload = {}) => {\n"
        "    if (window.parent === window) return;\n"
        "    window.parent.postMessage({ source: \"astra-content-script-sandbox\", type, metadata, payload }, \"*\");\n"
        "  };\n"
        "  const normalizeError = (value) => {\n"
        "    if (!value) return \"\";\n"
        "    if (typeof value === \"string\") return value.slice(0, 500);\n"
        "    if (value && typeof value.message === \"string\") return value.message.slice(0, 500);\n"
        "    return String(value).slice(0, 500);\n"
        "  };\n"
        "  window.__ASTRA_SCRIPT_SANDBOX__ = Object.freeze({\n"
        "    metadata,\n"
        "    assetUrls,\n"
        "    nonce,\n"
        "    ready(payload = {}) { post(\"ready\", payload); },\n"
        "    error(payload = {}) { post(\"error\", payload); },\n"
        "    post(type, payload = {}) { post(String(type || \"message\"), payload); },\n"
        "  });\n"
        "  const loadAsset = (url) => new Promise((resolve, reject) => {\n"
        "    const script = document.createElement(\"script\");\n"
        "    script.src = url;\n"
        "    script.defer = true;\n"
        "    if (nonce) script.nonce = nonce;\n"
        "    script.onload = () => resolve(url);\n"
        "    script.onerror = () => reject(new Error(`Failed to load sandbox asset: ${url}`));\n"
        "    document.head.appendChild(script);\n"
        "  });\n"
        "  const loadAssets = async () => {\n"
        "    for (const url of assetUrls) {\n"
        "      await loadAsset(url);\n"
        "    }\n"
        "  };\n"
        "  window.addEventListener(\"error\", (event) => {\n"
        "    post(\"error\", {\n"
        "      message: normalizeError(event.message),\n"
        "      filename: event.filename || \"\",\n"
        "      lineno: event.lineno || 0,\n"
        "      colno: event.colno || 0,\n"
        "    });\n"
        "  });\n"
        "  window.addEventListener(\"unhandledrejection\", (event) => {\n"
        "    post(\"unhandledrejection\", { message: normalizeError(event.reason) });\n"
        "  });\n"
        "  post(\"bootstrap-ready\");\n"
        "  loadAssets()\n"
        "    .then(() => post(\"assets-ready\", { assetCount: assetUrls.length }))\n"
        "    .catch((error) => post(\"error\", { message: normalizeError(error) }));\n"
        "})();\n"
    )


def _js_string_literal(value: str) -> str:
    return json.dumps(value)


def _script_sandbox_bootstrap_url(*, slug: str, sandbox_id: str) -> str:
    api_prefix = get_settings().api_prefix.rstrip("/")
    encoded_slug = quote(slug, safe="/")
    return f"{api_prefix}/render/script-sandboxes/{sandbox_id}/bootstrap/page/{encoded_slug}"


def _script_sandbox_asset_url(*, slug: str, sandbox_id: str, asset_sha256: str) -> str:
    api_prefix = get_settings().api_prefix.rstrip("/")
    encoded_slug = quote(slug, safe="/")
    return f"{api_prefix}/render/script-sandboxes/{sandbox_id}/assets/{asset_sha256}/page/{encoded_slug}"
