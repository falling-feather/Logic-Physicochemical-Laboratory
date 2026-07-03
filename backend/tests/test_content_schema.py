def test_energy_conservation_render_schema(client):
    response = client.get("/api/render/page/physics/energy-conservation")

    assert response.status_code == 200
    payload = response.json()
    assert payload["slug"] == "physics/energy-conservation"
    assert payload["layout"] == "experiment-page"
    assert payload["sections"][2]["type"] == "experiment"
    assert payload["sections"][2]["experimentId"] == "energy-conservation"
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
