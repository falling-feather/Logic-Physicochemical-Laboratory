from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.content import ContentPage
from app.services.content_catalog import get_page_schema


router = APIRouter()


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
