"""Tests for authentication endpoints."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.account import Account


class TestSignup:
    """Tests for signup endpoint."""

    def test_signup_success(self, client: TestClient) -> None:
        """Test successful user signup."""
        response = client.post(
            "/auth/signup",
            json={"email": "newuser@example.com", "password": "securepassword123"},
        )
        assert response.status_code == 201
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    def test_signup_duplicate_email(self, client: TestClient, test_user: Account) -> None:
        """Test signup with existing email."""
        response = client.post(
            "/auth/signup",
            json={"email": test_user.email, "password": "securepassword123"},
        )
        assert response.status_code == 400
        assert "already registered" in response.json()["detail"]

    def test_signup_invalid_email(self, client: TestClient) -> None:
        """Test signup with invalid email."""
        response = client.post(
            "/auth/signup",
            json={"email": "invalid-email", "password": "securepassword123"},
        )
        assert response.status_code == 422

    def test_signup_short_password(self, client: TestClient) -> None:
        """Test signup with too short password."""
        response = client.post(
            "/auth/signup",
            json={"email": "user@example.com", "password": "short"},
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
        assert "refresh_token" in data

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
        """Test successful token refresh."""
        # First login to get tokens
        login_response = client.post(
            "/auth/login",
            json={"email": test_user.email, "password": "testpassword123"},
        )
        refresh_token = login_response.json()["refresh_token"]

        # Refresh token
        response = client.post(
            "/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data

    def test_refresh_invalid_token(self, client: TestClient) -> None:
        """Test refresh with invalid token."""
        response = client.post(
            "/auth/refresh",
            json={"refresh_token": "invalid-token"},
        )
        assert response.status_code == 401
