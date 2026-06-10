"""P4: Google Business Profile API service."""

import logging
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

import httpx

from app.core.config import settings
from app.core.time import utc_now_naive

logger = logging.getLogger(__name__)

# Google API endpoints
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"
GBP_API_BASE = "https://mybusinessbusinessinformation.googleapis.com/v1"
GBP_INSIGHTS_API = "https://businessprofileperformance.googleapis.com/v1"
GBP_REVIEWS_API = "https://mybusiness.googleapis.com/v4"


class GoogleAPIService:
    """Service for Google Business Profile API operations.
    
    Handles:
    - OAuth 2.0 flow
    - Location management
    - Reviews & replies
    - Performance insights
    - Posts & updates
    """

    def __init__(self):
        self.client_id = settings.google_client_id
        self.client_secret = settings.google_client_secret
        
        # Default scopes for GBP
        self.default_scopes = [
            "openid",
            "email",
            "profile",
            "https://www.googleapis.com/auth/business.manage",
        ]

    # ====================
    # OAuth Flow
    # ====================

    def get_auth_url(
        self,
        redirect_uri: str,
        state: str,
        scopes: list[str] = None,
    ) -> str:
        """Generate OAuth authorization URL."""
        scopes = scopes or self.default_scopes
        
        params = {
            "client_id": self.client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": " ".join(scopes),
            "state": state,
            "access_type": "offline",
            "prompt": "consent",  # Force consent to get refresh token
        }
        
        query = "&".join(f"{k}={v}" for k, v in params.items())
        return f"{GOOGLE_AUTH_URL}?{query}"

    async def exchange_code(
        self,
        code: str,
        redirect_uri: str,
    ) -> dict:
        """Exchange authorization code for tokens."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                GOOGLE_TOKEN_URL,
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": redirect_uri,
                },
            )
            
            if response.status_code != 200:
                logger.error(f"Token exchange failed: {response.text}")
                raise ValueError(f"Token exchange failed: {response.text}")
            
            return response.json()

    async def refresh_access_token(self, refresh_token: str) -> dict:
        """Refresh access token using refresh token."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                GOOGLE_TOKEN_URL,
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "refresh_token": refresh_token,
                    "grant_type": "refresh_token",
                },
            )
            
            if response.status_code != 200:
                logger.error(f"Token refresh failed: {response.text}")
                raise ValueError(f"Token refresh failed: {response.text}")
            
            return response.json()

    async def get_user_info(self, access_token: str) -> dict:
        """Get Google user info."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                GOOGLE_USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            
            if response.status_code != 200:
                raise ValueError(f"Failed to get user info: {response.text}")
            
            return response.json()

    async def revoke_token(self, token: str) -> bool:
        """Revoke a token."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://oauth2.googleapis.com/revoke",
                params={"token": token},
            )
            return response.status_code == 200

    # ====================
    # GBP Locations
    # ====================

    async def get_accounts(self, access_token: str) -> list[dict]:
        """Get GBP accounts."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{GBP_API_BASE}/accounts",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            
            if response.status_code != 200:
                logger.error(f"Failed to get accounts: {response.text}")
                return []
            
            data = response.json()
            return data.get("accounts", [])

    async def get_locations(
        self,
        access_token: str,
        account_name: str = None,
    ) -> list[dict]:
        """Get GBP locations for an account."""
        # If no account specified, get all accounts first
        if not account_name:
            accounts = await self.get_accounts(access_token)
            if not accounts:
                return []
            account_name = accounts[0].get("name")
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{GBP_API_BASE}/{account_name}/locations",
                headers={"Authorization": f"Bearer {access_token}"},
                params={"readMask": "name,title,storefrontAddress,phoneNumbers,websiteUri,categories"},
            )
            
            if response.status_code != 200:
                logger.error(f"Failed to get locations: {response.text}")
                return []
            
            data = response.json()
            return data.get("locations", [])

    async def get_location(
        self,
        access_token: str,
        location_name: str,
    ) -> Optional[dict]:
        """Get single location details."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{GBP_API_BASE}/{location_name}",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            
            if response.status_code != 200:
                return None
            
            return response.json()

    # ====================
    # Reviews
    # ====================

    async def get_reviews(
        self,
        access_token: str,
        location_name: str,
        page_size: int = 50,
        page_token: str = None,
    ) -> dict:
        """Get reviews for a location."""
        async with httpx.AsyncClient() as client:
            params = {"pageSize": page_size}
            if page_token:
                params["pageToken"] = page_token
            
            # Note: Reviews API uses different base URL
            response = await client.get(
                f"{GBP_REVIEWS_API}/{location_name}/reviews",
                headers={"Authorization": f"Bearer {access_token}"},
                params=params,
            )
            
            if response.status_code != 200:
                logger.error(f"Failed to get reviews: {response.text}")
                return {"reviews": [], "totalReviewCount": 0}
            
            return response.json()

    async def reply_to_review(
        self,
        access_token: str,
        review_name: str,
        comment: str,
    ) -> dict:
        """Reply to a review."""
        async with httpx.AsyncClient() as client:
            response = await client.put(
                f"{GBP_REVIEWS_API}/{review_name}/reply",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                },
                json={"comment": comment},
            )
            
            if response.status_code not in [200, 201]:
                logger.error(f"Failed to reply to review: {response.text}")
                raise ValueError(f"Failed to reply: {response.text}")
            
            return response.json()

    async def delete_review_reply(
        self,
        access_token: str,
        review_name: str,
    ) -> bool:
        """Delete a review reply."""
        async with httpx.AsyncClient() as client:
            response = await client.delete(
                f"{GBP_REVIEWS_API}/{review_name}/reply",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            return response.status_code == 200

    # ====================
    # Insights / Performance
    # ====================

    async def get_insights(
        self,
        access_token: str,
        location_name: str,
        start_date: datetime = None,
        end_date: datetime = None,
    ) -> dict:
        """Get performance insights for a location."""
        if not end_date:
            end_date = utc_now_naive()
        if not start_date:
            start_date = end_date - timedelta(days=30)
        
        # Format dates
        start_str = start_date.strftime("%Y-%m-%d")
        end_str = end_date.strftime("%Y-%m-%d")
        
        async with httpx.AsyncClient() as client:
            # Get daily metrics
            response = await client.get(
                f"{GBP_INSIGHTS_API}/{location_name}:getDailyMetricsTimeSeries",
                headers={"Authorization": f"Bearer {access_token}"},
                params={
                    "dailyMetric": [
                        "BUSINESS_IMPRESSIONS_DESKTOP_MAPS",
                        "BUSINESS_IMPRESSIONS_DESKTOP_SEARCH",
                        "BUSINESS_IMPRESSIONS_MOBILE_MAPS",
                        "BUSINESS_IMPRESSIONS_MOBILE_SEARCH",
                        "CALL_CLICKS",
                        "WEBSITE_CLICKS",
                        "BUSINESS_DIRECTION_REQUESTS",
                    ],
                    "dailyRange.startDate.year": start_date.year,
                    "dailyRange.startDate.month": start_date.month,
                    "dailyRange.startDate.day": start_date.day,
                    "dailyRange.endDate.year": end_date.year,
                    "dailyRange.endDate.month": end_date.month,
                    "dailyRange.endDate.day": end_date.day,
                },
            )
            
            if response.status_code != 200:
                logger.error(f"Failed to get insights: {response.text}")
                return {}
            
            return response.json()

    # ====================
    # Posts
    # ====================

    async def create_post(
        self,
        access_token: str,
        location_name: str,
        post_data: dict,
    ) -> dict:
        """Create a GBP post."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{GBP_API_BASE}/{location_name}/localPosts",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                },
                json=post_data,
            )
            
            if response.status_code not in [200, 201]:
                logger.error(f"Failed to create post: {response.text}")
                raise ValueError(f"Failed to create post: {response.text}")
            
            return response.json()

    async def get_posts(
        self,
        access_token: str,
        location_name: str,
        page_size: int = 20,
    ) -> list[dict]:
        """Get posts for a location."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{GBP_API_BASE}/{location_name}/localPosts",
                headers={"Authorization": f"Bearer {access_token}"},
                params={"pageSize": page_size},
            )
            
            if response.status_code != 200:
                return []
            
            data = response.json()
            return data.get("localPosts", [])

    async def delete_post(
        self,
        access_token: str,
        post_name: str,
    ) -> bool:
        """Delete a GBP post."""
        async with httpx.AsyncClient() as client:
            response = await client.delete(
                f"{GBP_API_BASE}/{post_name}",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            return response.status_code == 200


# Singleton instance
_google_api: Optional[GoogleAPIService] = None


def get_google_api_service() -> GoogleAPIService:
    """Get Google API service singleton."""
    global _google_api
    if _google_api is None:
        _google_api = GoogleAPIService()
    return _google_api
