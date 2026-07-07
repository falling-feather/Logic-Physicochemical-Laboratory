from html import escape
from typing import Any
from urllib.parse import unquote

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.content import ContentPage
from app.services.content_catalog import get_page_schema, get_published_page_schema
from app.services.content_script_policy import collect_content_script_manifests


router = APIRouter()


@router.get("/script-sandboxes/{sandbox_id}/page/{slug:path}", response_class=HTMLResponse)
def render_script_sandbox_document(sandbox_id: str, slug: str, response: Response, db: Session = Depends(get_db)) -> str:
    page = get_published_page_schema(db, slug)
    if page is None:
        raise HTTPException(status_code=404, detail="Renderable page not found")
    manifest = _find_script_sandbox_manifest(page, sandbox_id)
    sandbox = manifest["sandbox"]
    script_sources = [_script_source_from_reference(reference) for reference in manifest["references"]]
    csp = _harden_sandbox_csp(str(sandbox["csp"]))
    response.headers["Content-Security-Policy"] = csp
    response.headers["X-Astra-Content-Script-Sandbox-Id"] = sandbox_id
    response.headers["X-Astra-Content-Script-Iframe-Sandbox"] = str(sandbox["iframeSandbox"])
    response.headers["X-Astra-Content-Script-Reference-Count"] = str(len(script_sources))
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    return _script_sandbox_html(slug=page.slug, sandbox_id=sandbox_id, script_sources=script_sources)


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


def _script_source_from_reference(reference: dict[str, Any]) -> str:
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


def _harden_sandbox_csp(csp: str) -> str:
    hardening_directives = [
        "base-uri 'none'",
        "object-src 'none'",
        "frame-ancestors 'self'",
        "form-action 'none'",
    ]
    return "; ".join([csp.rstrip("; "), *hardening_directives])


def _script_sandbox_html(*, slug: str, sandbox_id: str, script_sources: list[str]) -> str:
    script_tags = "\n".join(
        f'    <script src="{escape(source, quote=True)}" defer></script>' for source in script_sources
    )
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
        f"{script_tags}\n"
        "  </body>\n"
        "</html>\n"
    )
