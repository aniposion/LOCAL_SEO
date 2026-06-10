"""Tests for authentication endpoints."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.account import Account
from app.models.subscription import PlanType, Subscription


def valid_signup_payload(email: str) -> dict:
    """Return a payload that matches the current signup contract."""
    return {
        "email": email,
        "password": "Securepass1!",
        "full_name": "Test Owner",
        "company_name": "Test Co",
        "phone": "555-111-2222",
        "timezone": "UTC",
        "language": "en",
        "accept_terms": True,
        "accept_privacy": True,
    }


class TestSignup:
    """Tests for signup endpoint."""

    def test_signup_success(self, client: TestClient, db: Session) -> None:
        """Test successful user signup."""
        email = "newuser@example.com"
        response = client.post(
            "/auth/signup",
            json=valid_signup_payload(email),
        )
        assert response.status_code == 201
        data = response.json()
        assert "access_token" in data
        assert data["refresh_token"] is None
        assert data["token_type"] == "bearer"
        assert client.cookies.get("refresh_token") is not None

        account = db.query(Account).filter(Account.email == email).first()
        assert account is not None

        subscription = db.query(Subscription).filter(Subscription.account_id == account.id).first()
        assert subscription is not None
        assert subscription.plan_type == PlanType.FREE
        assert subscription.locations_limit == 1
        assert subscription.posts_per_month == 0
        assert subscription.api_calls_per_day == 1000

    def test_signup_duplicate_email(self, client: TestClient, test_user: Account) -> None:
        """Test signup with existing email."""
        response = client.post(
            "/auth/signup",
            json=valid_signup_payload(test_user.email),
        )
        assert response.status_code == 400
        assert "already registered" in response.json()["detail"]

    def test_signup_invalid_email(self, client: TestClient) -> None:
        """Test signup with invalid email."""
        response = client.post(
            "/auth/signup",
            json={**valid_signup_payload("placeholder@example.com"), "email": "invalid-email"},
        )
        assert response.status_code == 422

    def test_signup_short_password(self, client: TestClient) -> None:
        """Test signup with too short password."""
        response = client.post(
            "/auth/signup",
            json={**valid_signup_payload("user@example.com"), "password": "short"},
        )
        assert response.status_code == 422


class TestLogin:
    """Tests for login endpoint."""

    def test_login_success(self, client: TestClient, test_user: Account) -> None:
        """Test successful login."""
        response = client.post(
            "/auth/login",
            json={"email": test_user.email, "password": "testpassword123"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["refresh_token"] is None
        assert client.cookies.get("refresh_token") is not None
        assert "Path=/" in response.headers["set-cookie"]

    def test_login_wrong_password(self, client: TestClient, test_user: Account) -> None:
        """Test login with wrong password."""
        response = client.post(
            "/auth/login",
            json={"email": test_user.email, "password": "wrongpassword"},
        )
        assert response.status_code == 401

    def test_login_nonexistent_user(self, client: TestClient) -> None:
        """Test login with non-existent user."""
        response = client.post(
            "/auth/login",
            json={"email": "nonexistent@example.com", "password": "password123"},
        )
        assert response.status_code == 401


class TestRefresh:
    """Tests for token refresh endpoint."""

    def test_refresh_success(self, client: TestClient, test_user: Account) -> None:
        """Test successful token refresh using the httpOnly cookie."""
        client.post(
            "/auth/login",
            json={"email": test_user.email, "password": "testpassword123"},
        )

        # Refresh token
        response = client.post("/auth/refresh")
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["refresh_token"] is None
        assert client.cookies.get("refresh_token") is not None

    def test_login_uses_configured_refresh_cookie_path(
        self,
        client: TestClient,
        test_user: Account,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Refresh-cookie path should be configurable for proxy-prefixed public APIs."""
        monkeypatch.setattr(settings, "auth_cookie_path", "/api/v1/auth")

        response = client.post(
            "/auth/login",
            json={"email": test_user.email, "password": "testpassword123"},
        )

        assert response.status_code == 200
        assert "Path=/api/v1/auth" in response.headers["set-cookie"]

    def test_refresh_accepts_refresh_token_body_for_transition_compatibility(
        self,
        client: TestClient,
        test_user: Account,
    ) -> None:
        """Test refresh still accepts a refresh token body during the transition."""
        login_response = client.post(
            "/auth/login",
            json={"email": test_user.email, "password": "testpassword123"},
        )
        refresh_token = login_response.cookies.get("refresh_token")

        client.cookies.clear()
        response = client.post("/auth/refresh", json={"refresh_token": refresh_token})

        assert response.status_code == 200
        assert response.json()["access_token"]
        assert client.cookies.get("refresh_token") is not None

    def test_refresh_invalid_token(self, client: TestClient) -> None:
        """Test refresh with invalid token."""
        response = client.post(
            "/auth/refresh",
            json={"refresh_token": "invalid-token"},
        )
        assert response.status_code == 401

    def test_logout_clears_refresh_cookie(self, client: TestClient, test_user: Account) -> None:
        """Test logout clears the refresh cookie."""
        client.post(
            "/auth/login",
            json={"email": test_user.email, "password": "testpassword123"},
        )

        assert client.cookies.get("refresh_token") is not None

        response = client.post("/auth/logout")

        assert response.status_code == 204
        assert client.cookies.get("refresh_token") is None
