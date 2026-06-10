from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from shutil import rmtree
from uuid import uuid4

from app.models.billing import BillingAuditAction, BillingAuditLog
from app.models.post import Platform, Post, PostStatus
from app.models.upload import UploadAsset
from app.services.upload_migration import UploadMigrationService


class _StorageStub:
    def __init__(self) -> None:
        self.uploaded: list[tuple[str, str, str]] = []

    def is_configured(self) -> bool:
        return True

    def upload_from_file(self, file_path: str, destination_name: str, content_type: str = "application/octet-stream") -> str:
        self.uploaded.append((file_path, destination_name, content_type))
        return f"https://storage.googleapis.com/test-bucket/{destination_name}"


def _workspace_upload_root() -> Path:
    root = Path(".codex-run") / "upload-migration-tests" / str(uuid4()) / "uploads"
    root.mkdir(parents=True, exist_ok=True)
    return root


def test_upload_migration_service_dry_run_reports_candidates_without_mutating(db, test_user, test_location):
    upload_root = _workspace_upload_root()
    try:
        (upload_root / "images").mkdir(parents=True)
        (upload_root / "documents").mkdir(parents=True)
        (upload_root / "images" / "legacy-hero.png").write_bytes(b"asset")
        (upload_root / "images" / "post-image.png").write_bytes(b"post")
        (upload_root / "documents" / "invoice.pdf").write_bytes(b"invoice")

        now = datetime.now(UTC)
        asset = UploadAsset(
            account_id=test_user.id,
            file_type="image",
            filename="legacy-hero.png",
            original_filename="legacy-hero.png",
            mime_type="image/png",
            size_bytes=32,
            url="http://localhost:8000/uploads/images/legacy-hero.png",
            storage_key="uploads/images/legacy-hero.png",
            created_at=now,
        )
        post = Post(
            location_id=test_location.id,
            platform=Platform.GBP,
            status=PostStatus.DRAFT,
            title="Legacy post",
            body="Body",
            image_url="/uploads/images/post-image.png",
            created_at=now,
        )
        audit = BillingAuditLog(
            account_id=test_user.id,
            action=BillingAuditAction.DISPUTE_UPDATED,
            entity_type="dispute",
            entity_id="dp_dry_run",
            description="Legacy attachment references",
            extra_data={"attachment_urls": ["http://localhost:8000/uploads/documents/invoice.pdf"]},
            created_at=now,
        )
        db.add_all([asset, post, audit])
        db.commit()

        service = UploadMigrationService(db, upload_root=upload_root, storage_service=_StorageStub())
        result = service.run(apply=False)

        assert result.apply is False
        assert result.matching_total == 3
        assert result.candidate_total == 3
        assert result.migrated_total == 0
        assert result.error_total == 0
        assert result.missing_local_file_total == 0
        assert result.batch_offset == 0
        assert result.batch_limit is None
        assert result.has_more is False
        assert result.next_offset is None
        assert result.verification_performed is False
        assert result.verification_checked_total == 0
        assert result.verification_failed_total == 0
        assert result.verification_failures == []
        assert result.source_totals == {
            "billing_attachment": 1,
            "post": 1,
            "upload_asset": 1,
        }
        assert result.cleanup_candidate_total == 3
        assert {
            item.relative_path for item in result.cleanup_candidates
        } == {
            "documents/invoice.pdf",
            "images/legacy-hero.png",
            "images/post-image.png",
        }
        assert all(
            item.reason == "All persisted references would point at cloud storage URLs after this batch applies."
            for item in result.cleanup_candidates
        )
        assert all(item.status == "planned" for item in result.results)

        db.refresh(asset)
        db.refresh(post)
        db.refresh(audit)
        assert asset.url == "http://localhost:8000/uploads/images/legacy-hero.png"
        assert post.image_url == "/uploads/images/post-image.png"
        assert audit.extra_data["attachment_urls"][0] == "http://localhost:8000/uploads/documents/invoice.pdf"
    finally:
        rmtree(upload_root.parent, ignore_errors=True)


def test_upload_migration_service_apply_updates_db_references(db, test_user, test_location):
    upload_root = _workspace_upload_root()
    try:
        (upload_root / "images").mkdir(parents=True)
        (upload_root / "documents").mkdir(parents=True)
        (upload_root / "images" / "legacy-hero.png").write_bytes(b"asset")
        (upload_root / "images" / "generated-image.png").write_bytes(b"ai-image")
        (upload_root / "documents" / "invoice.pdf").write_bytes(b"invoice")

        now = datetime.now(UTC)
        asset = UploadAsset(
            account_id=test_user.id,
            file_type="image",
            filename="legacy-hero.png",
            original_filename="legacy-hero.png",
            mime_type="image/png",
            size_bytes=32,
            url="http://localhost:8000/uploads/images/legacy-hero.png",
            storage_key="uploads/images/legacy-hero.png",
            created_at=now,
        )
        post = Post(
            location_id=test_location.id,
            platform=Platform.GBP,
            status=PostStatus.DRAFT,
            title="Legacy AI image",
            body="Body",
            ai_image_url="/uploads/images/generated-image.png",
            created_at=now,
        )
        audit = BillingAuditLog(
            account_id=test_user.id,
            action=BillingAuditAction.DISPUTE_UPDATED,
            entity_type="dispute",
            entity_id="dp_apply",
            description="Legacy attachment references",
            extra_data={"attachment_urls": ["http://localhost:8000/uploads/documents/invoice.pdf"]},
            created_at=now,
        )
        db.add_all([asset, post, audit])
        db.commit()

        storage = _StorageStub()
        service = UploadMigrationService(db, upload_root=upload_root, storage_service=storage)
        result = service.run(apply=True)

        assert result.apply is True
        assert result.matching_total == 3
        assert result.candidate_total == 3
        assert result.migrated_total == 3
        assert result.error_total == 0
        assert result.missing_local_file_total == 0
        assert result.cleanup_candidate_total == 3
        assert result.verification_performed is True
        assert result.verification_checked_total == 3
        assert result.verification_failed_total == 0
        assert result.verification_failures == []
        assert len(storage.uploaded) == 3
        assert {
            item.relative_path for item in result.cleanup_candidates
        } == {
            "documents/invoice.pdf",
            "images/generated-image.png",
            "images/legacy-hero.png",
        }
        assert all(item.reason == "All persisted references now point at cloud storage URLs." for item in result.cleanup_candidates)

        db.refresh(asset)
        db.refresh(post)
        db.refresh(audit)
        assert asset.url == "https://storage.googleapis.com/test-bucket/uploads/images/legacy-hero.png"
        assert asset.storage_key == "uploads/images/legacy-hero.png"
        assert post.ai_image_url == "https://storage.googleapis.com/test-bucket/uploads/images/generated-image.png"
        assert audit.extra_data["attachment_urls"][0] == "https://storage.googleapis.com/test-bucket/uploads/documents/invoice.pdf"
    finally:
        rmtree(upload_root.parent, ignore_errors=True)


def test_upload_migration_service_marks_missing_local_files(db, test_user):
    upload_root = _workspace_upload_root()
    try:
        (upload_root / "documents").mkdir(parents=True)

        asset = UploadAsset(
            account_id=test_user.id,
            file_type="document",
            filename="missing-proof.pdf",
            original_filename="missing-proof.pdf",
            mime_type="application/pdf",
            size_bytes=10,
            url="http://localhost:8000/uploads/documents/missing-proof.pdf",
            storage_key="uploads/documents/missing-proof.pdf",
        )
        db.add(asset)
        db.commit()

        service = UploadMigrationService(db, upload_root=upload_root, storage_service=_StorageStub())
        result = service.run(apply=False)

        assert result.matching_total == 1
        assert result.candidate_total == 1
        assert result.missing_local_file_total == 1
        assert result.cleanup_candidate_total == 0
        assert result.results[0].status == "missing_local_file"
    finally:
        rmtree(upload_root.parent, ignore_errors=True)


def test_upload_migration_service_apply_reports_verification_failures_for_remaining_local_refs(db, test_user):
    upload_root = _workspace_upload_root()
    try:
        (upload_root / "documents").mkdir(parents=True)

        asset = UploadAsset(
            account_id=test_user.id,
            file_type="document",
            filename="missing-proof.pdf",
            original_filename="missing-proof.pdf",
            mime_type="application/pdf",
            size_bytes=10,
            url="http://localhost:8000/uploads/documents/missing-proof.pdf",
            storage_key="uploads/documents/missing-proof.pdf",
        )
        db.add(asset)
        db.commit()

        service = UploadMigrationService(db, upload_root=upload_root, storage_service=_StorageStub())
        result = service.run(apply=True)

        assert result.matching_total == 1
        assert result.candidate_total == 1
        assert result.missing_local_file_total == 1
        assert result.verification_performed is True
        assert result.verification_checked_total == 1
        assert result.verification_failed_total == 1
        failure = result.verification_failures[0]
        assert failure.source_type == "upload_asset"
        assert failure.field_name == "url"
        assert failure.original_url == "http://localhost:8000/uploads/documents/missing-proof.pdf"
        assert failure.current_url == "http://localhost:8000/uploads/documents/missing-proof.pdf"
        assert "local /uploads URL" in failure.reason
    finally:
        rmtree(upload_root.parent, ignore_errors=True)


def test_upload_migration_service_cleanup_manifest_waits_for_remaining_refs(db, test_user, test_location):
    upload_root = _workspace_upload_root()
    try:
        (upload_root / "images").mkdir(parents=True)
        shared_file = upload_root / "images" / "shared.png"
        shared_file.write_bytes(b"shared")

        now = datetime.now(UTC)
        first_post = Post(
            location_id=test_location.id,
            platform=Platform.GBP,
            status=PostStatus.DRAFT,
            title="First legacy image",
            body="Body",
            image_url="/uploads/images/shared.png",
            created_at=now,
        )
        second_post = Post(
            location_id=test_location.id,
            platform=Platform.GBP,
            status=PostStatus.DRAFT,
            title="Second legacy image",
            body="Body",
            image_url="/uploads/images/shared.png",
            created_at=now,
        )
        db.add_all([first_post, second_post])
        db.commit()

        storage = _StorageStub()
        service = UploadMigrationService(db, upload_root=upload_root, storage_service=storage)
        result = service.run(apply=True, entity_ids=[str(first_post.id)])

        assert result.migrated_total == 1
        assert result.cleanup_candidate_total == 0
    finally:
        rmtree(upload_root.parent, ignore_errors=True)


def test_upload_migration_service_dry_run_cleanup_preview_waits_for_remaining_refs(db, test_user, test_location):
    upload_root = _workspace_upload_root()
    try:
        (upload_root / "images").mkdir(parents=True)
        shared_file = upload_root / "images" / "shared-preview.png"
        shared_file.write_bytes(b"shared")

        now = datetime.now(UTC)
        first_post = Post(
            location_id=test_location.id,
            platform=Platform.GBP,
            status=PostStatus.DRAFT,
            title="First legacy image",
            body="Body",
            image_url="/uploads/images/shared-preview.png",
            created_at=now,
        )
        second_post = Post(
            location_id=test_location.id,
            platform=Platform.GBP,
            status=PostStatus.DRAFT,
            title="Second legacy image",
            body="Body",
            image_url="/uploads/images/shared-preview.png",
            created_at=now,
        )
        db.add_all([first_post, second_post])
        db.commit()

        service = UploadMigrationService(db, upload_root=upload_root, storage_service=_StorageStub())
        result = service.run(apply=False, entity_ids=[str(first_post.id)])

        assert result.candidate_total == 1
        assert result.results[0].status == "planned"
        assert result.cleanup_candidate_total == 0
        assert result.cleanup_candidates == []
    finally:
        rmtree(upload_root.parent, ignore_errors=True)


def test_upload_migration_service_supports_offset_batches(db, test_user, test_location):
    upload_root = _workspace_upload_root()
    try:
        (upload_root / "images").mkdir(parents=True)
        (upload_root / "documents").mkdir(parents=True)
        (upload_root / "images" / "legacy-hero.png").write_bytes(b"asset")
        (upload_root / "images" / "generated-image.png").write_bytes(b"ai-image")
        (upload_root / "documents" / "invoice.pdf").write_bytes(b"invoice")

        now = datetime.now(UTC)
        asset = UploadAsset(
            account_id=test_user.id,
            file_type="image",
            filename="legacy-hero.png",
            original_filename="legacy-hero.png",
            mime_type="image/png",
            size_bytes=32,
            url="http://localhost:8000/uploads/images/legacy-hero.png",
            storage_key="uploads/images/legacy-hero.png",
            created_at=now,
        )
        post = Post(
            location_id=test_location.id,
            platform=Platform.GBP,
            status=PostStatus.DRAFT,
            title="Legacy AI image",
            body="Body",
            ai_image_url="/uploads/images/generated-image.png",
            created_at=now,
        )
        audit = BillingAuditLog(
            account_id=test_user.id,
            action=BillingAuditAction.DISPUTE_UPDATED,
            entity_type="dispute",
            entity_id="dp_offset",
            description="Legacy attachment references",
            extra_data={"attachment_urls": ["http://localhost:8000/uploads/documents/invoice.pdf"]},
            created_at=now,
        )
        db.add_all([asset, post, audit])
        db.commit()

        service = UploadMigrationService(db, upload_root=upload_root, storage_service=_StorageStub())
        result = service.run(apply=False, offset=1, limit=1)

        assert result.matching_total == 3
        assert result.candidate_total == 1
        assert result.batch_offset == 1
        assert result.batch_limit == 1
        assert result.has_more is True
        assert result.next_offset == 2
        assert result.cleanup_candidate_total == 1
        assert result.results[0].status == "planned"
    finally:
        rmtree(upload_root.parent, ignore_errors=True)
