import re
from urllib.parse import quote

from sqlalchemy import delete, func, select
import pytest
from fastapi import HTTPException, Response

from app.api.endpoints.render import _apply_script_contract_headers, _harden_sandbox_csp, _script_manifest_references
from app.core.config import get_settings
from app.db.session import get_session_factory
from app.models import ContentPageRecord, ContentPageVersion, User
from app.models.base import utc_now
from app.schemas.content import ContentPage
from app.services.content_script_policy import public_content_page_schema
from app.services.content_script_sandbox_templates import (
    ENERGY_CONSERVATION_TEMPLATE_ID,
    SCRIPT_SANDBOX_DOCUMENT_CONTRACT_VERSION,
)


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
    assert experiment_props["scriptManifest"]["sandbox"]["document"] == _sandbox_document_contract()
    assert experiment_props["scriptManifest"]["referenceCount"] == 1
    assert len(experiment_props["scriptManifest"]["references"][0]["valueSha256"]) == 64
    embed = experiment_props["scriptManifest"]["embed"]
    assert embed["descriptorVersion"] == "astra-script-sandbox-embed-v1"
    assert embed["status"] == "embeddable"
    assert embed["sandboxId"] == experiment_props["scriptManifest"]["sandboxId"]
    assert embed["iframe"] == {
        "src": f"/api/render/script-sandboxes/{embed['sandboxId']}/page/physics/energy-conservation",
        "sandbox": "allow-scripts",
        "referrerPolicy": "no-referrer",
        "loading": "lazy",
        "title": "Astra Script Sandbox",
    }
    assert embed["requiredContentSecurityPolicy"] == experiment_props["scriptManifest"]["sandbox"]["csp"]
    assert embed["originModel"] == "opaque"
    assert embed["capabilities"] == experiment_props["scriptManifest"]["sandbox"]["capabilities"]
    assert embed["messageProtocol"] == {
        "source": "astra-content-script-sandbox",
        "sandboxId": embed["sandboxId"],
        "bootstrapProtocolVersion": "astra-script-sandbox-bootstrap-v1",
        "systemMessageTypes": [
            "bootstrap-ready",
            "assets-ready",
            "ready",
            "error",
            "unhandledrejection",
        ],
    }
    assert embed["assetCount"] == 1
    assert embed["document"] == {
        "contractVersion": SCRIPT_SANDBOX_DOCUMENT_CONTRACT_VERSION,
        "templateId": ENERGY_CONSERVATION_TEMPLATE_ID,
    }
    public_render_text = response.text
    assert "scriptUrl" not in public_render_text
    assert "scriptIntegrity" not in public_render_text
    assert "scriptCrossorigin" not in public_render_text
    assert "pages/physics/energy-conservation.js" not in public_render_text
    assert "/assets/" not in public_render_text
    assert "nonce-" not in public_render_text
    assert "initEnergyConservation" not in public_render_text
    assert payload["courseUnit"]["unitId"] == "physics-energy-conservation"
    assert payload["sources"][0]["sourceId"] == "openstax-conservation-energy"


def test_render_script_sandbox_document_serves_isolated_html(client):
    render = client.get("/api/render/page/physics/energy-conservation")
    manifest = render.json()["sections"][2]["props"]["scriptManifest"]
    sandbox_id = manifest["sandboxId"]
    assert manifest["embed"]["iframe"]["src"] == f"/api/render/script-sandboxes/{sandbox_id}/page/physics/energy-conservation"

    response = client.get(manifest["embed"]["iframe"]["src"])

    assert response.status_code == 200
    assert response.headers["Content-Type"].startswith("text/html")
    assert response.headers["X-Astra-Content-Script-Sandbox-Id"] == sandbox_id
    assert response.headers["X-Astra-Content-Script-Iframe-Sandbox"] == "allow-scripts"
    assert response.headers["X-Astra-Content-Script-Reference-Count"] == "1"
    assert response.headers["X-Astra-Content-Script-Template-Id"] == ENERGY_CONSERVATION_TEMPLATE_ID
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert response.headers["Cache-Control"] == "no-store"
    assert "X-Astra-Content-Script-Nonce" not in response.headers
    assert "connect-src 'self'" in response.headers["Content-Security-Policy"]
    assert "frame-ancestors 'self' http://127.0.0.1:8766 http://localhost:8766" in response.headers["Content-Security-Policy"]
    assert "form-action 'none'" in response.headers["Content-Security-Policy"]
    nonce = _nonce_from_csp(response.headers["Content-Security-Policy"])
    assert nonce is not None
    assert "script-src 'self'" not in response.headers["Content-Security-Policy"]
    body = response.text
    assert f'data-sandbox-id="{sandbox_id}"' in body
    assert f'data-template-id="{ENERGY_CONSERVATION_TEMPLATE_ID}"' in body
    assert f'content="{ENERGY_CONSERVATION_TEMPLATE_ID}"' in body
    for element_id in [
        "astra-sandbox-root",
        "energy-friction",
        "energy-friction-value",
        "energy-play",
        "energy-reset",
        "energy-canvas",
        "energy-info",
    ]:
        assert f'id="{element_id}"' in body
    assert "--font-sans" in body
    assert "physics-energy-conservation-v1" in body
    bootstrap_url = f"/api/render/script-sandboxes/{sandbox_id}/bootstrap/page/physics/energy-conservation"
    asset_sha256 = manifest["references"][0]["valueSha256"]
    asset_url = f"/api/render/script-sandboxes/{sandbox_id}/assets/{asset_sha256}/page/physics/energy-conservation"
    assert f'<script src="{bootstrap_url}" nonce="{nonce}" defer></script>' in body
    assert f'<script src="{asset_url}" defer></script>' not in body
    assert "scriptSandbox" not in body
    assert "valueSha256" not in body

    second_response = client.get(f"/api/render/script-sandboxes/{sandbox_id}/page/physics/energy-conservation")
    second_nonce = _nonce_from_csp(second_response.headers["Content-Security-Policy"])
    assert second_nonce is not None
    assert second_nonce != nonce
    assert f'nonce="{second_nonce}"' in second_response.text

    bootstrap = client.get(bootstrap_url)
    assert bootstrap.status_code == 200
    assert bootstrap.headers["Content-Type"].startswith("application/javascript")
    assert bootstrap.headers["Cache-Control"] == "no-store"
    assert bootstrap.headers["X-Astra-Content-Script-Sandbox-Id"] == sandbox_id
    assert bootstrap.headers["X-Astra-Content-Script-Bootstrap-Version"] == "bootstrap-v1"
    assert bootstrap.headers["X-Astra-Content-Script-Asset-Count"] == "1"
    assert bootstrap.headers["X-Astra-Content-Script-Template-Id"] == ENERGY_CONSERVATION_TEMPLATE_ID
    assert bootstrap.headers["X-Content-Type-Options"] == "nosniff"
    assert bootstrap.headers["Cross-Origin-Resource-Policy"] == "cross-origin"
    assert "astra-script-sandbox-bootstrap-v1" in bootstrap.text
    assert "__ASTRA_SCRIPT_SANDBOX__" in bootstrap.text
    assert "document.currentScript" in bootstrap.text
    assert "bootstrap-ready" in bootstrap.text
    assert "assets-ready" in bootstrap.text
    assert "unhandledrejection" in bootstrap.text
    assert "isBenignResizeObserverError" in bootstrap.text
    assert "ResizeObserver loop limit exceeded" in bootstrap.text
    assert "ResizeObserver loop completed with undelivered notifications." in bootstrap.text
    assert 'const initializerName = "initEnergyConservation"' in bootstrap.text
    assert 'const documentConfig = Object.freeze({"defaultFriction":0.1})' in bootstrap.text
    assert "const initializeDocument = async ()" in bootstrap.text
    assert "Registered sandbox initializer did not confirm readiness" in bootstrap.text
    assert bootstrap.text.index('post("assets-ready"') < bootstrap.text.index("return initializeDocument()")
    assert bootstrap.text.index("return initializeDocument()") < bootstrap.text.index('.then(() => post("ready"')
    assert asset_url in bootstrap.text
    assert "/pages/physics/energy-conservation.js" not in bootstrap.text

    asset = client.get(asset_url)
    assert asset.status_code == 200
    assert asset.headers["Content-Type"].startswith("application/javascript")
    assert asset.headers["X-Astra-Content-Script-Sandbox-Id"] == sandbox_id
    assert asset.headers["X-Astra-Content-Script-Asset-Sha256"] == asset_sha256
    assert asset.headers["X-Content-Type-Options"] == "nosniff"
    assert asset.headers["Cache-Control"] == "no-store"
    assert asset.headers["Cross-Origin-Resource-Policy"] == "cross-origin"
    assert asset.headers["Referrer-Policy"] == "no-referrer"
    assert "const EnergyConservation" in asset.text
    assert "this.root.querySelector" in asset.text
    assert "return { ready: true }" in asset.text
    assert "typeof CF !== 'undefined'" in asset.text
    assert "document.getElementById('energy-canvas')" not in asset.text

    missing_asset = client.get(
        f"/api/render/script-sandboxes/{sandbox_id}/assets/{'0' * 64}/page/physics/energy-conservation"
    )
    assert missing_asset.status_code == 404
    assert missing_asset.json()["detail"] == "Script sandbox asset not found"


def test_sandbox_csp_nonce_updates_script_src_without_mutating_public_manifest(client):
    render = client.get("/api/render/page/physics/energy-conservation")
    manifest = render.json()["sections"][2]["props"]["scriptManifest"]
    public_csp = manifest["sandbox"]["csp"]
    assert "script-src 'self'" in public_csp
    assert "'nonce-" not in public_csp

    csp = _harden_sandbox_csp(
        "default-src 'none'; script-src 'self'; connect-src 'none'; script-src https://example.invalid; ",
        nonce="fixed_nonce",
    )

    assert csp.count("script-src") == 1
    assert "script-src 'nonce-fixed_nonce'" in csp
    assert "script-src 'self'" not in csp
    assert "'unsafe-inline'" not in csp
    assert "connect-src 'none'" in csp
    assert "frame-ancestors 'self'" in csp
    assert "form-action 'none'" in csp

    dev_frame_csp = _harden_sandbox_csp(
        "default-src 'none'; script-src 'self'",
        nonce="frontend_nonce",
        frame_ancestors=["'self'", "http://frontend.example.test"],
    )
    assert "frame-ancestors 'self' http://frontend.example.test" in dev_frame_csp

    no_script_src = _harden_sandbox_csp("default-src 'none'; img-src 'self'", nonce="another_nonce")
    assert "script-src 'nonce-another_nonce'" in no_script_src


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
    assert "embed" not in manifest
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
        "scriptSandbox": {
            "mode": "isolated-iframe",
            "network": "same-origin",
            "storage": "none",
            "document": _sandbox_document_contract(),
        },
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
    assert "embed" not in manifests[0]
    assert "embed" not in manifests[1]

    response = client.get(f"/api/render/script-sandboxes/{manifests[0]['sandboxId']}/page/physics/ambiguous-sandbox")

    assert response.status_code == 409
    assert response.json()["detail"] == "Script sandbox manifest is ambiguous"


def test_render_script_sandbox_document_rejects_assets_outside_allowed_roots(client):
    payload = _content_page_payload()
    payload["slug"] = "physics/outside-root-sandbox"
    payload["status"] = "published"
    payload["sections"][0]["props"] = {
        "scriptPath": "muban/template.js",
        "scriptSandbox": {
            "mode": "isolated-iframe",
            "network": "same-origin",
            "storage": "none",
            "document": _sandbox_document_contract(),
        },
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


def test_render_script_sandbox_document_requires_published_external_mirror(client):
    payload = _content_page_payload()
    payload["slug"] = "physics/unmirrored-external-sandbox"
    payload["status"] = "published"
    payload["version"] = "external-unmirrored-test"
    payload["sections"][0]["props"] = {
        "scriptUrl": "https://cdn.example.test/tool.js",
        "scriptIntegrity": "sha384-AbCdEf0123456789+/=",
        "scriptCrossorigin": "anonymous",
        "scriptSandbox": {
            "mode": "isolated-iframe",
            "network": "same-origin",
            "storage": "none",
            "document": _sandbox_document_contract(),
        },
    }
    session_factory = get_session_factory(get_settings().database_url)
    with session_factory() as db:
        publisher = User(
            username="external_mirror_publisher",
            normalized_username="external_mirror_publisher",
            password_hash="x",
            display_name="External Mirror Publisher",
            role="admin",
            status="active",
        )
        db.add(publisher)
        db.flush()
        page = ContentPageRecord(
            slug=payload["slug"],
            status="published",
            version=payload["version"],
            schema_json=payload,
        )
        db.add(page)
        db.flush()
        version = ContentPageVersion(
            page_id=page.id,
            slug=page.slug,
            status=page.status,
            version=page.version,
            schema_hash="a" * 64,
            schema_json=payload,
            published_by_user_id=publisher.id,
            published_at=utc_now(),
        )
        db.add(version)
        db.flush()
        page.current_version_id = version.id
        db.commit()

    render = client.get("/api/render/page/physics/unmirrored-external-sandbox")
    manifest = render.json()["sections"][0]["props"]["scriptManifest"]
    assert manifest["embed"]["iframe"]["src"].endswith("/page/physics/unmirrored-external-sandbox")
    assert "https://cdn.example.test/tool.js" not in render.text
    assert "scriptIntegrity" not in render.text
    assert "scriptCrossorigin" not in render.text
    response = client.get(
        f"/api/render/script-sandboxes/{manifest['sandboxId']}/page/physics/unmirrored-external-sandbox"
    )
    bootstrap = client.get(
        f"/api/render/script-sandboxes/{manifest['sandboxId']}/bootstrap/page/physics/unmirrored-external-sandbox"
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "External script sandbox asset is not mirrored"
    assert bootstrap.status_code == 409
    assert bootstrap.json()["detail"] == "External script sandbox asset is not mirrored"


def test_script_sandbox_embed_descriptor_encodes_unicode_slug(client):
    slug = "物理/脚本嵌入测试"
    encoded_slug = quote(slug, safe="/")
    payload = _content_page_payload()
    payload["slug"] = slug
    payload["status"] = "published"
    payload["version"] = "unicode-embed-test"
    payload["sections"][0]["props"] = {
        "scriptPath": "pages/physics/energy-conservation.js",
        "scriptSandbox": {
            "mode": "isolated-iframe",
            "network": "same-origin",
            "storage": "none",
            "document": _sandbox_document_contract(),
        },
    }
    session_factory = get_session_factory(get_settings().database_url)
    with session_factory() as db:
        db.add(
            ContentPageRecord(
                slug=payload["slug"],
                status="published",
                version="unicode-embed-test",
                schema_json=payload,
            )
        )
        db.commit()

    render = client.get(f"/api/render/page/{encoded_slug}")

    assert render.status_code == 200
    manifest = render.json()["sections"][0]["props"]["scriptManifest"]
    assert manifest["embed"]["iframe"]["src"] == f"/api/render/script-sandboxes/{manifest['sandboxId']}/page/{encoded_slug}"
    sandbox = client.get(manifest["embed"]["iframe"]["src"])
    assert sandbox.status_code == 200


def test_script_manifest_references_require_hashes():
    with pytest.raises(HTTPException) as exc_info:
        _script_manifest_references({"references": [{"key": "scriptPath", "value": "pages/physics/tool.js"}]})

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == "Script sandbox manifest references are invalid"


@pytest.mark.parametrize(
    ("document", "expected_code"),
    [
        (None, "content_script_sandbox_document_missing"),
        (
            {
                "contractVersion": SCRIPT_SANDBOX_DOCUMENT_CONTRACT_VERSION,
                "templateId": "physics-unregistered-template-v1",
                "config": {},
            },
            "content_script_sandbox_template_unsupported",
        ),
    ],
)
def test_script_sandbox_embed_requires_registered_document_template(client, document, expected_code):
    payload = _content_page_payload()
    payload["slug"] = f"physics/template-gate-{expected_code}"
    payload["status"] = "published"
    sandbox = {"mode": "isolated-iframe", "network": "same-origin", "storage": "none"}
    if document is not None:
        sandbox["document"] = document
    payload["sections"][0]["props"] = {
        "scriptPath": "pages/physics/energy-conservation.js",
        "scriptSandbox": sandbox,
    }
    session_factory = get_session_factory(get_settings().database_url)
    with session_factory() as db:
        db.add(
            ContentPageRecord(
                slug=payload["slug"],
                status="published",
                version="template-gate-test",
                schema_json=payload,
            )
        )
        db.commit()

    render = client.get(f"/api/render/page/{payload['slug']}")
    assert render.status_code == 200
    manifest = render.json()["sections"][0]["props"]["scriptManifest"]
    assert "embed" not in manifest

    sandbox_id = manifest["sandboxId"]
    document_response = client.get(f"/api/render/script-sandboxes/{sandbox_id}/page/{payload['slug']}")
    bootstrap_response = client.get(
        f"/api/render/script-sandboxes/{sandbox_id}/bootstrap/page/{payload['slug']}"
    )
    assert document_response.status_code == 409
    assert bootstrap_response.status_code == 409
    assert document_response.json()["detail"]["code"] == expected_code
    assert bootstrap_response.json()["detail"]["code"] == expected_code


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


def _nonce_from_csp(csp: str) -> str | None:
    match = re.search(r"script-src 'nonce-([A-Za-z0-9_-]+)'", csp)
    if match is None:
        return None
    return match.group(1)


def _sandbox_document_contract(default_friction: float = 0.1) -> dict:
    return {
        "contractVersion": SCRIPT_SANDBOX_DOCUMENT_CONTRACT_VERSION,
        "templateId": ENERGY_CONSERVATION_TEMPLATE_ID,
        "config": {"defaultFriction": default_friction},
    }


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
