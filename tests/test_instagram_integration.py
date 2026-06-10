from datetime import date

import pytest

from app.integrations.instagram import InstagramClient


async def test_instagram_client_accepts_oauth_account_id_for_conversations(monkeypatch):
    client = InstagramClient({"access_token": "token", "instagram_account_id": "ig-123"})
    calls = []

    async def fake_request(method, endpoint, **kwargs):
        calls.append((method, endpoint, kwargs))
        return {"data": []}

    monkeypatch.setattr(client, "_request", fake_request)

    result = await client.get_conversations(limit=5)

    assert result == {"data": []}
    assert calls[0][0] == "GET"
    assert calls[0][1] == "ig-123/conversations"
    assert calls[0][2]["params"]["platform"] == "instagram"
    assert calls[0][2]["params"]["limit"] == 5


async def test_instagram_client_shapes_dm_and_comment_reply_requests(monkeypatch):
    client = InstagramClient({"access_token": "token", "ig_user_id": "ig-456"})
    calls = []

    async def fake_request(method, endpoint, **kwargs):
        calls.append((method, endpoint, kwargs))
        return {"id": "created-id"}

    monkeypatch.setattr(client, "_request", fake_request)

    dm_id = await client.send_dm("recipient-1", "Thanks for reaching out.")
    reply_id = await client.reply_to_comment("comment-1", "Thanks for the comment.")

    assert dm_id == "created-id"
    assert reply_id == "created-id"
    assert calls[0] == (
        "POST",
        "ig-456/messages",
        {
            "json": {
                "recipient": {"id": "recipient-1"},
                "message": {"text": "Thanks for reaching out."},
            }
        },
    )
    assert calls[1] == (
        "POST",
        "comment-1/replies",
        {"json": {"message": "Thanks for the comment."}},
    )


async def test_instagram_insights_use_portable_unix_timestamps(monkeypatch):
    client = InstagramClient({"access_token": "token", "ig_user_id": "ig-789"})
    captured_params = []

    async def fake_request(method, endpoint, **kwargs):
        captured_params.append(kwargs.get("params", {}))
        return {"data": []}

    monkeypatch.setattr(client, "_request", fake_request)

    await client.get_insights(date(2026, 4, 25), date(2026, 4, 26))

    assert isinstance(captured_params[0]["since"], int)
    assert isinstance(captured_params[0]["until"], int)
    assert captured_params[0]["until"] > captured_params[0]["since"]


async def test_instagram_client_requires_business_account_id_for_messaging():
    client = InstagramClient({"access_token": "token"})

    with pytest.raises(ValueError, match="Instagram business account ID"):
        await client.get_conversations()
