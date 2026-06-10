from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy.orm import Session

from app.models.channel import Channel, ChannelStatus, ChannelType
from app.models.location import Location
from app.models.oauth import OAuthEvent, OAuthEventType, OAuthProvider, OAuthStatus, OAuthToken


async def test_refresh_channel_token_marks_reconnect_required_on_google_refresh_failure(
    client,
    auth_headers,
    test_location: Location,
    db: Session,
    monkeypatch,
):
    channel = Channel(
        id=uuid4(),
        location_id=test_location.id,
        type=ChannelType.GBP,
        status=ChannelStatus.CONNECTED,
        is_active=True,
        access_token_expires_at=datetime.now(UTC) + timedelta(days=1),
    )
    channel.set_credentials(
        {
            "access_token": "old-access",
            "refresh_token": "old-refresh",
        }
    )
    db.add(channel)
    db.commit()

    async def fake_refresh_provider_access_token(provider, refresh_token):
        raise ValueError("invalid_grant: token revoked")

    monkeypatch.setattr("app.routers.oauth.refresh_provider_access_token", fake_refresh_provider_access_token)

    response = client.post(f"/oauth/refresh/{channel.id}", headers=auth_headers)
    assert response.status_code == 400
    assert "unavailable right now" in response.json()["detail"].lower()

    db.refresh(channel)
    assert channel.status == ChannelStatus.EXPIRED
    assert channel.error_count == 1
    assert "reconnect required" in channel.error_message.lower()
    assert channel.is_token_expired is True


async def test_refresh_provider_token_marks_needs_reauth_on_invalid_grant(
    client,
    auth_headers,
    test_user,
    test_location,
    db: Session,
    monkeypatch,
):
    token = OAuthToken(
        account_id=test_user.id,
        location_id=test_location.id,
        provider=OAuthProvider.GOOGLE,
        access_token_ref="secret://old-access",
        refresh_token_ref="secret://old-refresh",
        expires_at=datetime.now(UTC) + timedelta(minutes=30),
        status=OAuthStatus.HEALTHY,
    )
    db.add(token)
    db.commit()

    async def fake_refresh_provider_access_token(provider, refresh_token):
        raise ValueError("invalid_grant: token revoked")

    monkeypatch.setattr("app.routers.oauth.refresh_provider_access_token", fake_refresh_provider_access_token)

    response = client.post("/oauth/refresh-token/google", headers=auth_headers)
    assert response.status_code == 400
    assert "reconnect" in response.json()["detail"].lower()

    db.refresh(token)
    assert token.status == OAuthStatus.NEEDS_REAUTH
    assert token.last_error_code == "REAUTH_REQUIRED"
    assert "invalid_grant" in token.last_error.lower()

    event = (
        db.query(OAuthEvent)
        .filter(
            OAuthEvent.token_id == token.id,
            OAuthEvent.event_type == OAuthEventType.REFRESH_FAILED,
        )
        .one()
    )
    assert event.error_message == token.last_error
