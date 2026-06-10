"""Dry-run and apply helper for migrating legacy local uploads to cloud storage."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db.session import SessionLocal
from app.services.upload_migration import UploadMigrationService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Migrate legacy local /uploads references to cloud storage.")
    parser.add_argument("--apply", action="store_true", help="Apply changes instead of running a dry run.")
    parser.add_argument("--offset", type=int, default=0, help="Number of matching references to skip before processing the batch.")
    parser.add_argument("--limit", type=int, default=None, help="Maximum number of references to process.")
    parser.add_argument(
        "--source-type",
        action="append",
        choices=["upload_asset", "post", "billing_attachment"],
        dest="source_types",
        help="Restrict processing to one or more source types.",
    )
    parser.add_argument(
        "--entity-id",
        action="append",
        dest="entity_ids",
        help="Restrict processing to one or more entity ids.",
    )
    parser.add_argument(
        "--upload-root",
        default=str(ROOT / "uploads"),
        help="Local uploads directory root. Defaults to the repo uploads directory.",
    )
    parser.add_argument("--json", action="store_true", help="Print the summary as JSON.")
    parser.add_argument(
        "--cleanup-manifest",
        default=None,
        help="Optional path to write the safe-to-delete local file manifest as JSON after the run.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    db = SessionLocal()
    try:
        service = UploadMigrationService(db, upload_root=Path(args.upload_root))
        summary = service.run(
            apply=args.apply,
            source_types=args.source_types,
            entity_ids=args.entity_ids,
            offset=args.offset,
            limit=args.limit,
        )
    except Exception as exc:
        print(f"Upload migration failed: {exc}", file=sys.stderr)
        return 1
    finally:
        db.close()

    summary_payload = summary.to_dict()

    if args.cleanup_manifest:
        cleanup_manifest_path = Path(args.cleanup_manifest)
        cleanup_manifest_path.parent.mkdir(parents=True, exist_ok=True)
        cleanup_manifest_path.write_text(
            json.dumps(
                {
                    "apply": summary.apply,
                    "matching_total": summary.matching_total,
                    "batch_offset": summary.batch_offset,
                    "batch_limit": summary.batch_limit,
                    "has_more": summary.has_more,
                    "next_offset": summary.next_offset,
                    "source_totals": summary.source_totals,
                    "cleanup_candidate_total": summary.cleanup_candidate_total,
                    "cleanup_candidates": summary_payload["cleanup_candidates"],
                    "verification_performed": summary.verification_performed,
                    "verification_checked_total": summary.verification_checked_total,
                    "verification_failed_total": summary.verification_failed_total,
                    "verification_failures": summary_payload["verification_failures"],
                },
                indent=2,
                default=str,
            ),
            encoding="utf-8",
        )

    if args.json:
        print(json.dumps(summary_payload, indent=2, default=str))
        return 0

    mode = "APPLY" if summary.apply else "DRY RUN"
    print(f"Upload migration summary ({mode})")
    print(f"- matching total: {summary.matching_total}")
    print(f"- batch offset: {summary.batch_offset}")
    print(f"- batch limit: {summary.batch_limit if summary.batch_limit is not None else 'all'}")
    print(f"- candidates: {summary.candidate_total}")
    print(f"- processed: {summary.processed_total}")
    print(f"- migrated: {summary.migrated_total}")
    print(f"- missing local file: {summary.missing_local_file_total}")
    print(f"- skipped/planned: {summary.skipped_total}")
    print(f"- errors: {summary.error_total}")
    print(f"- cleanup candidates: {summary.cleanup_candidate_total}")
    if summary.verification_performed:
        print(f"- verification checked: {summary.verification_checked_total}")
        print(f"- verification failures: {summary.verification_failed_total}")
    print(f"- has more: {'yes' if summary.has_more else 'no'}")
    if summary.next_offset is not None:
        print(f"- next offset: {summary.next_offset}")
    if summary.source_totals:
        source_summary = ", ".join(f"{source}={count}" for source, count in sorted(summary.source_totals.items()))
        print(f"- source totals: {source_summary}")

    for item in summary.results:
        line = f"[{item.status}] {item.source_type}:{item.entity_id}:{item.field_name} -> {item.destination_key or '-'}"
        if item.migrated_url:
            line = f"{line} => {item.migrated_url}"
        if item.message:
            line = f"{line} ({item.message})"
        print(line)

    for item in summary.cleanup_candidates:
        print(
            f"[cleanup] {item.local_path} -> {', '.join(item.destination_keys)} "
            f"(refs: {item.reference_count})"
        )

    for item in summary.verification_failures:
        print(
            f"[verify-failed] {item.source_type}:{item.entity_id}:{item.field_name} -> "
            f"{item.current_url or '-'} ({item.reason})"
        )

    return 0 if summary.error_total == 0 and summary.verification_failed_total == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
