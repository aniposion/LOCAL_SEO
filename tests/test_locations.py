"""Tests for locations endpoints."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.account import Account
from app.models.location import Location


class TestCreateLocation:
    """Tests for location creation."""

    def test_create_location_success(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        """Test successful location creation."""
        response = client.post(
            "/locations",
            headers=auth_headers,
            json={
                "name": "My Business",
                "address": "456 Main St",
                "city": "New York",
                "state": "NY",
                "country": "US",
                "phone": "555-5678",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "My Business"
        assert data["city"] == "New York"
        assert "id" in data

    def test_create_location_unauthorized(self, client: TestClient) -> None:
        """Test location creation without auth."""
        response = client.post(
            "/locations",
            json={"name": "My Business"},
        )
        assert response.status_code == 403


class TestListLocations:
    """Tests for listing locations."""

    def test_list_locations_empty(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        """Test listing locations when none exist."""
        response = client.get("/locations", headers=auth_headers)
        assert response.status_code == 200
        assert response.json() == []

    def test_list_locations_with_data(
        self, client: TestClient, auth_headers: dict[str, str], test_location: Location
    ) -> None:
        """Test listing locations with existing data."""
        response = client.get("/locations", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == test_location.name


class TestGetLocation:
    """Tests for getting a single location."""

    def test_get_location_success(
        self, client: TestClient, auth_headers: dict[str, str], test_location: Location
    ) -> None:
        """Test getting a location by ID."""
        response = client.get(
            f"/locations/{test_location.id}",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == test_location.name

    def test_get_location_not_found(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        """Test getting non-existent location."""
        from uuid import uuid4

        response = client.get(
            f"/locations/{uuid4()}",
            headers=auth_headers,
        )
        assert response.status_code == 404


class TestUpdateLocation:
    """Tests for updating locations."""

    def test_update_location_success(
        self, client: TestClient, auth_headers: dict[str, str], test_location: Location
    ) -> None:
        """Test updating a location."""
        response = client.patch(
            f"/locations/{test_location.id}",
            headers=auth_headers,
            json={"name": "Updated Business Name"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Business Name"


class TestDeleteLocation:
    """Tests for deleting locations."""

    def test_delete_location_success(
        self, client: TestClient, auth_headers: dict[str, str], test_location: Location
    ) -> None:
        """Test deleting a location."""
        response = client.delete(
            f"/locations/{test_location.id}",
            headers=auth_headers,
        )
        assert response.status_code == 204

        # Verify deletion
        response = client.get(
            f"/locations/{test_location.id}",
            headers=auth_headers,
        )
        assert response.status_code == 404
