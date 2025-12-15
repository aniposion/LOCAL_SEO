"""Tests for posts endpoints."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.location import Location
from app.models.post import Platform, Post, PostStatus


class TestCreatePost:
    """Tests for post creation."""

    def test_create_post_success(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        test_location: Location,
    ) -> None:
        """Test successful post creation."""
        response = client.post(
            "/posts",
            headers=auth_headers,
            json={
                "location_id": str(test_location.id),
                "platform": "GBP",
                "title": "Test Post",
                "body": "This is a test post body",
                "hashtags": ["test", "local"],
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "Test Post"
        assert data["platform"] == "GBP"
        assert data["status"] == "draft"

    def test_create_post_invalid_location(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        """Test post creation with invalid location."""
        from uuid import uuid4

        response = client.post(
            "/posts",
            headers=auth_headers,
            json={
                "location_id": str(uuid4()),
                "platform": "GBP",
                "title": "Test Post",
            },
        )
        assert response.status_code == 404


class TestListPosts:
    """Tests for listing posts."""

    def test_list_posts_empty(
        self, client: TestClient, auth_headers: dict[str, str], test_location: Location
    ) -> None:
        """Test listing posts when none exist."""
        response = client.get(
            f"/posts?location_id={test_location.id}",
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert response.json() == []

    def test_list_posts_with_filter(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        test_location: Location,
        db: Session,
    ) -> None:
        """Test listing posts with platform filter."""
        # Create test posts
        from uuid import uuid4

        post1 = Post(
            id=uuid4(),
            location_id=test_location.id,
            platform=Platform.GBP,
            status=PostStatus.DRAFT,
            title="GBP Post",
        )
        post2 = Post(
            id=uuid4(),
            location_id=test_location.id,
            platform=Platform.INSTAGRAM,
            status=PostStatus.DRAFT,
            title="IG Post",
        )
        db.add_all([post1, post2])
        db.commit()

        # Filter by platform
        response = client.get(
            f"/posts?location_id={test_location.id}&platform=GBP",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["platform"] == "GBP"


class TestUpdatePost:
    """Tests for updating posts."""

    def test_update_post_success(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        test_location: Location,
        db: Session,
    ) -> None:
        """Test updating a post."""
        from uuid import uuid4

        post = Post(
            id=uuid4(),
            location_id=test_location.id,
            platform=Platform.GBP,
            status=PostStatus.DRAFT,
            title="Original Title",
        )
        db.add(post)
        db.commit()

        response = client.patch(
            f"/posts/{post.id}",
            headers=auth_headers,
            json={"title": "Updated Title", "status": "queued"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Updated Title"
        assert data["status"] == "queued"


class TestDeletePost:
    """Tests for deleting posts."""

    def test_delete_post_success(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        test_location: Location,
        db: Session,
    ) -> None:
        """Test deleting a post."""
        from uuid import uuid4

        post = Post(
            id=uuid4(),
            location_id=test_location.id,
            platform=Platform.GBP,
            status=PostStatus.DRAFT,
        )
        db.add(post)
        db.commit()

        response = client.delete(
            f"/posts/{post.id}",
            headers=auth_headers,
        )
        assert response.status_code == 204
