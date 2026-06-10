"""Upload migration helpers for moving legacy local files to cloud storage."""

from __future__ import annotations

import mimetypes
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Iterable
from urllib.parse import urlparse

from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.orm.attributes import flag_modified

from app.models.billing import BillingAuditLog
from app.models.location import Location
from app.models.post import Post
from app.models.upload import UploadAsset
from app.services.storage import CloudStorageService, get_storage_service


def looks_like_local_upload_url(value: str | None) -> bool:
    """Return whether a URL still points at the legacy local uploads path."""
    if not value:
        return False

    candidate = value.strip()
    if not candidate:
        return False

    lowered = candidate.lower()
    if lowered.startswith("/uploads/"):
        return True

    parsed = urlparse(candidate)
    return parsed.hostname in {"localhost", "127.0.0.1"} and parsed.path.startswith("/uploads/")


def relative_upload_path_from_url(url: str) -> PurePosixPath | None:
    """Extract the relative legacy upload path from a local uploads URL."""
    if not looks_like_local_upload_url(url):
        return None

    candidate = url.strip()
    if candidate.lower().startswith("/uploads/"):
        return PurePosixPath(candidate[len("/uploads/") :])

    parsed = urlparse(candidate)
    return PurePosixPath(parsed.path[len("/uploads/") :])


@dataclass
class UploadMigrationCandidate:
    source_type: str
    entity_id: str
    field_name: str
    original_url: str
    destination_key: str | None
    local_path: Path | None
    mime_type: str | None


@dataclass
class UploadMigrationItemResult:
    source_type: str
    entity_id: str
    field_name: str
    original_url: str
    destination_key: str | None
    status: str
    migrated_url: str | None = None
    message: str | None = None


@dataclass
class UploadCleanupCandidate:
    local_path: str
    relative_path: str
    destination_keys: list[str]
    migrated_urls: list[str]
    reference_count: int
    reference_fields: list[str]
    reason: str


@dataclass
class UploadMigrationVerificationFailure:
    source_type: str
    entity_id: str
    field_name: str
    original_url: str
    current_url: str | None
    reason: str


@dataclass
class UploadMigrationRunResult:
    apply: bool
    matching_total: int
    candidate_total: int
    processed_total: int
    migrated_total: int
    missing_local_file_total: int
    skipped_total: int
    error_total: int
    batch_offset: int
    batch_limit: int | None
    has_more: bool
    next_offset: int | None
    source_totals: dict[str, int]
    cleanup_candidate_total: int
    cleanup_candidates: list[UploadCleanupCandidate]
    verification_performed: bool
    verification_checked_total: int
    verification_failed_total: int
    verification_failures: list[UploadMigrationVerificationFailure]
    results: list[UploadMigrationItemResult]

    def to_dict(self) -> dict:
        return asdict(self)


class UploadMigrationService:
    """Migrate legacy `/uploads/...` references to configured cloud storage."""

    def __init__(
        self,
        db: Session,
        *,
        upload_root: str | Path = "uploads",
        storage_service: CloudStorageService | None = None,
    ) -> None:
        self.db = db
        self.upload_root = Path(upload_root)
        self.storage = storage_service or get_storage_service()

    def _candidate_from_upload_asset(self, asset: UploadAsset) -> UploadMigrationCandidate | None:
        if not looks_like_local_upload_url(asset.url):
            return None
        relative_path = relative_upload_path_from_url(asset.url)
        if relative_path is None:
            return None
        destination_key = asset.storage_key or f"uploads/{relative_path.as_posix()}"
        return UploadMigrationCandidate(
            source_type="upload_asset",
            entity_id=str(asset.id),
            field_name="url",
            original_url=asset.url,
            destination_key=destination_key,
            local_path=self.upload_root / Path(relative_path.as_posix()),
            mime_type=asset.mime_type,
        )

    def _candidate_from_post(self, post: Post, field_name: str, url: str | None) -> UploadMigrationCandidate | None:
        if not looks_like_local_upload_url(url):
            return None
        relative_path = relative_upload_path_from_url(url or "")
        if relative_path is None:
            return None
        mime_type = mimetypes.guess_type(relative_path.name)[0] or "application/octet-stream"
        return UploadMigrationCandidate(
            source_type="post",
            entity_id=str(post.id),
            field_name=field_name,
            original_url=url or "",
            destination_key=f"uploads/{relative_path.as_posix()}",
            local_path=self.upload_root / Path(relative_path.as_posix()),
            mime_type=mime_type,
        )

    def _candidate_from_billing_attachment(self, audit: BillingAuditLog, url: str) -> UploadMigrationCandidate | None:
        if not looks_like_local_upload_url(url):
            return None
        relative_path = relative_upload_path_from_url(url)
        if relative_path is None:
            return None
        mime_type = mimetypes.guess_type(relative_path.name)[0] or "application/octet-stream"
        return UploadMigrationCandidate(
            source_type="billing_attachment",
            entity_id=str(audit.id),
            field_name="attachment_urls",
            original_url=url,
            destination_key=f"uploads/{relative_path.as_posix()}",
            local_path=self.upload_root / Path(relative_path.as_posix()),
            mime_type=mime_type,
        )

    def scan_candidates(
        self,
        *,
        source_types: Iterable[str] | None = None,
        entity_ids: Iterable[str] | None = None,
        offset: int = 0,
        limit: int | None = None,
    ) -> tuple[list[UploadMigrationCandidate], int, dict[str, int]]:
        """Collect legacy upload references that can be migrated."""
        allowed_sources = {value for value in (source_types or []) if value} or None
        allowed_ids = {value for value in (entity_ids or []) if value} or None
        candidates: list[UploadMigrationCandidate] = []

        def _take(candidate: UploadMigrationCandidate | None) -> None:
            if candidate is None:
                return
            if allowed_sources and candidate.source_type not in allowed_sources:
                return
            if allowed_ids and candidate.entity_id not in allowed_ids:
                return
            candidates.append(candidate)

        if allowed_sources is None or "upload_asset" in allowed_sources:
            upload_assets = self.db.query(UploadAsset).order_by(UploadAsset.created_at.desc()).all()
            for asset in upload_assets:
                _take(self._candidate_from_upload_asset(asset))

        if allowed_sources is None or "post" in allowed_sources:
            posts = (
                self.db.query(Post)
                .options(joinedload(Post.location).joinedload(Location.account))
                .filter(or_(Post.image_url.isnot(None), Post.ai_image_url.isnot(None)))
                .order_by(Post.created_at.desc())
                .all()
            )
            for post in posts:
                _take(self._candidate_from_post(post, "image_url", post.image_url))
                _take(self._candidate_from_post(post, "ai_image_url", post.ai_image_url))

        if allowed_sources is None or "billing_attachment" in allowed_sources:
            audits = (
                self.db.query(BillingAuditLog)
                .filter(BillingAuditLog.extra_data.isnot(None))
                .order_by(BillingAuditLog.created_at.desc())
                .all()
            )
            for audit in audits:
                payload = audit.extra_data if isinstance(audit.extra_data, dict) else {}
                attachment_urls = payload.get("attachment_urls")
                if not isinstance(attachment_urls, list):
                    continue
                for url in attachment_urls:
                    _take(self._candidate_from_billing_attachment(audit, url))

        matching_total = len(candidates)
        source_totals: dict[str, int] = {}
        for candidate in candidates:
            source_totals[candidate.source_type] = source_totals.get(candidate.source_type, 0) + 1

        safe_offset = max(offset, 0)
        if safe_offset:
            candidates = candidates[safe_offset:]
        if limit is not None:
            candidates = candidates[:limit]

        return candidates, matching_total, source_totals

    def _require_storage_for_apply(self) -> None:
        if not self.storage.is_configured():
            raise RuntimeError("Cloud storage must be configured before applying upload migration.")

    def _upload_candidate_file(self, candidate: UploadMigrationCandidate) -> str:
        assert candidate.local_path is not None
        assert candidate.destination_key is not None
        return self.storage.upload_from_file(
            str(candidate.local_path),
            candidate.destination_key,
            candidate.mime_type or "application/octet-stream",
        )

    def _apply_upload_asset(self, candidate: UploadMigrationCandidate, cloud_url: str) -> None:
        asset = self.db.query(UploadAsset).filter(UploadAsset.id == candidate.entity_id).first()
        if asset is None:
            raise RuntimeError("UploadAsset no longer exists.")
        asset.url = cloud_url
        asset.storage_key = candidate.destination_key

    def _apply_post(self, candidate: UploadMigrationCandidate, cloud_url: str) -> None:
        post = self.db.query(Post).filter(Post.id == candidate.entity_id).first()
        if post is None:
            raise RuntimeError("Post no longer exists.")
        if candidate.field_name == "image_url":
            post.image_url = cloud_url
        elif candidate.field_name == "ai_image_url":
            post.ai_image_url = cloud_url
        else:
            raise RuntimeError(f"Unsupported post field: {candidate.field_name}")

    def _apply_billing_attachment(self, candidate: UploadMigrationCandidate, cloud_url: str) -> None:
        audit = self.db.query(BillingAuditLog).filter(BillingAuditLog.id == candidate.entity_id).first()
        if audit is None:
            raise RuntimeError("BillingAuditLog no longer exists.")
        payload = audit.extra_data if isinstance(audit.extra_data, dict) else {}
        attachment_urls = payload.get("attachment_urls")
        if not isinstance(attachment_urls, list):
            raise RuntimeError("Billing audit no longer has attachment_urls.")
        payload["attachment_urls"] = [cloud_url if value == candidate.original_url else value for value in attachment_urls]
        audit.extra_data = payload
        flag_modified(audit, "extra_data")

    def _build_cleanup_candidates(
        self,
        candidates: list[UploadMigrationCandidate],
        results: list[UploadMigrationItemResult],
        *,
        simulate: bool = False,
    ) -> list[UploadCleanupCandidate]:
        eligible_statuses = {"planned"} if simulate else {"migrated"}
        migrated_by_path: dict[str, dict[str, object]] = {}
        simulated_candidate_keys = {
            self._candidate_key(candidate)
            for candidate, result in zip(candidates, results)
            if result.status in eligible_statuses
        }
        for candidate, result in zip(candidates, results):
            if result.status not in eligible_statuses or candidate.local_path is None:
                continue

            path_key = str(candidate.local_path.resolve())
            entry = migrated_by_path.setdefault(
                path_key,
                {
                    "local_path": path_key,
                    "relative_path": candidate.local_path.relative_to(self.upload_root).as_posix()
                    if candidate.local_path.is_relative_to(self.upload_root)
                    else candidate.local_path.name,
                    "destination_keys": set(),
                    "migrated_urls": set(),
                    "reference_fields": set(),
                    "reference_count": 0,
                },
            )
            if candidate.destination_key:
                entry["destination_keys"].add(candidate.destination_key)
            if result.migrated_url:
                entry["migrated_urls"].add(result.migrated_url)
            entry["reference_fields"].add(f"{candidate.source_type}:{candidate.field_name}")
            entry["reference_count"] = int(entry["reference_count"]) + 1

        if not migrated_by_path:
            return []

        remaining_candidates, _, _ = self.scan_candidates()
        remaining_paths = {
            str(candidate.local_path.resolve())
            for candidate in remaining_candidates
            if candidate.local_path is not None
            and (
                not simulate
                or self._candidate_key(candidate) not in simulated_candidate_keys
            )
        }

        cleanup_candidates: list[UploadCleanupCandidate] = []
        for path_key, entry in migrated_by_path.items():
            if path_key in remaining_paths:
                continue
            cleanup_candidates.append(
                UploadCleanupCandidate(
                    local_path=str(entry["local_path"]),
                    relative_path=str(entry["relative_path"]),
                    destination_keys=sorted(str(value) for value in entry["destination_keys"]),
                    migrated_urls=sorted(str(value) for value in entry["migrated_urls"]),
                    reference_count=int(entry["reference_count"]),
                    reference_fields=sorted(str(value) for value in entry["reference_fields"]),
                    reason=(
                        "All persisted references would point at cloud storage URLs after this batch applies."
                        if simulate
                        else "All persisted references now point at cloud storage URLs."
                    ),
                )
            )

        cleanup_candidates.sort(key=lambda item: item.local_path)
        return cleanup_candidates

    def _current_candidate_urls(self, candidate: UploadMigrationCandidate) -> list[str]:
        if candidate.source_type == "upload_asset":
            asset = self.db.query(UploadAsset).filter(UploadAsset.id == candidate.entity_id).first()
            if asset is None or not isinstance(asset.url, str) or not asset.url.strip():
                return []
            return [asset.url]

        if candidate.source_type == "post":
            post = self.db.query(Post).filter(Post.id == candidate.entity_id).first()
            if post is None:
                return []
            current_url = getattr(post, candidate.field_name, None)
            if not isinstance(current_url, str) or not current_url.strip():
                return []
            return [current_url]

        if candidate.source_type == "billing_attachment":
            audit = self.db.query(BillingAuditLog).filter(BillingAuditLog.id == candidate.entity_id).first()
            if audit is None:
                return []
            payload = audit.extra_data if isinstance(audit.extra_data, dict) else {}
            attachment_urls = payload.get("attachment_urls")
            if not isinstance(attachment_urls, list):
                return []
            return [value for value in attachment_urls if isinstance(value, str) and value.strip()]

        return []

    def _build_verification_failures(
        self,
        candidates: list[UploadMigrationCandidate],
    ) -> list[UploadMigrationVerificationFailure]:
        failures: list[UploadMigrationVerificationFailure] = []
        for candidate in candidates:
            current_url = next(
                (
                    value
                    for value in self._current_candidate_urls(candidate)
                    if looks_like_local_upload_url(value)
                ),
                None,
            )
            if current_url is None:
                continue
            failures.append(
                UploadMigrationVerificationFailure(
                    source_type=candidate.source_type,
                    entity_id=candidate.entity_id,
                    field_name=candidate.field_name,
                    original_url=candidate.original_url,
                    current_url=current_url,
                    reason="Persisted reference still points at a local /uploads URL after this batch.",
                )
            )
        return failures

    @staticmethod
    def _candidate_key(candidate: UploadMigrationCandidate) -> tuple[str, str, str, str]:
        return (
            candidate.source_type,
            candidate.entity_id,
            candidate.field_name,
            candidate.original_url,
        )

    def migrate_candidate(self, candidate: UploadMigrationCandidate, *, apply: bool) -> UploadMigrationItemResult:
        if candidate.local_path is None or candidate.destination_key is None:
            return UploadMigrationItemResult(
                source_type=candidate.source_type,
                entity_id=candidate.entity_id,
                field_name=candidate.field_name,
                original_url=candidate.original_url,
                destination_key=candidate.destination_key,
                status="skipped",
                message="Candidate could not be resolved to a local file path and destination key.",
            )

        if not candidate.local_path.exists() or not candidate.local_path.is_file():
            return UploadMigrationItemResult(
                source_type=candidate.source_type,
                entity_id=candidate.entity_id,
                field_name=candidate.field_name,
                original_url=candidate.original_url,
                destination_key=candidate.destination_key,
                status="missing_local_file",
                message=f"Local file not found: {candidate.local_path}",
            )

        if not apply:
            return UploadMigrationItemResult(
                source_type=candidate.source_type,
                entity_id=candidate.entity_id,
                field_name=candidate.field_name,
                original_url=candidate.original_url,
                destination_key=candidate.destination_key,
                status="planned",
                message=str(candidate.local_path),
            )

        try:
            cloud_url = self._upload_candidate_file(candidate)
            if candidate.source_type == "upload_asset":
                self._apply_upload_asset(candidate, cloud_url)
            elif candidate.source_type == "post":
                self._apply_post(candidate, cloud_url)
            elif candidate.source_type == "billing_attachment":
                self._apply_billing_attachment(candidate, cloud_url)
            else:
                raise RuntimeError(f"Unsupported source type: {candidate.source_type}")
            self.db.commit()
            return UploadMigrationItemResult(
                source_type=candidate.source_type,
                entity_id=candidate.entity_id,
                field_name=candidate.field_name,
                original_url=candidate.original_url,
                destination_key=candidate.destination_key,
                status="migrated",
                migrated_url=cloud_url,
            )
        except Exception as exc:
            self.db.rollback()
            return UploadMigrationItemResult(
                source_type=candidate.source_type,
                entity_id=candidate.entity_id,
                field_name=candidate.field_name,
                original_url=candidate.original_url,
                destination_key=candidate.destination_key,
                status="error",
                message=str(exc),
            )

    def run(
        self,
        *,
        apply: bool = False,
        source_types: Iterable[str] | None = None,
        entity_ids: Iterable[str] | None = None,
        offset: int = 0,
        limit: int | None = None,
    ) -> UploadMigrationRunResult:
        """Run upload migration in dry-run or apply mode."""
        if apply:
            self._require_storage_for_apply()

        candidates, matching_total, source_totals = self.scan_candidates(
            source_types=source_types,
            entity_ids=entity_ids,
            offset=offset,
            limit=limit,
        )
        results = [self.migrate_candidate(candidate, apply=apply) for candidate in candidates]
        cleanup_candidates = self._build_cleanup_candidates(
            candidates,
            results,
            simulate=not apply,
        )
        verification_failures = self._build_verification_failures(candidates) if apply else []
        safe_offset = max(offset, 0)
        consumed_total = safe_offset + len(candidates)
        has_more = consumed_total < matching_total
        return UploadMigrationRunResult(
            apply=apply,
            matching_total=matching_total,
            candidate_total=len(candidates),
            processed_total=len(results),
            migrated_total=sum(1 for item in results if item.status == "migrated"),
            missing_local_file_total=sum(1 for item in results if item.status == "missing_local_file"),
            skipped_total=sum(1 for item in results if item.status in {"planned", "skipped"}),
            error_total=sum(1 for item in results if item.status == "error"),
            batch_offset=safe_offset,
            batch_limit=limit,
            has_more=has_more,
            next_offset=consumed_total if has_more else None,
            source_totals=source_totals,
            cleanup_candidate_total=len(cleanup_candidates),
            cleanup_candidates=cleanup_candidates,
            verification_performed=apply,
            verification_checked_total=len(candidates) if apply else 0,
            verification_failed_total=len(verification_failures),
            verification_failures=verification_failures,
            results=results,
        )
