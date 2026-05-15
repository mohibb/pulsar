"""Tests for auth routes and user management."""


# ── Login ─────────────────────────────────────────────────────────────────────


def test_login_success(client):
    r = client.post("/api/auth/login", json={"username": "admin", "password": "admin"})
    assert r.status_code == 200
    body = r.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"
    assert body["is_admin"] is True
    assert body["username"] == "admin"


def test_login_wrong_password(client):
    r = client.post("/api/auth/login", json={"username": "admin", "password": "wrong"})
    assert r.status_code == 401


def test_login_unknown_user(client):
    r = client.post("/api/auth/login", json={"username": "nobody", "password": "x"})
    assert r.status_code == 401


# ── List users ────────────────────────────────────────────────────────────────


def test_list_users_unauthenticated(client):
    assert client.get("/api/auth/users").status_code == 401


def test_list_users_as_admin(client, auth_headers):
    r = client.get("/api/auth/users", headers=auth_headers)
    assert r.status_code == 200
    users = r.json()
    assert isinstance(users, list)
    assert any(u["username"] == "admin" for u in users)


# ── Create user ───────────────────────────────────────────────────────────────


def test_create_user_unauthenticated(client):
    r = client.post("/api/auth/users", json={"username": "bob", "password": "pass"})
    assert r.status_code == 401


def test_create_user_as_admin(client, auth_headers):
    r = client.post(
        "/api/auth/users",
        json={"username": "bob", "password": "pass123"},
        headers=auth_headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["username"] == "bob"
    assert body["is_admin"] is False


def test_create_user_duplicate(client, auth_headers):
    client.post("/api/auth/users", json={"username": "bob", "password": "p"}, headers=auth_headers)
    r = client.post(
        "/api/auth/users", json={"username": "bob", "password": "p"}, headers=auth_headers
    )
    assert r.status_code == 409


def test_create_user_missing_username(client, auth_headers):
    r = client.post("/api/auth/users", json={"username": "", "password": "p"}, headers=auth_headers)
    assert r.status_code == 400


def test_create_user_missing_password(client, auth_headers):
    r = client.post(
        "/api/auth/users", json={"username": "carol", "password": ""}, headers=auth_headers
    )
    assert r.status_code == 400


def test_created_user_can_login(client, auth_headers):
    client.post(
        "/api/auth/users",
        json={"username": "dave", "password": "secret99"},
        headers=auth_headers,
    )
    r = client.post("/api/auth/login", json={"username": "dave", "password": "secret99"})
    assert r.status_code == 200
    assert r.json()["is_admin"] is False


def test_created_user_cannot_create_users(client, auth_headers):
    client.post(
        "/api/auth/users",
        json={"username": "dave", "password": "secret99"},
        headers=auth_headers,
    )
    dave_token = client.post(
        "/api/auth/login", json={"username": "dave", "password": "secret99"}
    ).json()["access_token"]
    dave_headers = {"Authorization": f"Bearer {dave_token}"}
    r = client.post(
        "/api/auth/users",
        json={"username": "eve", "password": "p"},
        headers=dave_headers,
    )
    assert r.status_code == 403


# ── Delete user ───────────────────────────────────────────────────────────────


def test_delete_user(client, auth_headers):
    client.post("/api/auth/users", json={"username": "bob", "password": "p"}, headers=auth_headers)
    r = client.delete("/api/auth/users/bob", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["deleted"] == "bob"


def test_delete_admin_fails(client, auth_headers):
    r = client.delete("/api/auth/users/admin", headers=auth_headers)
    assert r.status_code == 404


def test_delete_unauthenticated(client):
    assert client.delete("/api/auth/users/admin").status_code == 401
