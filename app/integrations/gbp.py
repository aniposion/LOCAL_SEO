"""Google Business Profile API integration."""

from datetime import date
from typing import Any

import httpx


class GBPClient:
    """Client for Google Business Profile API."""

    def __init__(self, credentials: dict) -> None:
        self.access_token = credentials.get("access_token")
        self.location_id = credentials.get("location_id")
        self.account_id = credentials.get("account_id")
        self.base_url = "https://mybusiness.googleapis.com/v4"
        self.qanda_base_url = "https://mybusinessqanda.googleapis.com/v1"
        self.timeout = httpx.Timeout(30.0)

    async def _request(
        self,
        method: str,
        endpoint: str,
        **kwargs: Any,
    ) -> dict:
        """Make authenticated request to GBP API."""
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.request(
                method,
                f"{self.base_url}/{endpoint}",
                headers=headers,
                **kwargs,
            )

            if response.status_code == 429:
                raise Exception("Rate limit exceeded")

            if response.status_code >= 400:
                raise Exception(f"GBP API error: {response.status_code} - {response.text}")

            return response.json() if response.text else {}

    async def _qanda_request(
        self,
        method: str,
        endpoint: str,
        **kwargs: Any,
    ) -> dict:
        """Make authenticated request to GBP Q&A API."""
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.request(
                method,
                f"{self.qanda_base_url}/{endpoint}",
                headers=headers,
                **kwargs,
            )

            if response.status_code == 429:
                raise Exception("Rate limit exceeded")

            if response.status_code >= 400:
                raise Exception(f"GBP Q&A API error: {response.status_code} - {response.text}")

            return response.json() if response.text else {}

    async def create_post(
        self,
        title: str | None,
        body: str,
        image_url: str | None = None,
        call_to_action: dict | None = None,
    ) -> str:
        """Create a local post on GBP."""
        post_data: dict[str, Any] = {
            "languageCode": "en",
            "summary": body,
            "topicType": "STANDARD",
        }

        if image_url:
            media_id = await self._upload_media(image_url)
            if media_id:
                post_data["media"] = [{"mediaFormat": "PHOTO", "sourceUrl": image_url}]

        if call_to_action:
            post_data["callToAction"] = call_to_action

        endpoint = f"accounts/{self.account_id}/locations/{self.location_id}/localPosts"
        result = await self._request("POST", endpoint, json=post_data)

        return result.get("name", "").split("/")[-1]

    async def _upload_media(self, image_url: str) -> str | None:
        """Upload media to GBP."""
        endpoint = f"accounts/{self.account_id}/locations/{self.location_id}/media"
        media_data = {
            "mediaFormat": "PHOTO",
            "sourceUrl": image_url,
        }

        try:
            result = await self._request("POST", endpoint, json=media_data)
            return result.get("name", "").split("/")[-1]
        except Exception:
            return None

    async def get_metrics(
        self,
        start_date: date,
        end_date: date,
    ) -> list[dict]:
        """Get performance metrics for the location."""
        endpoint = f"accounts/{self.account_id}/locations/{self.location_id}:reportInsights"

        request_data = {
            "locationNames": [f"accounts/{self.account_id}/locations/{self.location_id}"],
            "basicRequest": {
                "metricRequests": [
                    {"metric": "QUERIES_DIRECT"},
                    {"metric": "QUERIES_INDIRECT"},
                    {"metric": "VIEWS_MAPS"},
                    {"metric": "VIEWS_SEARCH"},
                    {"metric": "ACTIONS_WEBSITE"},
                    {"metric": "ACTIONS_PHONE"},
                    {"metric": "ACTIONS_DRIVING_DIRECTIONS"},
                ],
                "timeRange": {
                    "startTime": f"{start_date.isoformat()}T00:00:00Z",
                    "endTime": f"{end_date.isoformat()}T23:59:59Z",
                },
            },
        }

        try:
            result = await self._request("POST", endpoint, json=request_data)
            location_metrics = result.get("locationMetrics", [])

            if not location_metrics:
                return []

            metrics = location_metrics[0].get("metricValues", [])
            aggregated = {
                "date": end_date,
                "impressions": 0,
                "clicks": 0,
                "calls": 0,
                "direction_requests": 0,
            }

            for metric in metrics:
                metric_name = metric.get("metric", "")
                total = metric.get("totalValue", {}).get("value", 0)

                if metric_name in ["VIEWS_MAPS", "VIEWS_SEARCH"]:
                    aggregated["impressions"] += int(total)
                elif metric_name == "ACTIONS_WEBSITE":
                    aggregated["clicks"] += int(total)
                elif metric_name == "ACTIONS_PHONE":
                    aggregated["calls"] += int(total)
                elif metric_name == "ACTIONS_DRIVING_DIRECTIONS":
                    aggregated["direction_requests"] += int(total)

            return [aggregated]

        except Exception:
            return []

    async def get_reviews(self, page_size: int = 50) -> list[dict]:
        """Get reviews for the location."""
        endpoint = f"accounts/{self.account_id}/locations/{self.location_id}/reviews"
        result = await self._request("GET", endpoint, params={"pageSize": page_size})
        return result.get("reviews", [])

    async def get_questions(self, location_id: str | None = None) -> dict:
        """Get questions for the location from GBP Q&A."""
        target_location_id = location_id or self.location_id
        endpoint = f"locations/{target_location_id}/questions"
        return await self._qanda_request("GET", endpoint, params={"pageSize": 50})

    async def answer_question(
        self,
        location_id: str | None,
        question_id: str,
        answer_text: str,
    ) -> dict:
        """Post an answer to a GBP question."""
        target_location_id = location_id or self.location_id
        endpoint = f"locations/{target_location_id}/questions/{question_id}/answers"
        payload = {"answer": {"text": answer_text}}
        return await self._qanda_request("POST", endpoint, json=payload)
