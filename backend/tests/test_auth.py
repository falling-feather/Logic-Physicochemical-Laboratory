def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_register_login_me_logout(client):
    register = client.post(
        "/api/auth/register",
        json={
            "username": "teacher01",
            "password": "secret123",
            "display_name": "Teacher One",
            "role": "teacher",
        },
    )
    assert register.status_code == 201
    assert register.json()["role"] == "teacher"

    login = client.post(
        "/api/auth/login",
        json={"username": "teacher01", "password": "secret123"},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]

    me = client.get("/api/users/me", headers=_auth_header(token))
    assert me.status_code == 200
    assert me.json()["username"] == "teacher01"

    logout = client.post("/api/auth/logout", headers=_auth_header(token))
    assert logout.status_code == 200

    after_logout = client.get("/api/users/me", headers=_auth_header(token))
    assert after_logout.status_code == 401


def test_public_register_rejects_admin_role(client):
    response = client.post(
        "/api/auth/register",
        json={
            "username": "admin01",
            "password": "secret123",
            "display_name": "Admin One",
            "role": "admin",
        },
    )

    assert response.status_code == 422
