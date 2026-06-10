"""Google Places API (New) integration for competitor analysis."""

import logging
from typing import Any, Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class GooglePlacesClient:
    """Client for Google Places API (New)."""

    BASE_URL = "https://places.googleapis.com/v1"

    def __init__(self, api_key: Optional[str] = None):
        """Initialize Google Places client."""
        self.api_key = api_key or settings.gbp_api_key
        if not self.api_key:
            raise ValueError("Google Places API key is required")

    async def nearby_search(
        self,
        latitude: float,
        longitude: float,
        radius_meters: int,
        business_type: str,
        max_results: int = 20,
    ) -> list[dict[str, Any]]:
        """
        Search for nearby places.

        Args:
            latitude: Latitude of center point
            longitude: Longitude of center point
            radius_meters: Search radius in meters
            business_type: Type of business to search for
            max_results: Maximum number of results

        Returns:
            List of place dictionaries
        """
        url = f"{self.BASE_URL}/places:searchNearby"
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self.api_key,
            "X-Goog-FieldMask": "places.id,places.displayName,places.formattedAddress,places.rating,places.userRatingCount,places.types,places.location",
        }

        payload = {
            "locationRestriction": {
                "circle": {
                    "center": {"latitude": latitude, "longitude": longitude},
                    "radius": radius_meters,
                }
            },
            "includedTypes": [business_type],
            "maxResultCount": max_results,
            "rankPreference": "DISTANCE",
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                data = response.json()
                return data.get("places", [])
        except httpx.HTTPError as e:
            logger.error(f"Google Places API error: {e}")
            raise

    async def get_place_details(
        self, place_id: str, include_reviews: bool = True
    ) -> dict[str, Any]:
        """
        Get detailed information about a place.

        Args:
            place_id: Google Place ID
            include_reviews: Whether to include reviews

        Returns:
            Place details dictionary
        """
        url = f"{self.BASE_URL}/places/{place_id}"
        
        field_mask = "id,displayName,formattedAddress,rating,userRatingCount,types,location,regularOpeningHours,websiteUri,internationalPhoneNumber"
        if include_reviews:
            field_mask += ",reviews"

        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self.api_key,
            "X-Goog-FieldMask": field_mask,
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Google Places API error for place {place_id}: {e}")
            raise

    async def get_place_reviews(
        self, place_id: str, max_reviews: int = 50
    ) -> list[dict[str, Any]]:
        """
        Get reviews for a place.

        Args:
            place_id: Google Place ID
            max_reviews: Maximum number of reviews to fetch

        Returns:
            List of review dictionaries
        """
        try:
            place_details = await self.get_place_details(place_id, include_reviews=True)
            reviews = place_details.get("reviews", [])
            return reviews[:max_reviews]
        except Exception as e:
            logger.error(f"Error fetching reviews for place {place_id}: {e}")
            return []

    @staticmethod
    def calculate_distance(
        lat1: float, lon1: float, lat2: float, lon2: float
    ) -> float:
        """
        Calculate distance between two coordinates in miles using Haversine formula.

        Args:
            lat1: Latitude of first point
            lon1: Longitude of first point
            lat2: Latitude of second point
            lon2: Longitude of second point

        Returns:
            Distance in miles
        """
        from math import asin, cos, radians, sin, sqrt

        # Convert to radians
        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])

        # Haversine formula
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
        c = 2 * asin(sqrt(a))

        # Radius of earth in miles
        r = 3956
        return c * r
