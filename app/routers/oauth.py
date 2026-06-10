"""OAuth router for platform connections (Google, Instagram/Facebook)."""

import base64
import hashlib
import hmac
import json
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.user_messages import integration_unavailable
from app.db.session import get_db
from app.models.account import Account
from app.models.channel import Channel, ChannelStatus, ChannelType
from app.models.oauth import OAuthEvent, OAuthEventType, OAuthProvider, OAuthStatus, OAuthToken
from app.models.location import Location
from app.routers.deps import get_current_user
from app.services.oauth_service import get_oauth_service, refresh_provider_access_token

router = APIRouter(prefix="/oauth", tags=["oauth"])


# Google OAuth URLs
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/business.manage",
    "https://www.googleapis.com/auth/userinfo.email",
]

# Facebook/Instagram OAuth URLs
FACEBOOK_AUTH_URL = "https://www.facebook.com/v18.0/dialog/oauth"
FACEBOOK_TOKEN_URL = "https://graph.facebook.com/v18.0/oauth/access_token"
INSTAGRAM_SCOPES = [
    "instagram_basic",
    "instagram_content_publish",
    "instagram_manage_insights",
    "pages_show_list",
    "pages_read_engagement",
]


def _oauth_state_timestamp() -> int:
    """Return the current timestamp for OAuth state validation."""
    return int(time.time())


def _encode_oauth_state_bytes(value: bytes) -> str:
    """Encode state payload/signature using URL-safe base64 without padding."""
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _decode_oauth_state_bytes(value: str) -> bytes:
    """Decode URL-safe base64 state data with restored padding."""
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(f"{value}{padding}".encode("ascii"))


def _sign_oauth_state(payload_segment: str) -> str:
    """Create an HMAC signature for the encoded OAuth payload segment."""
    digest = hmac.new(
        settings.jwt_secret.encode("utf-8"),
        payload_segment.encode("ascii"),
        hashlib.sha256,
    ).digest()
    return _encode_oauth_state_bytes(digest)


def _build_oauth_state(provider: str, location_id: UUID, user_id: UUID) -> str:
    """Build a signed OAuth state token bound to provider, location, and account."""
    payload = {
        "v": 1,
        "provider": provider,
        "location_id": str(location_id),
        "user_id": str(user_id),
        "iat": _oauth_state_timestamp(),
    }
    payload_segment = _encode_oauth_state_bytes(
        json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    )
    signature_segment = _sign_oauth_state(payload_segment)
    return f"{payload_segment}.{signature_segment}"


def _parse_oauth_state(state: str, expected_provider: str) -> tuple[UUID, UUID]:
    """Validate and decode a signed OAuth state token."""
    try:
        payload_segment, signature_segment = state.split(".", 1)
    except ValueError as exc:
        raise ValueError("Invalid OAuth state.") from exc

    expected_signature = _sign_oauth_state(payload_segment)
    if not hmac.compare_digest(signature_segment, expected_signature):
        raise ValueError("Invalid OAuth state.")

    try:
        payload = json.loads(_decode_oauth_state_bytes(payload_segment).decode("utf-8"))
        version = int(payload["v"])
        provider = str(payload["provider"])
        location_id = UUID(str(payload["location_id"]))
        user_id = UUID(str(payload["user_id"]))
        issued_at = int(payload["iat"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError("Invalid OAuth state.") from exc

    if version != 1 or provider != expected_provider:
        raise ValueError("Invalid OAuth state.")

    now_ts = _oauth_state_timestamp()
    if issued_at > now_ts + 60:
        raise ValueError("Invalid OAuth state.")
    if now_ts - issued_at > settings.oauth_state_ttl_seconds:
        raise ValueError("OAuth state expired. Please reconnect and try again.")

    return location_id, user_id


def _validate_oauth_state_location(db: Session, location_id: UUID, user_id: UUID) -> Location:
    """Ensure the signed OAuth state still matches an accessible location."""
    location = db.query(Location).filter(
        Location.id == location_id,
        Location.account_id == user_id,
    ).first()

    if not location:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OAuth state no longer matches an accessible location.",
        )

    return location


def _resolve_callback_redirect_uri(request: Request, redirect_uri: str | None, frontend_redirect: str | None) -> str:
    """Resolve the redirect URI used in the provider token exchange."""
    if redirect_uri:
        return redirect_uri
    if frontend_redirect:
        return str(request.url.replace_query_params(frontend_redirect=frontend_redirect))
    return str(request.url.replace_query_params())


def _frontend_callback_redirect(
    frontend_redirect: str | None,
    provider: str,
    status_value: str,
    **params: str | UUID,
) -> RedirectResponse | None:
    """Build a redirect response for frontend callback UX."""
    if not frontend_redirect:
        return None
    query = {"status": status_value, "provider": provider}
    for key, value in params.items():
        if value is not None and value != "":
            query[key] = str(value)
    return RedirectResponse(url=f"{frontend_redirect}?{urlencode(query)}")


def _mark_refresh_failure(channel: Channel, message: str) -> None:
    """Mark a channel as requiring reconnect after refresh failure."""
    channel.status = ChannelStatus.EXPIRED
    channel.error_message = message
    channel.error_count = (channel.error_count or 0) + 1
    channel.access_token_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)


@router.get("/google/authorize")
def google_authorize(
    location_id: UUID = Query(..., description="Location to connect"),
    redirect_uri: str = Query(..., description="Redirect URI after auth"),
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_user),
) -> dict:
    """Get Google OAuth authorization URL."""
    # Verify location ownership
    location = db.query(Location).filter(
        Location.id == location_id,
        Location.account_id == current_user.id,
    ).first()

    if not location:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Location not found",
        )

    state = _build_oauth_state("google", location_id, current_user.id)

    # Build authorization URL
    params = {
        "client_id": settings.gbp_client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(GOOGLE_SCOPES),
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }

    auth_url = f"{GOOGLE_AUTH_URL}?{urlencode(params)}"

    return {"authorization_url": auth_url, "state": state}


@router.get("/google/callback")
async def google_callback(
    request: Request,
    code: str | None = Query(None),
    state: str | None = Query(None),
    error: str | None = Query(None),
    error_description: str | None = Query(None),
    redirect_uri: str | None = Query(None),
    frontend_redirect: str | None = Query(None),
    db: Session = Depends(get_db),
) -> dict:
    """Handle Google OAuth callback."""
    import httpx

    if error:
        callback = _frontend_callback_redirect(
            frontend_redirect,
            "google",
            "cancelled" if error == "access_denied" else "failed",
            message=error_description or error,
        )
        if callback:
            return callback
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_description or error,
        )

    if not code or not state:
        callback = _frontend_callback_redirect(
            frontend_redirect,
            "google",
            "failed",
            message="Missing OAuth callback parameters",
        )
        if callback:
            return callback
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing OAuth callback parameters",
        )

    try:
        location_id, user_id = _parse_oauth_state(state, "google")
    except ValueError as exc:
        callback = _frontend_callback_redirect(
            frontend_redirect,
            "google",
            "failed",
            message=str(exc),
        )
        if callback:
            return callback
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    _validate_oauth_state_location(db, location_id, user_id)

    callback_redirect_uri = _resolve_callback_redirect_uri(request, redirect_uri, frontend_redirect)

    # Exchange code for tokens
    async with httpx.AsyncClient() as client:
        response = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "client_id": settings.gbp_client_id,
                "client_secret": settings.gbp_client_secret,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": callback_redirect_uri,
            },
        )

        if response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to exchange code: {response.text}",
            )

        token_data = response.json()

    # Get user info to verify
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {token_data['access_token']}"},
        )
        user_info = response.json()

    # Calculate token expiration
    expires_in = token_data.get("expires_in", 3600)
    access_token_expires = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

    # Create or update channel
    channel = db.query(Channel).filter(
        Channel.location_id == location_id,
        Channel.type == ChannelType.GBP,
    ).first()

    credentials = {
        "access_token": token_data["access_token"],
        "refresh_token": token_data.get("refresh_token"),
        "token_type": token_data.get("token_type", "Bearer"),
    }

    if channel:
        channel.set_credentials(credentials)
        channel.status = ChannelStatus.CONNECTED
        channel.access_token_expires_at = access_token_expires
        channel.platform_account_id = user_info.get("id")
        channel.platform_account_name = user_info.get("email")
        channel.scopes = GOOGLE_SCOPES
        channel.error_message = None
        channel.error_count = 0
    else:
        channel = Channel(
            location_id=location_id,
            type=ChannelType.GBP,
            status=ChannelStatus.CONNECTED,
            access_token_expires_at=access_token_expires,
            platform_account_id=user_info.get("id"),
            platform_account_name=user_info.get("email"),
            scopes=GOOGLE_SCOPES,
        )
        channel.set_credentials(credentials)
        db.add(channel)

    db.commit()

    callback = _frontend_callback_redirect(
        frontend_redirect,
        "google",
        "connected",
        location_id=location_id,
    )
    if callback:
        return callback

    return {
        "status": "connected",
        "channel_type": "GBP",
        "account_name": user_info.get("email"),
    }


@router.get("/instagram/authorize")
def instagram_authorize(
    location_id: UUID = Query(..., description="Location to connect"),
    redirect_uri: str = Query(..., description="Redirect URI after auth"),
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_user),
) -> dict:
    """Get Instagram/Facebook OAuth authorization URL."""
    # Verify location ownership
    location = db.query(Location).filter(
        Location.id == location_id,
        Location.account_id == current_user.id,
    ).first()

    if not location:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Location not found",
        )

    state = _build_oauth_state("instagram", location_id, current_user.id)

    params = {
        "client_id": settings.ig_app_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": ",".join(INSTAGRAM_SCOPES),
        "state": state,
    }

    auth_url = f"{FACEBOOK_AUTH_URL}?{urlencode(params)}"

    return {"authorization_url": auth_url, "state": state}


@router.get("/instagram/callback")
async def instagram_callback(
    request: Request,
    code: str | None = Query(None),
    state: str | None = Query(None),
    error: str | None = Query(None),
    error_description: str | None = Query(None),
    redirect_uri: str | None = Query(None),
    frontend_redirect: str | None = Query(None),
    db: Session = Depends(get_db),
) -> dict:
    """Handle Instagram/Facebook OAuth callback."""
    import httpx

    if error:
        callback = _frontend_callback_redirect(
            frontend_redirect,
            "instagram",
            "cancelled" if error == "access_denied" else "failed",
            message=error_description or error,
        )
        if callback:
            return callback
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_description or error,
        )

    if not code or not state:
        callback = _frontend_callback_redirect(
            frontend_redirect,
            "instagram",
            "failed",
            message="Missing OAuth callback parameters",
        )
        if callback:
            return callback
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing OAuth callback parameters",
        )

    try:
        location_id, user_id = _parse_oauth_state(state, "instagram")
    except ValueError as exc:
        callback = _frontend_callback_redirect(
            frontend_redirect,
            "instagram",
            "failed",
            message=str(exc),
        )
        if callback:
            return callback
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    location = _validate_oauth_state_location(db, location_id, user_id)

    callback_redirect_uri = _resolve_callback_redirect_uri(request, redirect_uri, frontend_redirect)

    # Exchange code for short-lived token
    async with httpx.AsyncClient() as client:
        response = await client.get(
            FACEBOOK_TOKEN_URL,
            params={
                "client_id": settings.ig_app_id,
                "client_secret": settings.ig_app_secret,
                "code": code,
                "redirect_uri": callback_redirect_uri,
            },
        )

        if response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to exchange code: {response.text}",
            )

        short_token_data = response.json()

    # Exchange for long-lived token
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://graph.facebook.com/v18.0/oauth/access_token",
            params={
                "grant_type": "fb_exchange_token",
                "client_id": settings.ig_app_id,
                "client_secret": settings.ig_app_secret,
                "fb_exchange_token": short_token_data["access_token"],
            },
        )

        if response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to get long-lived token",
            )

        long_token_data = response.json()

    # Get Instagram Business Account ID
    async with httpx.AsyncClient() as client:
        # First get Facebook pages
        response = await client.get(
            "https://graph.facebook.com/v18.0/me/accounts",
            params={"access_token": long_token_data["access_token"]},
        )
        pages_data = response.json()

        instagram_account_id = None
        instagram_username = None

        # Find Instagram account linked to pages
        for page in pages_data.get("data", []):
            page_response = await client.get(
                f"https://graph.facebook.com/v18.0/{page['id']}",
                params={
                    "fields": "instagram_business_account",
                    "access_token": long_token_data["access_token"],
                },
            )
            page_data = page_response.json()

            if "instagram_business_account" in page_data:
                instagram_account_id = page_data["instagram_business_account"]["id"]

                # Get Instagram username
                ig_response = await client.get(
                    f"https://graph.facebook.com/v18.0/{instagram_account_id}",
                    params={
                        "fields": "username",
                        "access_token": long_token_data["access_token"],
                    },
                )
                ig_data = ig_response.json()
                instagram_username = ig_data.get("username")
                break

    if not instagram_account_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No Instagram Business Account found. Please connect an Instagram Business account to a Facebook Page.",
        )

    # Calculate expiration (long-lived tokens last ~60 days)
    expires_in = long_token_data.get("expires_in", 5184000)
    access_token_expires = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

    # Create or update channel
    channel = db.query(Channel).filter(
        Channel.location_id == location_id,
        Channel.type == ChannelType.INSTAGRAM,
    ).first()

    credentials = {
        "access_token": long_token_data["access_token"],
        "instagram_account_id": instagram_account_id,
    }

    if channel:
        channel.set_credentials(credentials)
        channel.status = ChannelStatus.CONNECTED
        channel.access_token_expires_at = access_token_expires
        channel.platform_account_id = instagram_account_id
        channel.platform_account_name = instagram_username
        channel.scopes = INSTAGRAM_SCOPES
        channel.error_message = None
        channel.error_count = 0
    else:
        channel = Channel(
            location_id=location_id,
            type=ChannelType.INSTAGRAM,
            status=ChannelStatus.CONNECTED,
            access_token_expires_at=access_token_expires,
            platform_account_id=instagram_account_id,
            platform_account_name=instagram_username,
            scopes=INSTAGRAM_SCOPES,
        )
        channel.set_credentials(credentials)
        db.add(channel)

    # Update location with Instagram ID
    location.ig_business_id = instagram_account_id

    db.commit()

    callback = _frontend_callback_redirect(
        frontend_redirect,
        "instagram",
        "connected",
        location_id=location_id,
        account_name=instagram_username or "",
    )
    if callback:
        return callback

    return {
        "status": "connected",
        "channel_type": "INSTAGRAM",
        "account_name": instagram_username,
        "account_id": instagram_account_id,
    }


@router.post("/disconnect/{channel_id}")
def disconnect_channel(
    channel_id: UUID,
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_user),
) -> dict:
    """Disconnect a channel."""
    channel = db.query(Channel).join(Location).filter(
        Channel.id == channel_id,
        Location.account_id == current_user.id,
    ).first()

    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Channel not found",
        )

    channel.status = ChannelStatus.DISCONNECTED
    channel.credentials_encrypted = None
    channel.is_active = False
    db.commit()

    return {"status": "disconnected", "channel_id": str(channel_id)}


@router.post("/refresh/{channel_id}")
async def refresh_channel_token(
    channel_id: UUID,
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_user),
) -> dict:
    """Refresh channel access token."""
    import httpx

    channel = db.get(Channel, channel_id)

    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Channel not found",
        )

    location = db.get(Location, channel.location_id)
    if not location or location.account_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Channel not found",
        )

    credentials = channel.get_credentials()

    if channel.type == ChannelType.GBP:
        refresh_token = credentials.get("refresh_token")
        if not refresh_token:
            _mark_refresh_failure(channel, "Missing Google refresh token; reconnect required")
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=integration_unavailable(
                    "Google token refresh",
                    "the Google refresh token is missing",
                    "Open Integrations to reconnect Google and try again",
                ),
            )

        try:
            token_data = await refresh_provider_access_token("google", refresh_token)
        except Exception as exc:
            _mark_refresh_failure(channel, f"Google refresh failed; reconnect required: {exc}")
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=integration_unavailable(
                    "Google token refresh",
                    "the Google refresh flow failed",
                    "Open Integrations to reconnect Google and try again",
                ),
            ) from exc

        credentials["access_token"] = token_data["access_token"]
        if token_data.get("refresh_token"):
            credentials["refresh_token"] = token_data["refresh_token"]
        channel.set_credentials(credentials)
        channel.access_token_expires_at = datetime.now(timezone.utc) + timedelta(
            seconds=token_data.get("expires_in", 3600)
        )

    elif channel.type == ChannelType.INSTAGRAM:
        refresh_token = credentials.get("access_token")
        if not refresh_token:
            _mark_refresh_failure(channel, "Missing Instagram token; reconnect required")
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=integration_unavailable(
                    "Instagram token refresh",
                    "the Instagram token is missing",
                    "Open Integrations to reconnect Instagram and try again",
                ),
            )

        try:
            token_data = await refresh_provider_access_token("instagram", refresh_token)
        except Exception as exc:
            _mark_refresh_failure(channel, f"Instagram refresh failed; reconnect required: {exc}")
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=integration_unavailable(
                    "Instagram token refresh",
                    "the Instagram refresh flow failed",
                    "Open Integrations to reconnect Instagram and try again",
                ),
            ) from exc

        credentials["access_token"] = token_data["access_token"]
        channel.set_credentials(credentials)
        channel.access_token_expires_at = datetime.now(timezone.utc) + timedelta(
            seconds=token_data.get("expires_in", 5184000)
        )
    else:
        _mark_refresh_failure(channel, f"Refresh not supported for {channel.type.value}; reconnect required")
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=integration_unavailable(
                f"{channel.type.value.title()} token refresh",
                "this channel does not support token refresh",
                "Open Integrations to reconnect the channel and try again",
            ),
        )

    channel.status = ChannelStatus.CONNECTED
    channel.error_message = None
    channel.error_count = 0
    db.commit()

    return {
        "status": "refreshed",
        "expires_at": channel.access_token_expires_at.isoformat(),
    }


# ====================
# P4: Account-level Token Management
# ====================

@router.get("/tokens")
async def get_oauth_tokens(
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_user),
) -> dict:
    """Get all OAuth tokens for current user's account."""
    from app.services.oauth_service import get_oauth_service
    from sqlalchemy.ext.asyncio import AsyncSession
    
    # Get tokens using new service
    service = get_oauth_service(db)
    tokens = await service.get_tokens(current_user.id)
    
    # Count stats
    expiring_soon = sum(
        1 for t in tokens 
        if t.expires_at and t.expires_at <= datetime.now(timezone.utc) + timedelta(days=7)
    )
    needs_attention = sum(
        1 for t in tokens 
        if t.status in [OAuthStatus.NEEDS_REAUTH, OAuthStatus.DEGRADED]
    )
    
    return {
        "items": [
            {
                "id": str(t.id),
                "provider": t.provider.value,
                "email": t.email,
                "status": t.status.value,
                "scopes": t.scopes or [],
                "expires_at": t.expires_at.isoformat() if t.expires_at else None,
                "last_used_at": t.last_used_at.isoformat() if t.last_used_at else None,
                "created_at": t.created_at.isoformat(),
            }
            for t in tokens
        ],
        "total": len(tokens),
        "expiring_soon": expiring_soon,
        "needs_attention": needs_attention,
    }


@router.get("/status")
async def get_connection_status(
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_user),
) -> dict:
    """Get connection status for all providers."""
    from app.services.oauth_service import get_oauth_service
    
    service = get_oauth_service(db)
    status = await service.get_connection_status(current_user.id)
    
    return {
        "google_connected": status["google_connected"],
        "facebook_connected": status["facebook_connected"],
        "instagram_connected": status["instagram_connected"],
        "google_locations": status["google_locations"],
        "needs_attention": status["needs_attention"],
    }


@router.post("/connect/{provider}")
async def initiate_oauth_connect(
    provider: str,
    redirect_uri: str = Query(...),
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_user),
) -> dict:
    """Initiate OAuth connection for a provider."""
    from app.services.oauth_service import get_oauth_service
    
    if provider not in ["google", "facebook", "instagram"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid provider: {provider}",
        )
    
    service = get_oauth_service(db)
    auth_url, state = service.initiate_connection(
        provider=provider,
        redirect_uri=redirect_uri,
        account_id=current_user.id,
    )
    
    return {
        "auth_url": auth_url,
        "state": state,
    }


@router.post("/callback/{provider}")
async def handle_oauth_callback(
    provider: str,
    code: str = Query(...),
    state: str = Query(...),
    db: Session = Depends(get_db),
) -> dict:
    """Handle OAuth callback from provider."""
    from app.services.oauth_service import get_oauth_service
    
    service = get_oauth_service(db)
    
    try:
        token = await service.handle_callback(provider, code, state)
        return {
            "success": True,
            "provider": provider,
            "email": token.email,
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post("/disconnect-provider/{provider}")
async def disconnect_provider(
    provider: str,
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_user),
) -> dict:
    """Disconnect OAuth provider from account."""
    from app.services.oauth_service import get_oauth_service
    
    service = get_oauth_service(db)
    success = await service.disconnect(current_user.id, provider)
    
    return {
        "success": success,
        "provider": provider,
        "message": f"{provider.title()} disconnected successfully",
    }


@router.post("/refresh-token/{provider}")
async def refresh_provider_token(
    provider: str,
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_user),
) -> dict:
    """Manually refresh OAuth token for provider."""
    try:
        provider_enum = OAuthProvider(provider)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid provider: {provider}",
        ) from exc

    token = (
        db.query(OAuthToken)
        .filter(
            OAuthToken.account_id == current_user.id,
            OAuthToken.provider == provider_enum,
        )
        .first()
    )
    
    if not token:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No {provider} token found",
        )

    if not token.refresh_token_ref:
        token.status = OAuthStatus.NEEDS_REAUTH
        token.last_error = "Refresh token missing; reconnect required"
        token.last_error_code = "REAUTH_REQUIRED"
        token.refresh_failure_count = (token.refresh_failure_count or 0) + 1
        token.last_refresh_at = datetime.now(timezone.utc)
        db.add(
            OAuthEvent(
                token_id=token.id,
                event_type=OAuthEventType.REFRESH_FAILED,
                error_message=token.last_error,
                event_data={"failure_count": token.refresh_failure_count},
            )
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Refresh token missing; reconnect required.",
        )

    try:
        new_tokens = await refresh_provider_access_token(provider_enum, token.refresh_token_ref)
    except Exception as exc:
        message = str(exc)
        token.status = OAuthStatus.NEEDS_REAUTH if "reconnect required" in message.lower() or "invalid_grant" in message.lower() else OAuthStatus.DEGRADED
        token.last_error = message
        token.last_error_code = "REAUTH_REQUIRED" if token.status == OAuthStatus.NEEDS_REAUTH else "REFRESH_FAILED"
        token.refresh_failure_count = (token.refresh_failure_count or 0) + 1
        token.last_refresh_at = datetime.now(timezone.utc)
        db.add(
            OAuthEvent(
                token_id=token.id,
                event_type=OAuthEventType.REFRESH_FAILED,
                error_message=token.last_error,
                event_data={"failure_count": token.refresh_failure_count},
            )
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message if "reconnect" in message.lower() else "Failed to refresh token. Please reconnect.",
        ) from exc

    token.access_token_ref = new_tokens["access_token"]
    if new_tokens.get("refresh_token"):
        token.refresh_token_ref = new_tokens["refresh_token"]
    token.expires_at = datetime.now(timezone.utc) + timedelta(seconds=int(new_tokens.get("expires_in", 3600)))
    token.status = OAuthStatus.HEALTHY
    token.last_error = None
    token.last_error_code = None
    token.refresh_failure_count = 0
    token.next_refresh_at = None
    token.last_refresh_at = datetime.now(timezone.utc)
    db.add(
        OAuthEvent(
            token_id=token.id,
            event_type=OAuthEventType.REFRESHED,
            event_data={"expires_at": token.expires_at.isoformat()},
        )
    )
    db.commit()

    return {
        "success": True,
        "status": token.status.value,
        "new_expiry": token.expires_at.isoformat() if token.expires_at else None,
    }
