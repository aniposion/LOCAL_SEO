import re
from datetime import UTC, datetime, timedelta

from app.core.security import get_password_hash, hash_opaque_token, verify_password
from app.models.account import Account


def _extract_token_from_body(body: str) -> str:
    match = re.search(r"token=([A-Za-z0-9_\-]+)", body)
    assert match is not None
    return match.group(1)


def _as_naive_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(UTC).replace(tzinfo=None)


def _naive_utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


async def test_signup_stores_hashed_verification_token_and_expiry(client, db, monkeypatch) -> None:
    sent_messages: list[dict[str, str]] = []

    async def fake_send(self, to_email: str, subject: str, body: str, html_body: str | None = None) -> None:
        sent_messages.append({"to_email": to_email, "subject": subject, "body": body})

    monkeypatch.setattr("app.routers.auth.EmailClient.send", fake_send)

    response = client.post(
        "/auth/signup",
        json={
            "email": "secure-signup@example.com",
            "password": "Securepass1!",
            "full_name": "Secure Owner",
            "company_name": "Secure Co",
            "phone": "555-0101",
            "timezone": "UTC",
            "language": "en",
            "accept_terms": True,
            "accept_privacy": True,
        },
    )

    assert response.status_code == 201
    assert sent_messages

    account = db.query(Account).filter(Account.email == "secure-signup@example.com").one()
    raw_token = _extract_token_from_body(sent_messages[0]["body"])

    assert account.verification_token == hash_opaque_token(raw_token)
    assert account.verification_token != raw_token
    assert account.verification_token_expires is not None
    assert _as_naive_utc(account.verification_token_expires) > _naive_utc_now()


def test_verify_email_requires_unexpired_token_and_clears_stored_hash(client, db) -> None:
    raw_token = "verify-me-token"
    account = Account(
        email="verify@example.com",
        password_hash=get_password_hash("Securepass1!"),
        verification_token=hash_opaque_token(raw_token),
        verification_token_expires=datetime.now(UTC) + timedelta(hours=1),
        is_verified=False,
        timezone="UTC",
        language="en",
    )
    db.add(account)
    db.commit()

    response = client.post("/auth/verify-email", json={"token": raw_token})

    assert response.status_code == 200
    db.refresh(account)
    assert account.is_verified is True
    assert account.verification_token is None
    assert account.verification_token_expires is None
    assert account.email_verified_at is not None


def test_verify_email_rejects_expired_token(client, db) -> None:
    raw_token = "expired-verify-token"
    account = Account(
        email="expired-verify@example.com",
        password_hash=get_password_hash("Securepass1!"),
        verification_token=hash_opaque_token(raw_token),
        verification_token_expires=datetime.now(UTC) - timedelta(minutes=1),
        is_verified=False,
        timezone="UTC",
        language="en",
    )
    db.add(account)
    db.commit()

    response = client.post("/auth/verify-email", json={"token": raw_token})

    assert response.status_code == 400
    assert "expired" in response.json()["detail"].lower()


async def test_password_reset_stores_hashed_token_and_accepts_raw_token(client, db, test_user, monkeypatch) -> None:
    sent_messages: list[dict[str, str]] = []

    async def fake_send(self, to_email: str, subject: str, body: str, html_body: str | None = None) -> None:
        sent_messages.append({"to_email": to_email, "subject": subject, "body": body})

    monkeypatch.setattr("app.routers.auth.EmailClient.send", fake_send)

    response = client.post("/auth/forgot-password", json={"email": test_user.email})

    assert response.status_code == 200
    assert sent_messages

    db.refresh(test_user)
    raw_token = _extract_token_from_body(sent_messages[0]["body"])

    assert test_user.password_reset_token == hash_opaque_token(raw_token)
    assert test_user.password_reset_token != raw_token
    assert test_user.password_reset_expires is not None
    assert _as_naive_utc(test_user.password_reset_expires) > _naive_utc_now()

    confirm_response = client.post(
        "/auth/reset-password",
        json={"token": raw_token, "new_password": "EvenMoreSecure1!"},
    )

    assert confirm_response.status_code == 200
    db.refresh(test_user)
    assert test_user.password_reset_token is None
    assert test_user.password_reset_expires is None
    assert verify_password("EvenMoreSecure1!", test_user.password_hash or "") is True
