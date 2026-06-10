"""Instagram Graph API integration."""

from datetime import date, datetime, time, timezone
from typing import Any

import httpx


def _date_to_unix(value: date) -> int:
    """Convert a date to a UTC midnight Unix timestamp."""
    return int(datetime.combine(value, time.min, tzinfo=timezone.utc).timestamp())


class InstagramClient:
    """Client for Instagram Graph API."""

    def __init__(self, credentials: dict) -> None:
        self.access_token = credentials.get("access_token")
        self.ig_user_id = (
            credentials.get("ig_user_id")
            or credentials.get("instagram_account_id")
            or credentials.get("account_id")
        )
        self.base_url = "https://graph.facebook.com/v18.0"
        self.timeout = httpx.Timeout(30.0)

    async def _request(
        self,
        method: str,
        endpoint: str,
        **kwargs: Any,
    ) -> dict:
        """Make authenticated request to Instagram API."""
        params = kwargs.pop("params", {})
        params["access_token"] = self.access_token

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.request(
                method,
                f"{self.base_url}/{endpoint}",
                params=params,
                **kwargs,
            )

            if response.status_code == 429:
                raise Exception("Rate limit exceeded")

            if response.status_code >= 400:
                raise Exception(f"Instagram API error: {response.status_code} - {response.text}")

            return response.json() if response.text else {}

    def _require_ig_user_id(self) -> str:
        if not self.ig_user_id:
            raise ValueError("Instagram business account ID is required")
        return self.ig_user_id

    async def publish_image(
        self,
        image_url: str,
        caption: str,
        hashtags: list[str] | None = None,
    ) -> str:
        """Publish an image post to Instagram."""
        # Combine caption with hashtags
        full_caption = caption
        if hashtags:
            hashtag_str = " ".join(f"#{tag.lstrip('#')}" for tag in hashtags)
            full_caption = f"{caption}\n\n{hashtag_str}"

        # Step 1: Create media container
        container_data = await self._request(
            "POST",
            f"{self.ig_user_id}/media",
            params={
                "image_url": image_url,
                "caption": full_caption,
            },
        )

        container_id = container_data.get("id")
        if not container_id:
            raise Exception("Failed to create media container")

        # Step 2: Wait for container to be ready (simplified - in production use polling)
        import asyncio
        await asyncio.sleep(5)

        # Step 3: Publish the container
        publish_data = await self._request(
            "POST",
            f"{self.ig_user_id}/media_publish",
            params={"creation_id": container_id},
        )

        return publish_data.get("id", "")

    async def publish_carousel(
        self,
        image_urls: list[str],
        caption: str,
        hashtags: list[str] | None = None,
    ) -> str:
        """Publish a carousel post to Instagram."""
        # Create containers for each image
        children_ids = []
        for url in image_urls[:10]:  # Max 10 images
            container = await self._request(
                "POST",
                f"{self.ig_user_id}/media",
                params={
                    "image_url": url,
                    "is_carousel_item": "true",
                },
            )
            children_ids.append(container.get("id"))

        # Combine caption with hashtags
        full_caption = caption
        if hashtags:
            hashtag_str = " ".join(f"#{tag.lstrip('#')}" for tag in hashtags)
            full_caption = f"{caption}\n\n{hashtag_str}"

        # Create carousel container
        carousel = await self._request(
            "POST",
            f"{self.ig_user_id}/media",
            params={
                "media_type": "CAROUSEL",
                "children": ",".join(children_ids),
                "caption": full_caption,
            },
        )

        carousel_id = carousel.get("id")

        # Wait and publish
        import asyncio
        await asyncio.sleep(5)

        publish_data = await self._request(
            "POST",
            f"{self.ig_user_id}/media_publish",
            params={"creation_id": carousel_id},
        )

        return publish_data.get("id", "")

    async def get_insights(
        self,
        start_date: date,
        end_date: date,
    ) -> list[dict]:
        """Get account insights."""
        # Get account-level insights
        insights_data = await self._request(
            "GET",
            f"{self.ig_user_id}/insights",
            params={
                "metric": "reach,impressions,profile_views",
                "period": "day",
                "since": _date_to_unix(start_date),
                "until": _date_to_unix(end_date),
            },
        )

        # Get recent media insights
        media_data = await self._request(
            "GET",
            f"{self.ig_user_id}/media",
            params={
                "fields": "id,timestamp,like_count,comments_count,insights.metric(reach,impressions,saved,shares)",
                "limit": 50,
            },
        )

        # Aggregate by date
        daily_metrics: dict[str, dict] = {}

        for media in media_data.get("data", []):
            media_date = media.get("timestamp", "")[:10]
            if media_date not in daily_metrics:
                daily_metrics[media_date] = {
                    "date": date.fromisoformat(media_date),
                    "reach": 0,
                    "likes": 0,
                    "comments": 0,
                    "shares": 0,
                    "saves": 0,
                }

            daily_metrics[media_date]["likes"] += media.get("like_count", 0)
            daily_metrics[media_date]["comments"] += media.get("comments_count", 0)

            # Get insights if available
            insights = media.get("insights", {}).get("data", [])
            for insight in insights:
                metric = insight.get("name", "")
                value = insight.get("values", [{}])[0].get("value", 0)
                if metric == "reach":
                    daily_metrics[media_date]["reach"] += value
                elif metric == "saved":
                    daily_metrics[media_date]["saves"] += value
                elif metric == "shares":
                    daily_metrics[media_date]["shares"] += value

        return list(daily_metrics.values())

    async def get_media_insights(self, media_id: str) -> dict:
        """Get insights for a specific media post."""
        data = await self._request(
            "GET",
            f"{media_id}/insights",
            params={
                "metric": "reach,impressions,engagement,saved,shares",
            },
        )

        insights = {}
        for item in data.get("data", []):
            insights[item.get("name")] = item.get("values", [{}])[0].get("value", 0)

        return insights

    async def get_conversations(self, limit: int = 20) -> dict:
        """Get Instagram business conversations with recent message snippets."""
        ig_user_id = self._require_ig_user_id()
        return await self._request(
            "GET",
            f"{ig_user_id}/conversations",
            params={
                "platform": "instagram",
                "limit": limit,
                "fields": (
                    "id,participants,"
                    "messages.limit(10){id,message,from,created_time,is_echo}"
                ),
            },
        )

    async def send_dm(self, recipient_id: str, message_text: str) -> str:
        """Send an Instagram direct message through the business messaging endpoint."""
        ig_user_id = self._require_ig_user_id()
        result = await self._request(
            "POST",
            f"{ig_user_id}/messages",
            json={
                "recipient": {"id": recipient_id},
                "message": {"text": message_text},
            },
        )
        return str(result.get("message_id") or result.get("id") or "")

    async def get_comments(self, media_id: str | None = None, limit: int = 20) -> dict:
        """Get comments for a media item, or flatten recent media comments."""
        if media_id:
            return await self._request(
                "GET",
                f"{media_id}/comments",
                params={
                    "limit": limit,
                    "fields": "id,text,username,timestamp,from",
                },
            )

        ig_user_id = self._require_ig_user_id()
        media = await self._request(
            "GET",
            f"{ig_user_id}/media",
            params={
                "limit": limit,
                "fields": "id,comments.limit(10){id,text,username,timestamp,from}",
            },
        )
        comments: list[dict] = []
        for item in media.get("data", []):
            for comment in item.get("comments", {}).get("data", []):
                comment.setdefault("media_id", item.get("id"))
                comments.append(comment)
                if len(comments) >= limit:
                    return {"data": comments}
        return {"data": comments}

    async def reply_to_comment(self, comment_id: str, message_text: str) -> str:
        """Reply publicly to an Instagram comment."""
        result = await self._request(
            "POST",
            f"{comment_id}/replies",
            json={"message": message_text},
        )
        return str(result.get("id") or "")
