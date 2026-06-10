"""Tests for locations endpoints."""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.account import Account
from app.models.channel import Channel, ChannelStatus, ChannelType
from app.models.location import Location
from app.models.post import Platform, Post, PostStatus
from app.models.publish_job import PublishJob, PublishJobStatus


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
        assert response.status_code == 401


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

    def test_list_locations_includes_instagram_reconnect_status(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        test_location: Location,
        db: Session,
    ) -> None:
        """Instagram channel expiry should surface as reconnect required."""
        from uuid import uuid4

        channel = Channel(
            id=uuid4(),
            location_id=test_location.id,
            type=ChannelType.INSTAGRAM,
            status=ChannelStatus.CONNECTED,
            is_active=True,
            access_token_expires_at=datetime.now(UTC) - timedelta(minutes=1),
        )
        channel.set_credentials({"access_token": "ig-token", "ig_user_id": "ig-user-123"})
        db.add(channel)
        db.commit()

        response = client.get("/locations", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data[0]["instagram_connected"] is False
        assert data[0]["instagram_status"] == "reconnect required"


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


class TestChannels:
    """Tests for channel diagnostics."""

    def test_list_channels_includes_recent_publish_health(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        test_location: Location,
        db: Session,
    ) -> None:
        """Channel list should expose last failure and last success timestamps."""
        from uuid import uuid4

        channel = Channel(
            id=uuid4(),
            location_id=test_location.id,
            type=ChannelType.INSTAGRAM,
            status=ChannelStatus.ERROR,
            is_active=True,
            access_token_expires_at=datetime.now(UTC) + timedelta(days=7),
        )
        channel.set_credentials({"access_token": "ig-token", "ig_user_id": "ig-user-123"})

        post = Post(
            id=uuid4(),
            location_id=test_location.id,
            platform=Platform.INSTAGRAM,
            status=PostStatus.FAILED,
            title="Instagram post",
        )
        failed_job = PublishJob(
            id=uuid4(),
            post_id=post.id,
            platform="INSTAGRAM",
            status=PublishJobStatus.FAILED,
            last_error="rate limit",
            created_at=datetime.now(UTC) - timedelta(hours=2),
        )
        success_job = PublishJob(
            id=uuid4(),
            post_id=post.id,
            platform="INSTAGRAM",
            status=PublishJobStatus.COMPLETED,
            completed_at=datetime.now(UTC) - timedelta(hours=1),
            created_at=datetime.now(UTC) - timedelta(hours=1, minutes=5),
        )

        db.add_all([channel, post, failed_job, success_job])
        db.commit()

        response = client.get(f"/locations/{test_location.id}/channels", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["type"] == "INSTAGRAM"
        assert data[0]["status"] == "error"
        assert data[0]["last_publish_failed_error"] == "rate limit"
        assert data[0]["last_publish_failed_at"] is not None
        assert data[0]["last_publish_succeeded_at"] is not None

    def test_get_location_forbidden_other_account(
        self, client: TestClient, auth_headers: dict[str, str], other_location: Location
    ) -> None:
        """Test another account's location is hidden."""
        response = client.get(
            f"/locations/{other_location.id}",
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
            json={
                "name": "Updated Business Name",
                "website_url": "https://updated.example.com",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Business Name"
        assert data["website_url"] == "https://updated.example.com"

    def test_update_location_forbidden_other_account(
        self, client: TestClient, auth_headers: dict[str, str], other_location: Location
    ) -> None:
        """Test another account's location cannot be updated."""
        response = client.patch(
            f"/locations/{other_location.id}",
            headers=auth_headers,
            json={"name": "Hacked Name"},
        )
        assert response.status_code == 404


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
