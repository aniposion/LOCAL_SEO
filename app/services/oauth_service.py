"""P4: OAuth Token Management service."""

import logging
import secrets
from datetime import timedelta
from typing import Optional
from uuid import UUID

import httpx
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utc_now_naive
from app.core.config import settings
from app.models.oauth import OAuthToken, OAuthProvider, OAuthStatus
from app.services.google_api_service import get_google_api_service

logger = logging.getLogger(__name__)


def _requires_reauth(message: str) -> bool:
    """Detect refresh errors that should immediately require re-authentication."""
    lowered = message.lower()
    reauth_markers = (
        "invalid_grant",
        "invalid token",
        "token expired",
        "reconnect required",
        "reauth",
        "refresh token missing",
        "no refresh token",
        "unsupported provider",
        "not supported",
        "unauthorized",
        "forbidden",
        "revoked",
        "consent required",
    )
    return any(marker in lowered for marker in reauth_markers)


async def refresh_provider_access_token(provider: OAuthProvider | str, refresh_token: str) -> dict:
    """Refresh a provider access token using the real provider-specific code path."""
    provider_value = provider.value if isinstance(provider, OAuthProvider) else str(provider).lower()

    if provider_value == OAuthProvider.GOOGLE.value:
        return await get_google_api_service().refresh_access_token(refresh_token)

    if provider_value == OAuthProvider.FACEBOOK.value:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://graph.facebook.com/v18.0/oauth/access_token",
                params={
                    "grant_type": "fb_exchange_token",
                    "client_id": settings.facebook_app_id,
                    "client_secret": settings.facebook_app_secret,
                    "fb_exchange_token": refresh_token,
                },
            )

            if response.status_code != 200:
                raise ValueError(f"Facebook token refresh failed: {response.text}")

            return response.json()

    if provider_value == OAuthProvider.INSTAGRAM.value:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://graph.instagram.com/refresh_access_token",
                params={
                    "grant_type": "ig_refresh_token",
                    "access_token": refresh_token,
                },
            )

            if response.status_code != 200:
                raise ValueError(f"Instagram token refresh failed: {response.text}")

            return response.json()

    raise ValueError(f"Unsupported provider for refresh: {provider_value}")


class OAuthService:
    """Service for OAuth token management.
    
    Handles:
    - OAuth connection flows (Google, Facebook, Instagram)
    - Token storage and refresh
    - Token status monitoring
    - Provider disconnection
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.google = get_google_api_service()
        
        # State storage (in production, use Redis)
        self._pending_states: dict[str, dict] = {}

    # ====================
    # Token Management
    # ====================

    async def get_tokens(
        self,
        account_id: UUID,
        provider: Optional[str] = None,
    ) -> list[OAuthToken]:
        """Get OAuth tokens for account."""
        query = select(OAuthToken).where(
            OAuthToken.account_id == account_id
        )
        
        if provider:
            query = query.where(OAuthToken.provider == OAuthProvider(provider))
        
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_token(
        self,
        account_id: UUID,
        provider: str,
    ) -> Optional[OAuthToken]:
        """Get specific OAuth token."""
        result = await self.db.execute(
            select(OAuthToken).where(
                and_(
                    OAuthToken.account_id == account_id,
                    OAuthToken.provider == OAuthProvider(provider),
                )
            )
        )
        return result.scalar_one_or_none()

    async def get_token_by_id(self, token_id: UUID) -> Optional[OAuthToken]:
        """Get token by ID."""
        result = await self.db.execute(
            select(OAuthToken).where(OAuthToken.id == token_id)
        )
        return result.scalar_one_or_none()

    async def get_valid_access_token(
        self,
        account_id: UUID,
        provider: str,
    ) -> Optional[str]:
        """Get valid access token, refreshing if needed."""
        token = await self.get_token(account_id, provider)
        
        if not token:
            return None
        
        if token.status != OAuthStatus.HEALTHY:
            return None
        
        # Check if expired or expiring soon
        if token.expires_at and token.expires_at <= utc_now_naive() + timedelta(minutes=5):
            # Try to refresh
            success = await self.refresh_token(token)
            if not success:
                return None
            await self.db.refresh(token)
        
        # Update last used
        token.last_used_at = utc_now_naive()
        await self.db.commit()
        
        return token.access_token

    # ====================
    # OAuth Connection Flow
    # ====================

    def initiate_connection(
        self,
        provider: str,
        redirect_uri: str,
        account_id: UUID,
        scopes: list[str] = None,
    ) -> tuple[str, str]:
        """Initiate OAuth connection flow.
        
        Returns: (auth_url, state)
        """
        # Generate state token
        state = secrets.token_urlsafe(32)
        
        # Store state for verification
        self._pending_states[state] = {
            "account_id": str(account_id),
            "provider": provider,
            "redirect_uri": redirect_uri,
            "created_at": utc_now_naive(),
        }
        
        # Get auth URL based on provider
        if provider == "google":
            auth_url = self.google.get_auth_url(redirect_uri, state, scopes)
        elif provider == "facebook":
            auth_url = self._get_facebook_auth_url(redirect_uri, state, scopes)
        elif provider == "instagram":
            auth_url = self._get_instagram_auth_url(redirect_uri, state, scopes)
        else:
            raise ValueError(f"Unknown provider: {provider}")
        
        return auth_url, state

    async def handle_callback(
        self,
        provider: str,
        code: str,
        state: str,
    ) -> OAuthToken:
        """Handle OAuth callback.
        
        Returns the created/updated OAuth token.
        """
        # Verify state
        state_data = self._pending_states.pop(state, None)
        if not state_data:
            raise ValueError("Invalid or expired state")
        
        if state_data["provider"] != provider:
            raise ValueError("Provider mismatch")
        
        account_id = UUID(state_data["account_id"])
        redirect_uri = state_data["redirect_uri"]
        
        # Exchange code for tokens
        if provider == "google":
            token_data = await self.google.exchange_code(code, redirect_uri)
            user_info = await self.google.get_user_info(token_data["access_token"])
        elif provider == "facebook":
            token_data = await self._exchange_facebook_code(code, redirect_uri)
            user_info = await self._get_facebook_user_info(token_data["access_token"])
        elif provider == "instagram":
            token_data = await self._exchange_instagram_code(code, redirect_uri)
            user_info = {"id": token_data.get("user_id"), "email": None}
        else:
            raise ValueError(f"Unknown provider: {provider}")
        
        # Calculate expiry
        expires_in = token_data.get("expires_in", 3600)
        expires_at = utc_now_naive() + timedelta(seconds=expires_in)
        
        # Check for existing token
        existing = await self.get_token(account_id, provider)
        
        if existing:
            # Update existing token
            existing.access_token_ref = token_data["access_token"]
            existing.refresh_token_ref = token_data.get("refresh_token") or existing.refresh_token_ref
            existing.expires_at = expires_at
            existing.status = OAuthStatus.HEALTHY
            existing.provider_account_id = str(user_info.get("id"))
            existing.email = user_info.get("email")
            existing.scopes = token_data.get("scope", "").split()
            existing.last_error = None
            existing.last_error_code = None
            existing.refresh_failure_count = 0
            existing.next_refresh_at = None
            existing.updated_at = utc_now_naive()
            
            await self.db.commit()
            await self.db.refresh(existing)
            return existing
        else:
            # Create new token
            token = OAuthToken(
                account_id=account_id,
                provider=OAuthProvider(provider),
                access_token_ref=token_data["access_token"],
                refresh_token_ref=token_data.get("refresh_token"),
                expires_at=expires_at,
                provider_account_id=str(user_info.get("id")),
                email=user_info.get("email"),
                scopes=token_data.get("scope", "").split(),
            )
            
            self.db.add(token)
            await self.db.commit()
            await self.db.refresh(token)
            return token

    async def refresh_token(self, token: OAuthToken) -> bool:
        """Refresh an OAuth token.
        
        Returns True if successful.
        """
        if not token.refresh_token_ref:
            logger.warning(f"No refresh token for {token.id}")
            token.status = OAuthStatus.NEEDS_REAUTH
            token.last_error = "Refresh token missing; reconnect required"
            token.last_error_code = "REAUTH_REQUIRED"
            token.refresh_failure_count = (token.refresh_failure_count or 0) + 1
            token.last_refresh_at = utc_now_naive()
            token.next_refresh_at = None
            await self.db.commit()
            return False

        try:
            new_tokens = await refresh_provider_access_token(token.provider, token.refresh_token_ref)
            
            # Update token
            token.access_token_ref = new_tokens["access_token"]
            if "refresh_token" in new_tokens:
                token.refresh_token_ref = new_tokens["refresh_token"]
            
            expires_in = new_tokens.get("expires_in", 3600)
            token.expires_at = utc_now_naive() + timedelta(seconds=expires_in)
            token.status = OAuthStatus.HEALTHY
            token.last_refresh_at = utc_now_naive()
            token.last_error = None
            token.last_error_code = None
            token.refresh_failure_count = 0
            token.next_refresh_at = None
            
            await self.db.commit()
            logger.info(f"Refreshed token {token.id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to refresh token {token.id}: {e}")
            token.last_error = str(e)
            token.last_error_code = "REAUTH_REQUIRED" if _requires_reauth(str(e)) else "REFRESH_FAILED"
            token.refresh_failure_count = (token.refresh_failure_count or 0) + 1
            token.last_refresh_at = utc_now_naive()
            token.next_refresh_at = None
            token.status = (
                OAuthStatus.NEEDS_REAUTH
                if _requires_reauth(str(e)) or token.refresh_failure_count >= 3
                else OAuthStatus.DEGRADED
            )
            await self.db.commit()
            return False

    async def disconnect(
        self,
        account_id: UUID,
        provider: str,
    ) -> bool:
        """Disconnect OAuth provider."""
        token = await self.get_token(account_id, provider)
        
        if not token:
            return True
        
        # Revoke token at provider
        try:
            if token.provider == OAuthProvider.GOOGLE:
                await self.google.revoke_token(token.access_token_ref)
        except Exception as e:
            logger.warning(f"Failed to revoke token at provider: {e}")
        
        # Mark as revoked
        token.status = OAuthStatus.REVOKED
        token.access_token_ref = None
        token.refresh_token_ref = None
        token.last_error = None
        token.last_error_code = None
        token.refresh_failure_count = 0
        token.next_refresh_at = None
        await self.db.commit()
        
        logger.info(f"Disconnected {provider} for account {account_id}")
        return True

    # ====================
    # Connection Status
    # ====================

    async def get_connection_status(self, account_id: UUID) -> dict:
        """Get connection status for all providers."""
        tokens = await self.get_tokens(account_id)
        
        status = {
            "google": None,
            "facebook": None,
            "instagram": None,
            "google_connected": False,
            "facebook_connected": False,
            "instagram_connected": False,
            "google_locations": 0,
            "needs_attention": [],
        }
        
        for token in tokens:
            provider = token.provider.value
            status[provider] = token
            status[f"{provider}_connected"] = token.status == OAuthStatus.HEALTHY
            
            if token.status in [OAuthStatus.NEEDS_REAUTH, OAuthStatus.DEGRADED]:
                status["needs_attention"].append(provider)
        
        # Get Google location count if connected
        if status["google_connected"]:
            try:
                access_token = await self.get_valid_access_token(account_id, "google")
                if access_token:
                    locations = await self.google.get_locations(access_token)
                    status["google_locations"] = len(locations)
            except Exception:
                pass
        
        return status

    # ====================
    # Facebook/Instagram Helpers
    # ====================

    def _get_facebook_auth_url(
        self,
        redirect_uri: str,
        state: str,
        scopes: list[str] = None,
    ) -> str:
        """Generate Facebook OAuth URL."""
        scopes = scopes or ["email", "pages_read_engagement", "pages_manage_posts"]
        
        params = {
            "client_id": settings.facebook_app_id,
            "redirect_uri": redirect_uri,
            "state": state,
            "scope": ",".join(scopes),
        }
        
        query = "&".join(f"{k}={v}" for k, v in params.items())
        return f"https://www.facebook.com/v18.0/dialog/oauth?{query}"

    def _get_instagram_auth_url(
        self,
        redirect_uri: str,
        state: str,
        scopes: list[str] = None,
    ) -> str:
        """Generate Instagram OAuth URL."""
        scopes = scopes or ["user_profile", "user_media"]
        
        params = {
            "client_id": settings.instagram_client_id,
            "redirect_uri": redirect_uri,
            "scope": ",".join(scopes),
            "response_type": "code",
            "state": state,
        }
        
        query = "&".join(f"{k}={v}" for k, v in params.items())
        return f"https://api.instagram.com/oauth/authorize?{query}"

    async def _exchange_facebook_code(self, code: str, redirect_uri: str) -> dict:
        """Exchange Facebook code for tokens."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://graph.facebook.com/v18.0/oauth/access_token",
                params={
                    "client_id": settings.facebook_app_id,
                    "client_secret": settings.facebook_app_secret,
                    "code": code,
                    "redirect_uri": redirect_uri,
                },
            )
            
            if response.status_code != 200:
                raise ValueError(f"Facebook token exchange failed: {response.text}")
            
            return response.json()

    async def _get_facebook_user_info(self, access_token: str) -> dict:
        """Get Facebook user info."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://graph.facebook.com/me",
                params={
                    "access_token": access_token,
                    "fields": "id,name,email",
                },
            )
            return response.json()

    async def _exchange_instagram_code(self, code: str, redirect_uri: str) -> dict:
        """Exchange Instagram code for tokens."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.instagram.com/oauth/access_token",
                data={
                    "client_id": settings.instagram_client_id,
                    "client_secret": settings.instagram_client_secret,
                    "grant_type": "authorization_code",
                    "redirect_uri": redirect_uri,
                    "code": code,
                },
            )
            
            if response.status_code != 200:
                raise ValueError(f"Instagram token exchange failed: {response.text}")
            
            return response.json()

def get_oauth_service(db: AsyncSession) -> OAuthService:
    """Get OAuth service instance."""
    return OAuthService(db)
