from app.database import SessionLocal
from app.models import User

from .conftest import auth, login, signup


def test_signup_is_always_normal_user_even_if_role_is_sent(client):
    r = client.post(
        "/api/auth/signup",
        json={"email": "sneaky@test.dev", "name": "Sneaky", "password": "Password123", "role": "admin"},
    )
    assert r.status_code == 201
    assert r.json()["user"]["role"] == "user"


def test_password_is_hashed(client):
    signup(client, "hash@test.dev", password="Password123")
    with SessionLocal() as db:
        user = db.query(User).filter_by(email="hash@test.dev").one()
    assert user.hashed_password != "Password123"
    assert user.hashed_password.startswith("$argon2id$")
    assert login(client, "hash@test.dev", "Password123")["user"]["email"] == "hash@test.dev"


def test_wrong_password_rejected(client):
    signup(client, "a@test.dev")
    r = client.post("/api/auth/login", data={"username": "a@test.dev", "password": "wrong-pass"})
    assert r.status_code == 401


def test_normal_user_cannot_call_admin_api(client):
    token = signup(client, "u@test.dev")["access_token"]
    assert client.get("/api/admin/users", headers=auth(token)).status_code == 403
    assert client.get("/api/admin/tasks", headers=auth(token)).status_code == 403
    assert client.patch("/api/admin/users/1/role", json={"role": "admin"}, headers=auth(token)).status_code == 403


def test_no_token_is_401(client):
    assert client.get("/api/tasks").status_code == 401
    assert client.get("/api/admin/users").status_code == 401


def test_admin_can_list_users_and_promote(client):
    user = signup(client, "promote@test.dev")
    admin_token = login(client, "admin@test.dev", "Admin@12345")["access_token"]
    r = client.get("/api/admin/users", headers=auth(admin_token))
    assert r.status_code == 200
    assert {u["email"] for u in r.json()} >= {"admin@test.dev", "promote@test.dev"}

    r = client.patch(f"/api/admin/users/{user['user']['id']}/role", json={"role": "admin"}, headers=auth(admin_token))
    assert r.status_code == 200 and r.json()["role"] == "admin"
    # The promoted user's existing token now works on admin routes, because the role is read from the DB.
    assert client.get("/api/admin/users", headers=auth(user["access_token"])).status_code == 200


def test_duplicate_email_is_rejected(client):
    signup(client, "dup@test.dev")
    r = client.post("/api/auth/signup", json={"email": "DUP@test.dev", "name": "Again", "password": "Password123"})
    assert r.status_code == 409


def test_admin_cannot_change_own_role(client):
    admin = login(client, "admin@test.dev", "Admin@12345")
    r = client.patch(f"/api/admin/users/{admin['user']['id']}/role", json={"role": "user"}, headers=auth(admin["access_token"]))
    assert r.status_code == 400


def test_invalid_status_filter_is_rejected(client):
    token = signup(client, "filter@test.dev")["access_token"]
    assert client.get("/api/tasks?status_filter=bogus", headers=auth(token)).status_code == 422


def test_users_cannot_touch_each_others_tasks(client):
    alice = signup(client, "alice@test.dev")["access_token"]
    bob = signup(client, "bob@test.dev")["access_token"]
    task = client.post("/api/tasks", json={"title": "Alice's task"}, headers=auth(alice)).json()

    assert client.get("/api/tasks", headers=auth(bob)).json() == []
    assert client.patch(f"/api/tasks/{task['id']}", json={"status": "done"}, headers=auth(bob)).status_code == 404
    assert client.delete(f"/api/tasks/{task['id']}", headers=auth(bob)).status_code == 404
    assert client.get("/api/tasks", headers=auth(alice)).json()[0]["status"] == "todo"
