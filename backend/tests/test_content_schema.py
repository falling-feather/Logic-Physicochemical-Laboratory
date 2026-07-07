from sqlalchemy import delete, func, select
import pytest

from app.core.config import get_settings
from app.db.session import get_session_factory
from app.models import ContentPageRecord
from app.schemas.content import ContentPage


def test_energy_conservation_render_schema(client):
    response = client.get("/api/render/page/physics/energy-conservation")

    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["Pragma"] == "no-cache"
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
    assert experiment_props["scriptManifest"]["sandbox"]["status"] == "isolated"
    assert experiment_props["scriptManifest"]["referenceCount"] == 1
    assert len(experiment_props["scriptManifest"]["references"][0]["valueSha256"]) == 64
    assert payload["courseUnit"]["unitId"] == "physics-energy-conservation"
    assert payload["sources"][0]["sourceId"] == "openstax-conservation-energy"


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
