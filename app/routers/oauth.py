"""OAuth router for platform connections (Google, Instagram/Facebook)."""

from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.models.account import Account
from app.models.channel import Channel, ChannelStatus, ChannelType
from app.models.location import Location
from app.routers.deps import get_current_user

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

    # Build state parameter (location_id:user_id)
    state = f"{location_id}:{current_user.id}"

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

    query_string = "&".join(f"{k}={v}" for k, v in params.items())
    auth_url = f"{GOOGLE_AUTH_URL}?{query_string}"

    return {"authorization_url": auth_url, "state": state}


@router.get("/google/callback")
async def google_callback(
    code: str = Query(...),
    state: str = Query(...),
    redirect_uri: str = Query(...),
    db: Session = Depends(get_db),
) -> dict:
    """Handle Google OAuth callback."""
    import httpx

    # Parse state
    try:
        location_id, user_id = state.split(":")
        location_id = UUID(location_id)
        user_id = UUID(user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid state parameter",
        )

    # Exchange code for tokens
    async with httpx.AsyncClient() as client:
        response = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "client_id": settings.gbp_client_id,
                "client_secret": settings.gbp_client_secret,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri,
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

    state = f"{location_id}:{current_user.id}"

    params = {
        "client_id": settings.ig_app_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": ",".join(INSTAGRAM_SCOPES),
        "state": state,
    }

    query_string = "&".join(f"{k}={v}" for k, v in params.items())
    auth_url = f"{FACEBOOK_AUTH_URL}?{query_string}"

    return {"authorization_url": auth_url, "state": state}


@router.get("/instagram/callback")
async def instagram_callback(
    code: str = Query(...),
    state: str = Query(...),
    redirect_uri: str = Query(...),
    db: Session = Depends(get_db),
) -> dict:
    """Handle Instagram/Facebook OAuth callback."""
    import httpx

    # Parse state
    try:
        location_id, user_id = state.split(":")
        location_id = UUID(location_id)
        user_id = UUID(user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid state parameter",
        )

    # Exchange code for short-lived token
    async with httpx.AsyncClient() as client:
        response = await client.get(
            FACEBOOK_TOKEN_URL,
            params={
                "client_id": settings.ig_app_id,
                "client_secret": settings.ig_app_secret,
                "code": code,
                "redirect_uri": redirect_uri,
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
    location = db.query(Location).filter(Location.id == location_id).first()
    if location:
        location.ig_business_id = instagram_account_id

    db.commit()

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

    channel = db.query(Channel).join(Location).filter(
        Channel.id == channel_id,
        Location.account_id == current_user.id,
    ).first()

    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Channel not found",
        )

    credentials = channel.get_credentials()

    if channel.type == ChannelType.GBP:
        # Refresh Google token
        refresh_token = credentials.get("refresh_token")
        if not refresh_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No refresh token available. Please reconnect the channel.",
            )

        async with httpx.AsyncClient() as client:
            response = await client.post(
                GOOGLE_TOKEN_URL,
                data={
                    "client_id": settings.gbp_client_id,
                    "client_secret": settings.gbp_client_secret,
                    "refresh_token": refresh_token,
                    "grant_type": "refresh_token",
                },
            )

            if response.status_code != 200:
                channel.status = ChannelStatus.ERROR
                channel.error_message = "Failed to refresh token"
                db.commit()
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Failed to refresh token. Please reconnect the channel.",
                )

            token_data = response.json()

        credentials["access_token"] = token_data["access_token"]
        channel.set_credentials(credentials)
        channel.access_token_expires_at = datetime.now(timezone.utc) + timedelta(
            seconds=token_data.get("expires_in", 3600)
        )

    elif channel.type == ChannelType.INSTAGRAM:
        # Refresh Facebook/Instagram long-lived token
        access_token = credentials.get("access_token")
        if not access_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No access token available. Please reconnect the channel.",
            )

        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://graph.facebook.com/v18.0/oauth/access_token",
                params={
                    "grant_type": "fb_exchange_token",
                    "client_id": settings.ig_app_id,
                    "client_secret": settings.ig_app_secret,
                    "fb_exchange_token": access_token,
                },
            )

            if response.status_code != 200:
                channel.status = ChannelStatus.ERROR
                channel.error_message = "Failed to refresh token"
                db.commit()
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Failed to refresh token. Please reconnect the channel.",
                )

            token_data = response.json()

        credentials["access_token"] = token_data["access_token"]
        channel.set_credentials(credentials)
        channel.access_token_expires_at = datetime.now(timezone.utc) + timedelta(
            seconds=token_data.get("expires_in", 5184000)
        )

    channel.status = ChannelStatus.CONNECTED
    channel.error_message = None
    db.commit()

    return {
        "status": "refreshed",
        "expires_at": channel.access_token_expires_at.isoformat(),
    }
