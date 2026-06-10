from app.core.config import settings
from app.models.location import Location
from app.routers import oauth as oauth_router


def test_google_authorize_returns_signed_state(client, auth_headers, test_location: Location, test_user) -> None:
    response = client.get(
        "/oauth/google/authorize",
        params={
            "location_id": str(test_location.id),
            "redirect_uri": "https://app.example.com/oauth/google/callback",
        },
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    state = data["state"]

    assert state != f"{test_location.id}:{test_user.id}"
    assert "." in state
    assert oauth_router._parse_oauth_state(state, "google") == (test_location.id, test_user.id)


def test_google_callback_rejects_tampered_state(client, auth_headers, test_location: Location) -> None:
    authorize_response = client.get(
        "/oauth/google/authorize",
        params={
            "location_id": str(test_location.id),
            "redirect_uri": "https://app.example.com/oauth/google/callback",
        },
        headers=auth_headers,
    )
    state = authorize_response.json()["state"]
    payload, signature = state.split(".", 1)
    tampered_signature = f"{signature[:-1]}{'A' if signature[-1] != 'A' else 'B'}"

    response = client.get(
        "/oauth/google/callback",
        params={"code": "test-code", "state": f"{payload}.{tampered_signature}"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid OAuth state."


def test_google_callback_rejects_expired_state(client, test_location: Location, test_user, monkeypatch) -> None:
    issued_at = 1_700_000_000
    monkeypatch.setattr(oauth_router, "_oauth_state_timestamp", lambda: issued_at)
    state = oauth_router._build_oauth_state("google", test_location.id, test_user.id)
    monkeypatch.setattr(
        oauth_router,
        "_oauth_state_timestamp",
        lambda: issued_at + settings.oauth_state_ttl_seconds + 1,
    )

    response = client.get(
        "/oauth/google/callback",
        params={"code": "test-code", "state": state},
    )

    assert response.status_code == 400
    assert "expired" in response.json()["detail"].lower()


def test_instagram_callback_rejects_state_for_inaccessible_location(
    client,
    test_user,
    other_location: Location,
) -> None:
    state = oauth_router._build_oauth_state("instagram", other_location.id, test_user.id)

    response = client.get(
        "/oauth/instagram/callback",
        params={"code": "test-code", "state": state},
    )

    assert response.status_code == 400
    assert "accessible location" in response.json()["detail"].lower()
