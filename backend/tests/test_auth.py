"""End-to-end tests for the FastAPI Users auth flow."""

from httpx import AsyncClient


async def test_register_success(client: AsyncClient, credentials: dict[str, str]) -> None:
    response = await client.post("/api/auth/register", json=credentials)
    assert response.status_code == 201, response.text
    data = response.json()
    assert data["email"] == credentials["email"]
    assert data["is_active"] is True
    assert data["is_verified"] is False
    assert data["is_superuser"] is False
    assert "id" in data
    # Secrets must never leak in API responses.
    assert "hashed_password" not in data
    assert "password" not in data


async def test_register_duplicate_email_rejected(
    client: AsyncClient, registered_user: dict[str, str]
) -> None:
    response = await client.post("/api/auth/register", json=registered_user)
    assert response.status_code == 400
    assert response.json()["detail"] == "REGISTER_USER_ALREADY_EXISTS"


async def test_register_invalid_email_422(client: AsyncClient) -> None:
    response = await client.post(
        "/api/auth/register",
        json={"email": "not-an-email", "password": "correct horse battery"},
    )
    assert response.status_code == 422


async def test_register_password_too_short_400(client: AsyncClient) -> None:
    response = await client.post(
        "/api/auth/register",
        json={"email": "alice@example.com", "password": "short"},
    )
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["code"] == "REGISTER_INVALID_PASSWORD"
    assert "8 characters" in detail["reason"]


async def test_login_success_sets_cookie(
    client: AsyncClient, registered_user: dict[str, str]
) -> None:
    response = await client.post(
        "/api/auth/login",
        data={
            "username": registered_user["email"],
            "password": registered_user["password"],
        },
    )
    assert response.status_code == 204
    cookie_header = response.headers.get("set-cookie", "")
    assert "trading_journal_session=" in cookie_header
    assert "HttpOnly" in cookie_header
    assert "trading_journal_session" in client.cookies


async def test_login_wrong_password_400(
    client: AsyncClient, registered_user: dict[str, str]
) -> None:
    response = await client.post(
        "/api/auth/login",
        data={"username": registered_user["email"], "password": "wrong-password"},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "LOGIN_BAD_CREDENTIALS"


async def test_login_unknown_user_400(client: AsyncClient) -> None:
    response = await client.post(
        "/api/auth/login",
        data={"username": "ghost@example.com", "password": "does not matter"},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "LOGIN_BAD_CREDENTIALS"


async def test_me_without_cookie_401(client: AsyncClient) -> None:
    response = await client.get("/api/users/me")
    assert response.status_code == 401


async def test_me_with_cookie_200(
    auth_client: AsyncClient, registered_user: dict[str, str]
) -> None:
    response = await auth_client.get("/api/users/me")
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == registered_user["email"]
    assert data["is_active"] is True
    assert data["last_login_at"] is not None  # updated by on_after_login hook
    assert data["created_at"] is not None


async def test_logout_invalidates_session(
    auth_client: AsyncClient,
) -> None:
    # Sanity: session is alive
    me_before = await auth_client.get("/api/users/me")
    assert me_before.status_code == 200

    logout = await auth_client.post("/api/auth/logout")
    assert logout.status_code == 204

    me_after = await auth_client.get("/api/users/me")
    assert me_after.status_code == 401
