from datetime import date, timedelta
from uuid import uuid4

from sqlalchemy.orm import Session

from app.models.analytics import Analytics
from app.models.channel import Channel, ChannelStatus, ChannelType
from app.services.analytics import AnalyticsService


async def test_collect_for_location_uses_decrypted_gbp_credentials(
    db: Session,
    test_location,
    monkeypatch,
):
    channel = Channel(
        id=uuid4(),
        location_id=test_location.id,
        type=ChannelType.GBP,
        status=ChannelStatus.CONNECTED,
        is_active=True,
    )
    channel.set_credentials({"access_token": "gbp-token", "location_id": "loc-1", "account_id": "acct-1"})
    db.add(channel)
    db.commit()

    captured = {}

    class FakeGBPClient:
        def __init__(self, credentials):
            captured["credentials"] = credentials

        async def get_metrics(self, start_date, end_date):
            return [
                {
                    "date": date.today() - timedelta(days=1),
                    "impressions": 42,
                    "clicks": 7,
                    "calls": 3,
                    "direction_requests": 2,
                }
            ]

    monkeypatch.setattr("app.services.analytics.GBPClient", FakeGBPClient)

    await AnalyticsService(db).collect_for_location(test_location.id)

    assert captured["credentials"]["access_token"] == "gbp-token"
    analytics = db.query(Analytics).filter(Analytics.location_id == test_location.id).one()
    assert analytics.platform == "GBP"
    assert analytics.impressions == 42
    assert analytics.source_raw["date"] == (date.today() - timedelta(days=1)).isoformat()
    db.refresh(channel)
    assert channel.last_sync_at is not None
    assert channel.error_message is None


async def test_collect_for_location_uses_decrypted_instagram_credentials(
    db: Session,
    test_location,
    monkeypatch,
):
    channel = Channel(
        id=uuid4(),
        location_id=test_location.id,
        type=ChannelType.INSTAGRAM,
        status=ChannelStatus.CONNECTED,
        is_active=True,
    )
    channel.set_credentials({"access_token": "ig-token", "instagram_account_id": "ig-1"})
    db.add(channel)
    db.commit()

    captured = {}

    class FakeInstagramClient:
        def __init__(self, credentials):
            captured["credentials"] = credentials

        async def get_insights(self, start_date, end_date):
            return [
                {
                    "date": date.today() - timedelta(days=1),
                    "reach": 100,
                    "likes": 11,
                    "comments": 4,
                    "shares": 2,
                    "saves": 6,
                }
            ]

    monkeypatch.setattr("app.services.analytics.InstagramClient", FakeInstagramClient)

    await AnalyticsService(db).collect_for_location(test_location.id)

    assert captured["credentials"]["instagram_account_id"] == "ig-1"
    analytics = db.query(Analytics).filter(Analytics.location_id == test_location.id).one()
    assert analytics.platform == "INSTAGRAM"
    assert analytics.reach == 100
    assert analytics.comments == 4
    assert analytics.source_raw["date"] == (date.today() - timedelta(days=1)).isoformat()
    db.refresh(channel)
    assert channel.last_sync_at is not None
    assert channel.error_message is None
