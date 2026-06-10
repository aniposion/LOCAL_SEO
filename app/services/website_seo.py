"""Website SEO draft generation, optimization, and publishing service."""

import logging
import re
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.time import utc_now_aware
from app.core.user_messages import integration_unavailable, workflow_failed
from app.services.credits import CreditsService

logger = logging.getLogger(__name__)


class WebsiteSEOUsageLimitError(RuntimeError):
    """Raised when Website SEO generation exceeds the account usage limit."""

    def __init__(self, detail: dict[str, Any]):
        super().__init__(detail.get("message") or "Website SEO usage limit exceeded")
        self.detail = detail


class WebsiteSEOGenerationUnavailableError(RuntimeError):
    """Raised when Website SEO generation returns no usable content."""


class WebsiteSEOService:
    """Service for Website SEO generation, draft storage, and publish history."""

    LOCAL_KEYWORDS = {
        "restaurant": [
            "{cuisine} restaurant in {city}",
            "best {cuisine} near me",
            "{cuisine} food {city}",
            "restaurants in {neighborhood}",
            "{city} dining",
            "food delivery {city}",
        ],
        "spa": [
            "spa near me",
            "{city} spa",
            "massage {city}",
            "facial treatment {city}",
            "best spa in {city}",
            "relaxation spa {neighborhood}",
        ],
        "dentist": [
            "dentist near me",
            "{city} dentist",
            "dental clinic {city}",
            "teeth whitening {city}",
            "emergency dentist {city}",
            "family dentist {neighborhood}",
        ],
        "default": [
            "{business_type} near me",
            "{business_type} in {city}",
            "best {business_type} {city}",
            "{city} {business_type}",
            "{neighborhood} {business_type}",
        ],
    }

    def __init__(self, db: Session):
        self.db = db

    def _preview_usage(self, account_id: UUID, usage_type: str, count: int = 1) -> None:
        result = CreditsService(self.db).preview_usage(str(account_id), usage_type, count)
        if result.get("allowed"):
            return

        raise WebsiteSEOUsageLimitError(
            {
                "error": "Rate limit exceeded",
                "usage_type": usage_type,
                "message": result.get("reason"),
                "remaining_daily": result.get("remaining_daily", 0),
                "remaining_monthly": result.get("remaining_monthly", 0),
                "cooldown_seconds": result.get("cooldown_remaining_seconds", 0),
                "overage_available": result.get("overage_available", False),
                "overage_cost_cents": result.get("overage_cost_cents", 0),
            }
        )

    def _record_usage(self, account_id: UUID, usage_type: str, count: int = 1) -> None:
        result = CreditsService(self.db).use_credits(str(account_id), usage_type, count)
        if result.get("allowed"):
            return

        logger.warning(
            "Website SEO usage record failed after successful %s generation for account %s: %s",
            usage_type,
            account_id,
            result.get("reason"),
        )

    def _require_non_empty_generated_content(self, content: str, content_type: str) -> str:
        cleaned = (content or "").strip()
        if cleaned:
            return cleaned

        raise WebsiteSEOGenerationUnavailableError(
            workflow_failed(
                f"Website SEO {content_type} generation returned no content",
                "Try again in a few minutes or check the AI provider configuration",
            )
        )

    def _save_draft(
        self,
        *,
        location_id: UUID,
        content_type: str,
        payload: dict[str, Any],
        title: str | None = None,
        slug: str | None = None,
        page_type: str | None = None,
        source_topic: str | None = None,
    ) -> UUID:
        from app.models.website_seo import (
            WebsiteSEOApprovalStatus,
            WebsiteSEODraft,
            WebsiteSEOContentType,
        )

        draft = WebsiteSEODraft(
            location_id=location_id,
            content_type=WebsiteSEOContentType(content_type),
            title=title,
            slug=slug,
            page_type=page_type,
            source_topic=source_topic,
            payload=payload,
            approval_status=WebsiteSEOApprovalStatus.NOT_REQUESTED.value,
        )
        self.db.add(draft)
        self.db.commit()
        self.db.refresh(draft)
        return draft.id

    async def _notify_publish_failure(
        self,
        *,
        location_id: UUID,
        account_id: UUID,
        content_type: str,
        draft_id: UUID | None,
        draft_title: str | None,
        error_message: str,
        location_name: str | None,
    ) -> None:
        """Persist an operator-facing alert when website publishing fails."""
        from app.services.notification import NotificationService

        draft_label = (draft_title or content_type.replace("_", " ")).strip()
        await NotificationService(self.db).send_notification(
            account_id=account_id,
            title="Website publish failed",
            message=(
                f"Website publishing for {location_name or 'your location'} failed"
                f" while pushing {draft_label}."
                f"\n\nReason: {error_message}"
            ),
            notification_type="website_publish_failed",
            data={
                "url": "/dashboard/seo",
                "location_id": str(location_id),
                "draft_id": str(draft_id) if draft_id else None,
                "content_type": content_type,
                "error_message": error_message,
            },
        )

    def list_history(
        self,
        *,
        location_id: UUID,
        content_type: str | None = None,
        status: str | None = None,
        approval_status: str | None = None,
        search: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ):
        from app.models.website_seo import WebsiteSEODraft, WebsiteSEOContentType, WebsiteSEODraftStatus

        query = self.db.query(WebsiteSEODraft).filter(WebsiteSEODraft.location_id == location_id)
        if content_type:
            query = query.filter(WebsiteSEODraft.content_type == WebsiteSEOContentType(content_type))
        if status:
            if status == "archived":
                query = query.filter(WebsiteSEODraft.archived_at.is_not(None))
            else:
                query = query.filter(
                    WebsiteSEODraft.archived_at.is_(None),
                    WebsiteSEODraft.status == WebsiteSEODraftStatus(status),
                )
        else:
            query = query.filter(WebsiteSEODraft.archived_at.is_(None))
        if approval_status:
            query = query.filter(WebsiteSEODraft.approval_status == approval_status)
        if search:
            like_pattern = f"%{search.strip()}%"
            query = query.filter(
                WebsiteSEODraft.title.ilike(like_pattern)
                | WebsiteSEODraft.slug.ilike(like_pattern)
                | WebsiteSEODraft.source_topic.ilike(like_pattern)
                | WebsiteSEODraft.last_error.ilike(like_pattern)
            )
        total = query.count()
        items = query.order_by(WebsiteSEODraft.created_at.desc()).offset(max(offset, 0)).limit(min(max(limit, 1), 100)).all()
        return items, total

    def archive_drafts(
        self,
        *,
        location_id: UUID,
        draft_ids: list[UUID],
        reason: str | None = None,
    ) -> dict[str, Any]:
        from app.models.website_seo import WebsiteSEODraft

        now = utc_now_aware()
        drafts = (
            self.db.query(WebsiteSEODraft)
            .filter(
                WebsiteSEODraft.location_id == location_id,
                WebsiteSEODraft.id.in_(draft_ids),
            )
            .all()
        )
        if not drafts:
            return {"archived_count": 0, "archived_ids": []}

        archived_ids: list[str] = []
        for draft in drafts:
            if draft.archived_at is not None:
                continue
            draft.archived_at = now
            draft.archived_reason = reason
            archived_ids.append(str(draft.id))

        self.db.commit()
        return {"archived_count": len(archived_ids), "archived_ids": archived_ids}

    def get_draft(self, *, draft_id: UUID, location_id: UUID):
        from app.models.website_seo import WebsiteSEODraft

        return (
            self.db.query(WebsiteSEODraft)
            .filter(WebsiteSEODraft.id == draft_id, WebsiteSEODraft.location_id == location_id)
            .first()
        )

    def request_approval(self, *, draft_id: UUID, location_id: UUID):
        """Move a draft into approval review."""
        from app.models.website_seo import WebsiteSEOApprovalStatus

        draft = self.get_draft(draft_id=draft_id, location_id=location_id)
        if not draft:
            return None
        if draft.archived_at is not None:
            return None

        draft.approval_status = WebsiteSEOApprovalStatus.PENDING.value
        draft.approval_requested_at = utc_now_aware()
        draft.approved_at = None
        draft.rejected_at = None
        draft.rejection_reason = None
        self.db.commit()
        self.db.refresh(draft)
        return draft

    def approve_draft(self, *, draft_id: UUID, location_id: UUID):
        """Approve a draft for publishing."""
        from app.models.website_seo import WebsiteSEOApprovalStatus

        draft = self.get_draft(draft_id=draft_id, location_id=location_id)
        if not draft:
            return None
        if draft.archived_at is not None:
            return None

        draft.approval_status = WebsiteSEOApprovalStatus.APPROVED.value
        draft.approved_at = utc_now_aware()
        draft.rejected_at = None
        draft.rejection_reason = None
        self.db.commit()
        self.db.refresh(draft)
        return draft

    def reject_draft(self, *, draft_id: UUID, location_id: UUID, reason: str | None = None):
        """Reject a draft before publishing."""
        from app.models.website_seo import WebsiteSEOApprovalStatus

        draft = self.get_draft(draft_id=draft_id, location_id=location_id)
        if not draft:
            return None
        if draft.archived_at is not None:
            return None

        draft.approval_status = WebsiteSEOApprovalStatus.REJECTED.value
        draft.rejected_at = utc_now_aware()
        draft.rejection_reason = reason
        self.db.commit()
        self.db.refresh(draft)
        return draft

    def _update_channel_publish_state(
        self,
        *,
        location_id: UUID,
        success: bool,
        error_message: str | None = None,
        published_url: str | None = None,
        provider_reference: str | None = None,
    ) -> None:
        from app.models.channel import Channel, ChannelStatus, ChannelType

        channel = (
            self.db.query(Channel)
            .filter(
                Channel.location_id == location_id,
                Channel.type == ChannelType.WEBSITE,
                Channel.is_active.is_(True),
            )
            .first()
        )
        if not channel:
            return

        meta = dict(channel.meta or {})
        now = utc_now_aware()
        channel.last_sync_at = now

        if success:
            channel.status = ChannelStatus.CONNECTED
            channel.error_message = None
            meta["last_publish_succeeded_at"] = now.isoformat()
            if published_url:
                meta["last_published_url"] = published_url
            if provider_reference:
                meta["last_publish_provider_reference"] = provider_reference
        else:
            channel.status = ChannelStatus.ERROR
            channel.error_count = (channel.error_count or 0) + 1
            channel.error_message = error_message
            meta["last_publish_failed_at"] = now.isoformat()
            meta["last_publish_failed_error"] = error_message

        channel.meta = meta

    async def generate_meta_tags(
        self,
        location_id: UUID,
        page_type: str = "home",
        service_name: str | None = None,
    ) -> dict[str, str]:
        from app.models.location import Location

        location = self.db.query(Location).filter(Location.id == location_id).first()
        if not location:
            return {}

        business_name = location.name
        city = getattr(location, "city", "") or ""
        category = getattr(location, "category", "business") or "business"

        if page_type == "home":
            title = f"{business_name} | Best {category.title()} in {city}"
            description = (
                f"{business_name} is a top-rated {category} in {city}. "
                f"Visit us for exceptional service and quality. "
                f"Call now or book online!"
            )
        elif page_type == "service" and service_name:
            title = f"{service_name} | {business_name} - {city}"
            description = (
                f"Get the best {service_name} at {business_name} in {city}. "
                f"Professional service, great prices. Book your appointment today!"
            )
        elif page_type == "about":
            title = f"About {business_name} | {city} {category.title()}"
            description = (
                f"Learn about {business_name}, your trusted {category} in {city}. "
                f"Our story, team, and commitment to excellence."
            )
        elif page_type == "contact":
            title = f"Contact {business_name} | {city}"
            description = (
                f"Contact {business_name} in {city}. "
                f"Get directions, hours, and book your appointment. "
                f"We're here to help!"
            )
        else:
            title = f"{business_name} | {city}"
            description = f"Visit {business_name} in {city} for quality {category} services."

        keywords = await self.analyze_local_keywords(location_id)
        keywords_str = ", ".join(keywords[:10])
        schema_json = self._generate_schema_json(location, page_type)

        result = {
            "title": title[:60],
            "description": description[:160],
            "keywords": keywords_str,
            "og_title": title[:60],
            "og_description": description[:160],
            "og_type": "website",
            "schema_json": schema_json,
        }
        draft_id = self._save_draft(
            location_id=location_id,
            content_type="meta_tags",
            payload=result,
            title=result["title"],
            page_type=page_type,
            source_topic=service_name,
        )
        result["draft_id"] = str(draft_id)
        return result

    async def analyze_local_keywords(self, location_id: UUID, limit: int = 20) -> list[str]:
        from app.models.location import Location

        location = self.db.query(Location).filter(Location.id == location_id).first()
        if not location:
            return []

        category = getattr(location, "category", "default") or "default"
        city = getattr(location, "city", "") or ""
        neighborhood = getattr(location, "neighborhood", "") or city
        services = getattr(location, "services", []) or []
        templates = self.LOCAL_KEYWORDS.get(category, self.LOCAL_KEYWORDS["default"])

        keywords: list[str] = []
        for template in templates:
            keyword = template.format(
                business_type=category,
                cuisine=category if category == "restaurant" else "",
                city=city,
                neighborhood=neighborhood,
            ).strip()
            if keyword and keyword not in keywords:
                keywords.append(keyword)

        for service in services[:5]:
            keywords.append(f"{service} {city}")
            keywords.append(f"{service} near me")

        keywords.append(location.name)
        keywords.append(f"{location.name} {city}")
        return keywords[:limit]

    async def generate_service_page(
        self,
        location_id: UUID,
        service_name: str,
        service_description: str | None = None,
    ) -> dict[str, Any]:
        from app.integrations.llm import LLMClient
        from app.models.location import Location

        location = self.db.query(Location).filter(Location.id == location_id).first()
        if not location:
            return {"error": "Location not found"}
        self._preview_usage(location.account_id, "ai_content", 1)

        city = getattr(location, "city", "") or ""
        meta_tags = await self.generate_meta_tags(
            location_id=location_id,
            page_type="service",
            service_name=service_name,
        )

        llm = LLMClient()
        prompt = f"""Write an SEO-optimized service page for a local business.

Business: {location.name}
Service: {service_name}
Location: {city}
Description: {service_description or 'Professional service'}

Requirements:
1. Include the service name and location naturally in the content
2. Write 3-4 paragraphs
3. Include a call-to-action
4. Use headings (H2, H3)
5. Mention benefits and features
6. Keep it professional but friendly

Output in HTML format."""

        content = self._require_non_empty_generated_content(
            await llm.generate(prompt),
            "service page",
        )
        result = {
            "service_name": service_name,
            "meta_tags": meta_tags,
            "content_html": content,
            "keywords": await self.analyze_local_keywords(location_id),
        }
        draft_id = self._save_draft(
            location_id=location_id,
            content_type="service_page",
            payload=result,
            title=f"{service_name} | {location.name}",
            page_type="service",
            source_topic=service_name,
        )
        self._record_usage(location.account_id, "ai_content", 1)
        result["draft_id"] = str(draft_id)
        return result

    async def generate_blog_post(
        self,
        location_id: UUID,
        topic: str,
        keywords: list[str] | None = None,
    ) -> dict[str, Any]:
        from app.integrations.llm import LLMClient
        from app.models.location import Location

        location = self.db.query(Location).filter(Location.id == location_id).first()
        if not location:
            return {"error": "Location not found"}
        self._preview_usage(location.account_id, "ai_content", 1)

        city = getattr(location, "city", "") or ""
        category = getattr(location, "category", "business") or "business"
        if not keywords:
            keywords = await self.analyze_local_keywords(location_id)

        llm = LLMClient()
        prompt = f"""Write an SEO-optimized blog post for a local {category} business.

Business: {location.name}
Location: {city}
Topic: {topic}
Target Keywords: {', '.join(keywords[:5])}

Requirements:
1. Write 500-800 words
2. Include the target keywords naturally (2-3% density)
3. Use proper heading structure (H1, H2, H3)
4. Include internal linking suggestions
5. Add a compelling introduction and conclusion
6. Include a call-to-action at the end
7. Make it informative and valuable to readers

Output format:
---
title: [SEO Title]
meta_description: [Meta description under 160 chars]
---

[Blog content in Markdown]"""

        content = self._require_non_empty_generated_content(
            await llm.generate(prompt),
            "blog post",
        )
        title = ""
        meta_description = ""
        body = content

        if "---" in content:
            parts = content.split("---")
            if len(parts) >= 3:
                frontmatter = parts[1]
                body = "---".join(parts[2:]).strip()
                for line in frontmatter.split("\n"):
                    if line.startswith("title:"):
                        title = line.replace("title:", "").strip().strip('"')
                    elif line.startswith("meta_description:"):
                        meta_description = line.replace("meta_description:", "").strip().strip('"')

        body = self._require_non_empty_generated_content(body, "blog post")

        slug = re.sub(r"[^a-z0-9]+", "-", topic.lower()).strip("-")
        result = {
            "title": title or topic,
            "slug": slug,
            "meta_description": meta_description,
            "content_markdown": body,
            "keywords": keywords[:10],
            "word_count": len(body.split()),
        }
        draft_id = self._save_draft(
            location_id=location_id,
            content_type="blog_post",
            payload=result,
            title=result["title"],
            slug=slug,
            source_topic=topic,
        )
        self._record_usage(location.account_id, "ai_content", 1)
        result["draft_id"] = str(draft_id)
        return result

    async def optimize_existing_page(
        self,
        location_id: UUID,
        page_url: str,
        current_content: str,
    ) -> dict[str, Any]:
        word_count = len(current_content.split())
        has_h1 = "<h1" in current_content.lower() or "# " in current_content
        has_h2 = "<h2" in current_content.lower() or "## " in current_content
        keywords = await self.analyze_local_keywords(location_id)

        keyword_presence: dict[str, int] = {}
        content_lower = current_content.lower()
        for kw in keywords[:10]:
            keyword_presence[kw] = content_lower.count(kw.lower())

        recommendations: list[dict[str, str]] = []
        if word_count < 300:
            recommendations.append({
                "type": "content_length",
                "priority": "high",
                "message": f"Content is too short ({word_count} words). Aim for 500+ words.",
            })
        if not has_h1:
            recommendations.append({
                "type": "heading",
                "priority": "high",
                "message": "Missing H1 heading. Add a main heading with your primary keyword.",
            })
        if not has_h2:
            recommendations.append({
                "type": "heading",
                "priority": "medium",
                "message": "No H2 subheadings found. Add subheadings to structure content.",
            })

        missing_keywords = [kw for kw, count in keyword_presence.items() if count == 0]
        if missing_keywords:
            recommendations.append({
                "type": "keywords",
                "priority": "medium",
                "message": f"Missing keywords: {', '.join(missing_keywords[:5])}",
            })

        meta_tags = await self.generate_meta_tags(location_id)
        result = {
            "page_url": page_url,
            "analysis": {
                "word_count": word_count,
                "has_h1": has_h1,
                "has_h2": has_h2,
                "keyword_presence": keyword_presence,
            },
            "recommendations": recommendations,
            "suggested_meta_tags": meta_tags,
            "target_keywords": keywords[:10],
        }
        draft_id = self._save_draft(
            location_id=location_id,
            content_type="optimization",
            payload=result,
            title=page_url,
            source_topic=page_url,
        )
        result["draft_id"] = str(draft_id)
        return result

    def _generate_schema_json(self, location, page_type: str) -> str:
        import json

        category = getattr(location, "category", "LocalBusiness") or "LocalBusiness"
        schema_type_map = {
            "restaurant": "Restaurant",
            "spa": "HealthAndBeautyBusiness",
            "dentist": "Dentist",
            "gym": "HealthClub",
            "salon": "BeautySalon",
        }
        schema_type = schema_type_map.get(category, "LocalBusiness")

        schema = {
            "@context": "https://schema.org",
            "@type": schema_type,
            "name": location.name,
            "address": {
                "@type": "PostalAddress",
                "streetAddress": location.address or "",
                "addressLocality": getattr(location, "city", "") or "",
                "addressRegion": getattr(location, "state", "") or "",
                "postalCode": getattr(location, "zip_code", "") or "",
                "addressCountry": "US",
            },
        }
        if location.phone:
            schema["telephone"] = location.phone
        if location.website_url:
            schema["url"] = location.website_url
        return json.dumps(schema, indent=2)

    async def publish_to_website(
        self,
        location_id: UUID,
        content_type: str,
        content: dict,
        draft_id: UUID | None = None,
    ) -> dict[str, Any]:
        from app.integrations.website import WebsiteClient
        from app.models.channel import Channel, ChannelType
        from app.models.location import Location
        from app.models.website_seo import WebsiteSEODraftStatus

        location = self.db.query(Location).filter(Location.id == location_id).first()
        if not location:
            return {"success": False, "error": "Location not found"}

        channel = (
            self.db.query(Channel)
            .filter(
                Channel.location_id == location_id,
                Channel.type == ChannelType.WEBSITE,
                Channel.is_active.is_(True),
            )
            .first()
        )
        if not channel:
            return {
                "success": False,
                "error": integration_unavailable(
                    "Website publishing",
                    "the Website channel is not connected",
                    "Open Integrations to connect the Website channel and try again",
                ),
            }

        credentials = channel.get_credentials()
        if not credentials:
            return {
                "success": False,
                "error": integration_unavailable(
                    "Website publishing",
                    "Website channel credentials are missing",
                    "Reconnect the Website channel in Integrations and try again",
                ),
            }

        draft = self.get_draft(draft_id=draft_id, location_id=location_id) if draft_id else None
        if draft and draft.archived_at is not None:
            return {"success": False, "error": "Draft has been archived"}
        if draft and draft.approval_status != "approved":
            return {"success": False, "error": "Draft must be approved before publishing"}

        try:
            client = WebsiteClient(credentials)
            if content_type == "blog":
                result = await client.publish_markdown(
                    title=content.get("title"),
                    content=content.get("content_markdown"),
                    slug=content.get("slug"),
                )
            else:
                result = await client.publish_markdown(
                    title=content.get("service_name") or content.get("title"),
                    content=content.get("content_html") or content.get("content_markdown"),
                    slug=content.get("slug"),
                )

            if draft:
                draft.status = WebsiteSEODraftStatus.PUBLISHED
                draft.published_url = result
                draft.provider_reference = result
                draft.published_at = utc_now_aware()
                draft.last_error = None

            self._update_channel_publish_state(
                location_id=location_id,
                success=True,
                published_url=result,
                provider_reference=result,
            )
            self.db.commit()
            return {
                "success": True,
                "published_url": result,
                "draft_id": str(draft.id) if draft else None,
            }
        except Exception as exc:
            error_message = str(exc)
            if draft:
                draft.status = WebsiteSEODraftStatus.FAILED
                draft.last_error = error_message
            self._update_channel_publish_state(
                location_id=location_id,
                success=False,
                error_message=error_message,
            )
            self.db.commit()
            await self._notify_publish_failure(
                location_id=location_id,
                account_id=location.account_id,
                content_type=content_type,
                draft_id=draft.id if draft else None,
                draft_title=(draft.title if draft else None),
                error_message=error_message,
                location_name=location.name,
            )
            logger.exception("Website publish failed for location %s", location_id)
            return {
                "success": False,
                "error": workflow_failed(
                    "Website publishing",
                    "Open Integrations to verify the Website channel and try again",
                ),
            }
