# Upload Migration Apply Runbook

## 목적

공개 런칭 전에 legacy local `/uploads/...` 참조를 cloud storage URL로 전환한다.

이 runbook은 아래 원칙을 따른다.

- dry-run 없이 apply 하지 않는다.
- batch 단위로만 apply 한다.
- apply 결과에서 `verification_failed_total = 0`을 확인하기 전에는 cleanup 하지 않는다.
- local file 삭제는 자동으로 하지 않고, cleanup manifest 검토 후 별도 운영 승인으로 진행한다.

## 사전 조건

- 운영 DB 백업 완료
- 운영 배포 대상 코드가 최신 migration head를 포함함
- cloud storage 환경변수와 권한 설정 완료
- `python -m alembic heads` 결과가 단일 head인지 확인
- `/admin/upload-migration-audit`에서 legacy reference 총량 확인
- `/admin/upload-migration-audit/export` CSV를 저장해 작업 전 manifest로 보관

## 1. 전체 dry-run

```powershell
python scripts/migrate_upload_assets.py --json
```

확인할 값:

- `matching_total`
- `missing_local_file_total`
- `error_total`
- `source_totals`
- `cleanup_candidate_total`

`missing_local_file_total`이 0보다 크면 apply 전에 누락 파일을 복구하거나, 해당 reference를 수동 교체 대상으로 분리한다.

## 2. 우선순위

권장 처리 순서:

1. `billing_attachment`
2. `post`
3. `upload_asset`

이유:

- billing attachment는 dispute evidence, refund, support audit에 직접 연결된다.
- post image는 고객-facing content에 연결된다.
- upload_asset은 source registry 성격이 강해 마지막에 정리해도 된다.

## 3. Batch preview

Admin API 또는 화면에서 batch preview를 먼저 확인한다.

```text
GET /admin/upload-migration-batch-preview?source_type=billing_attachment&offset=0&limit=25
GET /admin/upload-migration-batch-preview?source_type=post&offset=0&limit=25
GET /admin/upload-migration-batch-preview?source_type=upload_asset&offset=0&limit=25
```

응답에서 확인할 값:

- `matching_total`
- `candidate_total`
- `missing_local_file_total`
- `error_total`
- `has_more`
- `next_offset`
- `cleanup_candidates`
- `apply_command`
- `next_apply_command`

## 4. Apply 실행

작은 batch부터 시작한다.

```powershell
python scripts/migrate_upload_assets.py --apply --source-type billing_attachment --offset 0 --limit 25 --cleanup-manifest .codex-run/upload-migration-cleanup-billing-0-25.json --json
```

성공 조건:

- `error_total = 0`
- `verification_performed = true`
- `verification_failed_total = 0`
- `migrated_total`이 예상 candidate 수와 일치

`verification_failed_total`이 0보다 크면 다음 batch로 넘어가지 않는다.

## 5. 다음 batch

`has_more = true`이면 `next_offset`으로 다음 batch를 실행한다.

```powershell
python scripts/migrate_upload_assets.py --apply --source-type billing_attachment --offset <next_offset> --limit 25 --cleanup-manifest .codex-run/upload-migration-cleanup-billing-<next_offset>-25.json --json
```

같은 source type을 끝낸 뒤 다음 source type으로 넘어간다.

## 6. Cleanup manifest 검토

cleanup manifest는 safe-to-delete 후보일 뿐이다.

삭제 전 확인:

- 해당 파일의 모든 persisted reference가 cloud URL로 바뀌었는지 확인
- `verification_failed_total = 0`인지 확인
- `reference_count`, `reference_fields`, `destination_keys`, `migrated_urls` 검토
- 운영자 1명 이상이 CSV manifest와 cleanup manifest를 대조 검토

이 프로젝트는 migration script에서 local file을 자동 삭제하지 않는다.

## 7. 실패 대응

`missing_local_file_total > 0`:

- 파일을 운영 upload volume에서 복구한다.
- 복구가 불가능하면 해당 reference를 수동 교체 대상으로 기록한다.

`error_total > 0`:

- 해당 result의 `message`를 확인한다.
- cloud storage 권한, destination key, DB row 존재 여부를 확인한다.
- 같은 batch를 재실행하기 전에 DB 상태와 storage object 중복 여부를 확인한다.

`verification_failed_total > 0`:

- 아직 local `/uploads/...` URL이 남은 상태다.
- 다음 batch나 cleanup으로 넘어가지 않는다.
- 실패 item의 `source_type`, `entity_id`, `field_name`, `current_url`을 기준으로 수동 조사한다.

## 8. 완료 조건

아래 조건이 모두 충족되어야 upload migration apply를 완료로 본다.

- `/admin/upload-migration-audit`의 `actionable_total = 0`
- 전체 source type apply 결과에서 `verification_failed_total = 0`
- cleanup manifest 검토 완료
- 고객-facing post image URL이 cloud URL로 표시됨
- billing attachment URL이 cloud URL로 표시됨
- smoke test에서 upload, post preview, dispute evidence path가 정상 동작함

