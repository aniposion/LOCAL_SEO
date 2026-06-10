"""Tests for auth rate limiting and production upload safeguards."""

from datetime import UTC, datetime, timedelta
from io import BytesIO
from pathlib import Path
from uuid import uuid4

from app.core.config import settings
from app.models.auth_rate_limit import AuthRateLimitBucket
from app.models.post import Platform, Post
from app.models.upload import UploadAsset


def _png_bytes() -> bytes:
    return (
        b"\x89PNG\r\n\x1a\n"
        b"\x00\x00\x00\rIHDR"
        b"\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00"
        b"\x90wS\xde\x00\x00\x00\x0cIDAT\x08\xd7c\xf8\xff\xff?\x00\x05\xfe\x02\xfeA\xd9\xa5\x1d"
        b"\x00\x00\x00\x00IEND\xaeB`\x82"
    )


def _valid_signup_payload(email: str) -> dict:
    return {
        "email": email,
        "password": "Securepass1!",
        "full_name": "Burst Test",
        "company_name": "Test Co",
        "phone": "555-111-2222",
        "timezone": "UTC",
        "language": "en",
        "accept_terms": True,
        "accept_privacy": True,
    }


def _clear_auth_buckets(db) -> None:
    db.query(AuthRateLimitBucket).delete()
    db.commit()


def test_login_rate_limit_blocks_repeated_attempts(client, db, test_user) -> None:
    """Repeated failed logins should eventually get a 429."""
    _clear_auth_buckets(db)

    payload = {"email": test_user.email, "password": "wrongpassword"}
    responses = [client.post("/auth/login", json=payload) for _ in range(9)]

    assert responses[-1].status_code == 429
    assert "Retry-After" in responses[-1].headers
    assert db.query(AuthRateLimitBucket).filter(AuthRateLimitBucket.action == "login").count() == 2


def test_signup_rate_limit_blocks_repeated_attempts(client, db) -> None:
    """Repeated signup attempts for the same email should be throttled."""
    _clear_auth_buckets(db)
    payload = _valid_signup_payload("burst@example.com")

    responses = [client.post("/auth/signup", json=payload) for _ in range(4)]

    assert responses[-1].status_code == 429
    identity_bucket = (
        db.query(AuthRateLimitBucket)
        .filter(
            AuthRateLimitBucket.action == "signup",
            AuthRateLimitBucket.scope == "identity",
        )
        .first()
    )
    assert identity_bucket is not None
    assert identity_bucket.hit_count == 3


def test_uploads_require_cloud_storage_in_prod(client, auth_headers, monkeypatch) -> None:
    """Production uploads should fail honestly when cloud storage is unavailable."""
    from app.services import storage as storage_module

    monkeypatch.setattr(settings, "app_env", "prod")
    monkeypatch.setattr(settings, "gcs_bucket", None)
    monkeypatch.setattr(settings, "s3_bucket", None)
    storage_module._storage_service = None

    response = client.post(
        "/uploads/image",
        headers=auth_headers,
        files={"file": ("tiny.png", BytesIO(_png_bytes()), "image/png")},
    )

    assert response.status_code == 503
    assert "Cloud storage must be configured" in response.json()["detail"]


def test_uploads_use_cloud_storage_when_configured(client, db, test_user, auth_headers, monkeypatch) -> None:
    """Uploads should return a cloud URL and avoid local-file paths when storage is configured."""

    class _StorageStub:
        def __init__(self) -> None:
            self.uploads: list[tuple[str, str, bytes, str]] = []

        def is_configured(self) -> bool:
            return True

        def upload_file(self, file_data, filename, content_type="application/octet-stream", folder="uploads"):
            self.uploads.append((folder, filename, file_data, content_type))
            return f"https://storage.googleapis.com/test-bucket/{folder}/{filename}"

    storage = _StorageStub()
    monkeypatch.setattr("app.services.file_upload.get_storage_service", lambda: storage)

    response = client.post(
        "/uploads/image",
        headers=auth_headers,
        files={"file": ("tiny.png", BytesIO(_png_bytes()), "image/png")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["url"].startswith("https://storage.googleapis.com/test-bucket/uploads/images/")
    assert storage.uploads[0][0] == "uploads/images"
    assert storage.uploads[0][1] == payload["filename"]
    assert not (Path("uploads") / "images" / payload["filename"]).exists()

    asset = db.query(UploadAsset).filter(UploadAsset.id == payload["id"]).first()
    assert asset is not None
    assert asset.account_id == test_user.id
    assert asset.filename == payload["filename"]
    assert asset.storage_key == f"uploads/images/{payload['filename']}"
    assert asset.url == payload["url"]


def test_delete_uses_cloud_storage_when_configured(client, db, test_user, auth_headers, monkeypatch) -> None:
    """Delete endpoint should remove cloud-backed files by object prefix."""

    class _StorageStub:
        def __init__(self) -> None:
            self.deleted: list[str] = []

        def is_configured(self) -> bool:
            return True

        def list_files(self, prefix="") -> list[str]:
            return [f"{prefix}png"]

        def delete_file(self, blob_name: str) -> bool:
            self.deleted.append(blob_name)
            return True

    storage = _StorageStub()
    monkeypatch.setattr("app.services.file_upload.get_storage_service", lambda: storage)

    asset = UploadAsset(
        id=uuid4(),
        account_id=test_user.id,
        filename="cloud-file-id.png",
        original_filename="cloud-file-id.png",
        file_type="image",
        mime_type="image/png",
        size_bytes=32,
        url="https://storage.googleapis.com/test-bucket/uploads/images/cloud-file-id.png",
        storage_key="uploads/images/cloud-file-id.png",
    )
    db.add(asset)
    db.commit()

    response = client.delete(
        f"/uploads/{asset.id}",
        headers=auth_headers,
        params={"file_type": "image"},
    )

    assert response.status_code == 200
    assert storage.deleted == ["uploads/images/cloud-file-id.png"]
    assert db.query(UploadAsset).filter(UploadAsset.id == asset.id).first() is None


def test_delete_upload_requires_asset_ownership(
    client,
    db,
    other_user,
    auth_headers,
    monkeypatch,
) -> None:
    """Users should not be able to delete another account's uploaded asset."""

    class _StorageStub:
        def __init__(self) -> None:
            self.deleted: list[str] = []

        def is_configured(self) -> bool:
            return True

        def delete_file(self, blob_name: str) -> bool:
            self.deleted.append(blob_name)
            return True

    storage = _StorageStub()
    monkeypatch.setattr("app.services.file_upload.get_storage_service", lambda: storage)

    asset = UploadAsset(
        id=uuid4(),
        account_id=other_user.id,
        filename="foreign-file.png",
        original_filename="foreign-file.png",
        file_type="image",
        mime_type="image/png",
        size_bytes=32,
        url="https://storage.googleapis.com/test-bucket/uploads/images/foreign-file.png",
        storage_key="uploads/images/foreign-file.png",
    )
    db.add(asset)
    db.commit()

    response = client.delete(
        f"/uploads/{asset.id}",
        headers=auth_headers,
        params={"file_type": "image"},
    )

    assert response.status_code == 404
    assert storage.deleted == []
    assert db.query(UploadAsset).filter(UploadAsset.id == asset.id).first() is not None


def test_list_uploads_returns_account_scoped_assets_in_recent_order(client, db, test_user, other_user, auth_headers):
    """List endpoint should only return the current account's assets, newest first."""
    older_asset = UploadAsset(
        id=uuid4(),
        account_id=test_user.id,
        filename="older.png",
        original_filename="older.png",
        file_type="image",
        mime_type="image/png",
        size_bytes=10,
        url="https://storage.googleapis.com/test-bucket/uploads/images/older.png",
        storage_key="uploads/images/older.png",
        created_at=datetime.now(UTC) - timedelta(days=2),
    )
    newer_asset = UploadAsset(
        id=uuid4(),
        account_id=test_user.id,
        filename="newer.png",
        original_filename="newer.png",
        file_type="image",
        mime_type="image/png",
        size_bytes=20,
        url="https://storage.googleapis.com/test-bucket/uploads/images/newer.png",
        storage_key="uploads/images/newer.png",
        created_at=datetime.now(UTC) - timedelta(hours=1),
    )
    foreign_asset = UploadAsset(
        id=uuid4(),
        account_id=other_user.id,
        filename="foreign.png",
        original_filename="foreign.png",
        file_type="image",
        mime_type="image/png",
        size_bytes=30,
        url="https://storage.googleapis.com/test-bucket/uploads/images/foreign.png",
        storage_key="uploads/images/foreign.png",
        created_at=datetime.now(UTC),
    )
    db.add_all([older_asset, newer_asset, foreign_asset])
    db.commit()

    response = client.get("/uploads?file_type=image&limit=10", headers=auth_headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 2
    assert [item["filename"] for item in payload["files"]] == ["newer.png", "older.png"]
    assert all(item["original_filename"] != "foreign.png" for item in payload["files"])
    assert payload["files"][0]["created_at"] is not None


def test_legacy_upload_post_endpoints_create_real_drafts(client, db, auth_headers, test_location) -> None:
    """Legacy upload post endpoints should create real draft posts through the current storage flow."""
    single = client.post(
        "/uploads/post",
        headers=auth_headers,
        data={
            "title": "Legacy upload draft",
            "body": "Body",
            "location_id": str(test_location.id),
            "platforms": "google,instagram",
        },
        files={"image": ("legacy.png", b"fake image bytes", "image/png")},
    )
    assert single.status_code == 200, single.text
    single_payload = single.json()
    assert single_payload["status"] == "draft"
    assert len(single_payload["created_post_ids"]) == 2
    assert single_payload["platforms"] == ["GBP", "INSTAGRAM"]
    assert single_payload["image_attachment_mode"] == "single_image_attached"
    assert len(single_payload["image_urls"]) == 1
    assert single_payload["attached_image_url"] == single_payload["image_urls"][0]
    assert single_payload["legacy_endpoint"] == "/uploads/post"
    assert single_payload["canonical_dashboard_path"] == "/dashboard/content"
    assert single_payload["canonical_primary_post_path"] == f"/dashboard/content/{single_payload['created_post_ids'][0]}"
    assert single_payload["canonical_post_paths"] == [
        f"/dashboard/content/{post_id}"
        for post_id in single_payload["created_post_ids"]
    ]
    assert "Legacy upload endpoint created real draft posts" in single_payload["legacy_notice"]
    assert single.headers["deprecation"] == "true"
    assert single.headers["x-legacy-endpoint"] == "/uploads/post"
    assert single.headers["x-canonical-dashboard-path"] == "/dashboard/content"
    assert single.headers["x-canonical-primary-post-path"] == single_payload["canonical_primary_post_path"]
    assert single.headers["link"] == f"<{single_payload['canonical_primary_post_path']}>; rel=\"alternate\""

    multiple = client.post(
        "/uploads/post/with-images",
        headers=auth_headers,
        data={
            "title": "Legacy multi upload draft",
            "body": "Body",
            "location_id": str(test_location.id),
            "platforms": "google",
        },
        files=[
            ("images", ("legacy-1.png", b"first image", "image/png")),
            ("images", ("legacy-2.png", b"second image", "image/png")),
        ],
    )
    assert multiple.status_code == 200, multiple.text
    multiple_payload = multiple.json()
    assert multiple_payload["status"] == "draft"
    assert len(multiple_payload["created_post_ids"]) == 1
    assert len(multiple_payload["image_urls"]) == 2
    assert multiple_payload["image_attachment_mode"] == "first_image_attached"
    assert multiple_payload["attached_image_url"] == multiple_payload["image_urls"][0]
    assert multiple_payload["legacy_endpoint"] == "/uploads/post/with-images"
    assert multiple_payload["canonical_dashboard_path"] == "/dashboard/content"
    assert multiple_payload["canonical_primary_post_path"] == f"/dashboard/content/{multiple_payload['created_post_ids'][0]}"
    assert multiple_payload["canonical_post_paths"] == [
        f"/dashboard/content/{post_id}"
        for post_id in multiple_payload["created_post_ids"]
    ]
    assert "Content workspace" in multiple_payload["legacy_notice"]
    assert multiple.headers["deprecation"] == "true"
    assert multiple.headers["x-legacy-endpoint"] == "/uploads/post/with-images"
    assert multiple.headers["x-canonical-dashboard-path"] == "/dashboard/content"
    assert multiple.headers["x-canonical-primary-post-path"] == multiple_payload["canonical_primary_post_path"]
    assert multiple.headers["link"] == f"<{multiple_payload['canonical_primary_post_path']}>; rel=\"alternate\""

    stored_posts = db.query(Post).filter(Post.location_id == test_location.id).order_by(Post.created_at.asc()).all()
    assert len(stored_posts) == 3
    assert stored_posts[0].platform == Platform.GBP
    assert stored_posts[1].platform == Platform.INSTAGRAM
    assert stored_posts[2].platform == Platform.GBP
    assert stored_posts[2].image_url == multiple_payload["image_urls"][0]
    assert stored_posts[2].generation_params["legacy_uploaded_image_urls"] == multiple_payload["image_urls"]
