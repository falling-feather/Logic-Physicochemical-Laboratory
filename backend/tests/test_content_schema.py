from sqlalchemy import delete, func, select

from app.core.config import get_settings
from app.db.session import get_session_factory
from app.models import ContentPageRecord


def test_energy_conservation_render_schema(client):
    response = client.get("/api/render/page/physics/energy-conservation")

    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["Pragma"] == "no-cache"
    payload = response.json()
    assert payload["slug"] == "physics/energy-conservation"
    assert payload["layout"] == "experiment-page"
    assert payload["sections"][2]["type"] == "experiment"
    assert payload["sections"][2]["experimentId"] == "energy-conservation"
    experiment_props = payload["sections"][2]["props"]
    assert "scriptPath" not in experiment_props
    assert "scriptSandbox" not in experiment_props
    assert experiment_props["scriptManifest"]["executionMode"] == "sandbox-required"
    assert experiment_props["scriptManifest"]["sandbox"]["status"] == "isolated"
    assert experiment_props["scriptManifest"]["referenceCount"] == 1
    assert len(experiment_props["scriptManifest"]["references"][0]["valueSha256"]) == 64
    assert payload["courseUnit"]["unitId"] == "physics-energy-conservation"


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
