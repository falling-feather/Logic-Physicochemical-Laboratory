from sqlalchemy import delete, func, select
import pytest
from fastapi import HTTPException, Response

from app.api.endpoints.render import _apply_script_contract_headers, _script_manifest_references
from app.core.config import get_settings
from app.db.session import get_session_factory
from app.models import ContentPageRecord
from app.schemas.content import ContentPage
from app.services.content_script_policy import public_content_page_schema


def test_energy_conservation_render_schema(client):
    response = client.get("/api/render/page/physics/energy-conservation")

    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["Pragma"] == "no-cache"
    assert response.headers["X-Astra-Content-Script-Sandbox"] == "required"
    assert response.headers["X-Astra-Content-Script-Manifest-Count"] == "1"
    assert response.headers["X-Astra-Content-Script-Iframe-Sandbox"] == "allow-scripts"
    assert "connect-src 'self'" in response.headers["X-Astra-Content-Script-CSP"]
    payload = response.json()
    assert payload["slug"] == "physics/energy-conservation"
    assert payload["layout"] == "experiment-page"
    assert payload["sections"][0]["sectionId"] == "energy-hero"
    assert payload["sections"][2]["type"] == "experiment"
    assert payload["sections"][2]["sectionId"] == "energy-interactive-lab"
    assert payload["sections"][2]["experimentId"] == "energy-conservation"
    experiment_props = payload["sections"][2]["props"]
    assert "scriptPath" not in experiment_props
    assert "scriptSandbox" not in experiment_props
    assert experiment_props["scriptManifest"]["executionMode"] == "sandbox-required"
    assert experiment_props["scriptManifest"]["sandboxId"].startswith("sm_")
    assert len(experiment_props["scriptManifest"]["sandboxId"]) == 27
    assert experiment_props["scriptManifest"]["sandbox"]["status"] == "isolated"
    assert experiment_props["scriptManifest"]["sandbox"]["network"] == "same-origin"
    assert "connect-src 'self'" in experiment_props["scriptManifest"]["sandbox"]["csp"]
    assert experiment_props["scriptManifest"]["sandbox"]["enforcement"] == {
        "browserContext": "sandboxed-iframe",
        "requiredIframeSandbox": "allow-scripts",
        "requiredContentSecurityPolicy": experiment_props["scriptManifest"]["sandbox"]["csp"],
        "sandboxOrigin": "opaque",
    }
    assert experiment_props["scriptManifest"]["sandbox"]["capabilities"]["sameOrigin"] is False
    assert experiment_props["scriptManifest"]["referenceCount"] == 1
    assert len(experiment_props["scriptManifest"]["references"][0]["valueSha256"]) == 64
    assert payload["courseUnit"]["unitId"] == "physics-energy-conservation"
    assert payload["sources"][0]["sourceId"] == "openstax-conservation-energy"


def test_render_script_sandbox_document_serves_isolated_html(client):
    render = client.get("/api/render/page/physics/energy-conservation")
    manifest = render.json()["sections"][2]["props"]["scriptManifest"]
    sandbox_id = manifest["sandboxId"]

    response = client.get(f"/api/render/script-sandboxes/{sandbox_id}/page/physics/energy-conservation")

    assert response.status_code == 200
    assert response.headers["Content-Type"].startswith("text/html")
    assert response.headers["X-Astra-Content-Script-Sandbox-Id"] == sandbox_id
    assert response.headers["X-Astra-Content-Script-Iframe-Sandbox"] == "allow-scripts"
    assert response.headers["X-Astra-Content-Script-Reference-Count"] == "1"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert "connect-src 'self'" in response.headers["Content-Security-Policy"]
    assert "frame-ancestors 'self'" in response.headers["Content-Security-Policy"]
    assert "form-action 'none'" in response.headers["Content-Security-Policy"]
    body = response.text
    assert f'data-sandbox-id="{sandbox_id}"' in body
    bootstrap_url = f"/api/render/script-sandboxes/{sandbox_id}/bootstrap/page/physics/energy-conservation"
    asset_sha256 = manifest["references"][0]["valueSha256"]
    asset_url = f"/api/render/script-sandboxes/{sandbox_id}/assets/{asset_sha256}/page/physics/energy-conservation"
    assert f'<script src="{bootstrap_url}" defer></script>' in body
    assert f'<script src="{asset_url}" defer></script>' not in body
    assert "scriptSandbox" not in body
    assert "valueSha256" not in body

    bootstrap = client.get(bootstrap_url)
    assert bootstrap.status_code == 200
    assert bootstrap.headers["Content-Type"].startswith("application/javascript")
    assert bootstrap.headers["Cache-Control"] == "no-store"
    assert bootstrap.headers["X-Astra-Content-Script-Sandbox-Id"] == sandbox_id
    assert bootstrap.headers["X-Astra-Content-Script-Bootstrap-Version"] == "bootstrap-v1"
    assert bootstrap.headers["X-Astra-Content-Script-Asset-Count"] == "1"
    assert bootstrap.headers["X-Content-Type-Options"] == "nosniff"
    assert bootstrap.headers["Cross-Origin-Resource-Policy"] == "same-origin"
    assert "astra-script-sandbox-bootstrap-v1" in bootstrap.text
    assert "__ASTRA_SCRIPT_SANDBOX__" in bootstrap.text
    assert "document.currentScript" in bootstrap.text
    assert "bootstrap-ready" in bootstrap.text
    assert "assets-ready" in bootstrap.text
    assert "unhandledrejection" in bootstrap.text
    assert asset_url in bootstrap.text
    assert "/pages/physics/energy-conservation.js" not in bootstrap.text

    asset = client.get(asset_url)
    assert asset.status_code == 200
    assert asset.headers["Content-Type"].startswith("application/javascript")
    assert asset.headers["X-Astra-Content-Script-Sandbox-Id"] == sandbox_id
    assert asset.headers["X-Astra-Content-Script-Asset-Sha256"] == asset_sha256
    assert asset.headers["X-Content-Type-Options"] == "nosniff"
    assert "const EnergyConservation" in asset.text

    missing_asset = client.get(
        f"/api/render/script-sandboxes/{sandbox_id}/assets/{'0' * 64}/page/physics/energy-conservation"
    )
    assert missing_asset.status_code == 404
    assert missing_asset.json()["detail"] == "Script sandbox asset not found"


def test_render_script_sandbox_document_fails_closed_for_missing_or_blocked_manifest(client):
    missing = client.get("/api/render/script-sandboxes/sm_missing/page/physics/energy-conservation")
    assert missing.status_code == 404

    missing_bootstrap = client.get("/api/render/script-sandboxes/sm_missing/bootstrap/page/physics/energy-conservation")
    assert missing_bootstrap.status_code == 404

    payload = _content_page_payload()
    payload["slug"] = "physics/blocked-sandbox"
    payload["status"] = "published"
    payload["sections"][0]["props"] = {
        "scriptPath": "pages/physics/blocked.js",
        "scriptSandbox": {"mode": "isolated-iframe", "network": "external", "storage": "none"},
    }
    session_factory = get_session_factory(get_settings().database_url)
    with session_factory() as db:
        db.add(
            ContentPageRecord(
                slug=payload["slug"],
                status="published",
                version="blocked-test",
                schema_json=payload,
            )
        )
        db.commit()

    render = client.get("/api/render/page/physics/blocked-sandbox")
    manifest = render.json()["sections"][0]["props"]["scriptManifest"]
    blocked = client.get(f"/api/render/script-sandboxes/{manifest['sandboxId']}/page/physics/blocked-sandbox")

    assert blocked.status_code == 409
    assert blocked.json()["detail"] == "Script sandbox manifest is not executable"

    blocked_bootstrap = client.get(f"/api/render/script-sandboxes/{manifest['sandboxId']}/bootstrap/page/physics/blocked-sandbox")
    assert blocked_bootstrap.status_code == 409
    assert blocked_bootstrap.json()["detail"] == "Script sandbox manifest is not executable"


def test_render_script_sandbox_document_rejects_ambiguous_manifest_id(client):
    payload = _content_page_payload()
    payload["slug"] = "physics/ambiguous-sandbox"
    payload["status"] = "published"
    shared_props = {
        "scriptPath": "pages/physics/ambiguous.js",
        "scriptSandbox": {"mode": "isolated-iframe", "network": "same-origin", "storage": "none"},
    }
    payload["sections"][0]["props"] = dict(shared_props)
    payload["sections"][1]["props"] = dict(shared_props)
    session_factory = get_session_factory(get_settings().database_url)
    with session_factory() as db:
        db.add(
            ContentPageRecord(
                slug=payload["slug"],
                status="published",
                version="ambiguous-test",
                schema_json=payload,
            )
        )
        db.commit()

    render = client.get("/api/render/page/physics/ambiguous-sandbox")
    manifests = [
        section["props"]["scriptManifest"]
        for section in render.json()["sections"]
        if "scriptManifest" in section["props"]
    ]
    assert manifests[0]["sandboxId"] == manifests[1]["sandboxId"]

    response = client.get(f"/api/render/script-sandboxes/{manifests[0]['sandboxId']}/page/physics/ambiguous-sandbox")

    assert response.status_code == 409
    assert response.json()["detail"] == "Script sandbox manifest is ambiguous"


def test_render_script_sandbox_document_rejects_assets_outside_allowed_roots(client):
    payload = _content_page_payload()
    payload["slug"] = "physics/outside-root-sandbox"
    payload["status"] = "published"
    payload["sections"][0]["props"] = {
        "scriptPath": "muban/template.js",
        "scriptSandbox": {"mode": "isolated-iframe", "network": "same-origin", "storage": "none"},
    }
    session_factory = get_session_factory(get_settings().database_url)
    with session_factory() as db:
        db.add(
            ContentPageRecord(
                slug=payload["slug"],
                status="published",
                version="outside-root-test",
                schema_json=payload,
            )
        )
        db.commit()

    render = client.get("/api/render/page/physics/outside-root-sandbox")
    manifest = render.json()["sections"][0]["props"]["scriptManifest"]
    response = client.get(f"/api/render/script-sandboxes/{manifest['sandboxId']}/page/physics/outside-root-sandbox")

    assert response.status_code == 409
    assert response.json()["detail"] == "Script sandbox asset path is outside allowed roots"

    bootstrap = client.get(f"/api/render/script-sandboxes/{manifest['sandboxId']}/bootstrap/page/physics/outside-root-sandbox")
    assert bootstrap.status_code == 409
    assert bootstrap.json()["detail"] == "Script sandbox asset path is outside allowed roots"


def test_script_manifest_references_require_hashes():
    with pytest.raises(HTTPException) as exc_info:
        _script_manifest_references({"references": [{"key": "scriptPath", "value": "pages/physics/tool.js"}]})

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == "Script sandbox manifest references are invalid"


def test_render_contract_headers_require_uniform_script_sandbox_contract():
    payload = _content_page_payload()
    payload["sections"][0]["props"] = {
        "scriptPath": "pages/physics/stable-hero.js",
        "scriptSandbox": {"mode": "isolated-iframe", "network": "none", "storage": "none"},
    }
    payload["sections"][1]["props"] = {
        "scriptPath": "pages/physics/stable-task.js",
        "scriptSandbox": {"mode": "isolated-iframe", "network": "external", "storage": "none"},
    }
    page = public_content_page_schema(payload)
    response = Response()

    _apply_script_contract_headers(response, page)

    assert response.headers["X-Astra-Content-Script-Sandbox"] == "required"
    assert response.headers["X-Astra-Content-Script-Manifest-Count"] == "2"
    assert "X-Astra-Content-Script-Iframe-Sandbox" not in response.headers
    assert "X-Astra-Content-Script-CSP" not in response.headers


def test_content_schema_rejects_duplicate_stable_ids():
    payload = _content_page_payload()
    payload["sections"][1]["sectionId"] = payload["sections"][0]["sectionId"]

    with pytest.raises(ValueError, match="Duplicate content sectionId"):
        ContentPage.model_validate(payload)


def test_content_schema_rejects_duplicate_source_ids():
    payload = _content_page_payload()
    payload["sources"].append(
        {
            "sourceId": payload["sources"][0]["sourceId"],
            "label": "Duplicate",
            "url": "https://example.com/duplicate",
        }
    )

    with pytest.raises(ValueError, match="Duplicate content sourceId"):
        ContentPage.model_validate(payload)


@pytest.mark.parametrize("field", ["sectionId", "sourceId"])
@pytest.mark.parametrize("value", ["UpperCase", "-leading-dash", "has space", "中文标识"])
def test_content_schema_rejects_invalid_stable_id_format(field, value):
    payload = _content_page_payload()
    if field == "sectionId":
        payload["sections"][0]["sectionId"] = value
    else:
        payload["sources"][0]["sourceId"] = value

    with pytest.raises(ValueError):
        ContentPage.model_validate(payload)


def test_unknown_render_schema_returns_404(client):
    response = client.get("/api/render/page/physics/missing")

    assert response.status_code == 404


def test_content_pages_list_uses_seeded_database_record(client):
    response = client.get("/api/content/pages")

    assert response.status_code == 200
    payload = response.json()
    assert payload[0]["slug"] == "physics/energy-conservation"
    assert payload[0]["layout"] == "experiment-page"


def test_content_reads_do_not_seed_missing_records(client):
    _clear_content_pages()

    list_response = client.get("/api/content/pages")
    render_response = client.get("/api/render/page/physics/energy-conservation")

    assert list_response.status_code == 200
    assert list_response.json() == []
    assert render_response.status_code == 404
    assert _content_page_count() == 0


def _clear_content_pages() -> None:
    session_factory = get_session_factory(get_settings().database_url)
    with session_factory() as db:
        db.execute(delete(ContentPageRecord))
        db.commit()


def _content_page_count() -> int:
    session_factory = get_session_factory(get_settings().database_url)
    with session_factory() as db:
        return int(db.scalar(select(func.count()).select_from(ContentPageRecord)) or 0)


def _content_page_payload() -> dict:
    return {
        "slug": "physics/stable-ids",
        "galaxy": "englab",
        "subject": "physics",
        "title": "Stable IDs",
        "layout": "experiment-page",
        "status": "draft",
        "version": "draft-local",
        "summary": "Stable identity test.",
        "sections": [
            {
                "sectionId": "stable-hero",
                "type": "hero",
                "title": "Stable Hero",
                "summary": "Hero.",
                "props": {},
            },
            {
                "sectionId": "stable-task",
                "type": "learning-task",
                "title": "Stable Task",
                "summary": "Task.",
                "props": {},
            },
        ],
        "sources": [
            {
                "sourceId": "stable-source",
                "label": "Stable Source",
                "url": "https://example.com/stable-source",
            }
        ],
    }
