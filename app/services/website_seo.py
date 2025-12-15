"""Website SEO Auto-Optimizer - Automated website SEO optimization."""

import logging
import re
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import settings

logger = logging.getLogger(__name__)


class WebsiteSEOService:
    """
    Service for automated website SEO optimization.
    
    Features:
    - Meta tags 자동 생성
    - 서비스 페이지 자동 최적화
    - 블로그 자동 생성 (AI)
    - 로컬 키워드 분석
    """

    # Local SEO keyword patterns by business category
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

    async def generate_meta_tags(
        self,
        location_id: UUID,
        page_type: str = "home",  # home, service, about, contact
        service_name: str | None = None,
    ) -> dict[str, str]:
        """
        Generate optimized meta tags for a page.
        
        Returns:
            {
                "title": "...",
                "description": "...",
                "keywords": "...",
                "og_title": "...",
                "og_description": "...",
                "schema_json": "..."
            }
        """
        from app.models.location import Location

        location = self.db.query(Location).filter(Location.id == location_id).first()
        if not location:
            return {}

        business_name = location.name
        city = getattr(location, 'city', '') or ''
        category = getattr(location, 'category', 'business') or 'business'

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

        # Generate keywords
        keywords = await self.analyze_local_keywords(location_id)
        keywords_str = ", ".join(keywords[:10])

        # Generate Schema.org JSON-LD
        schema_json = self._generate_schema_json(location, page_type)

        return {
            "title": title[:60],  # Google title limit
            "description": description[:160],  # Meta description limit
            "keywords": keywords_str,
            "og_title": title[:60],
            "og_description": description[:160],
            "og_type": "website",
            "schema_json": schema_json,
        }

    async def analyze_local_keywords(
        self,
        location_id: UUID,
        limit: int = 20,
    ) -> list[str]:
        """
        Analyze and generate local SEO keywords for a business.
        """
        from app.models.location import Location

        location = self.db.query(Location).filter(Location.id == location_id).first()
        if not location:
            return []

        category = getattr(location, 'category', 'default') or 'default'
        city = getattr(location, 'city', '') or ''
        neighborhood = getattr(location, 'neighborhood', '') or city
        services = getattr(location, 'services', []) or []

        # Get keyword templates
        templates = self.LOCAL_KEYWORDS.get(category, self.LOCAL_KEYWORDS['default'])

        keywords = []

        # Generate keywords from templates
        for template in templates:
            keyword = template.format(
                business_type=category,
                cuisine=category if category == 'restaurant' else '',
                city=city,
                neighborhood=neighborhood,
            )
            keyword = keyword.strip()
            if keyword and keyword not in keywords:
                keywords.append(keyword)

        # Add service-specific keywords
        for service in services[:5]:
            keywords.append(f"{service} {city}")
            keywords.append(f"{service} near me")

        # Add business name variations
        keywords.append(location.name)
        keywords.append(f"{location.name} {city}")

        return keywords[:limit]

    async def generate_service_page(
        self,
        location_id: UUID,
        service_name: str,
        service_description: str | None = None,
    ) -> dict[str, Any]:
        """
        Generate an optimized service page content.
        """
        from app.models.location import Location
        from app.integrations.llm import LLMClient

        location = self.db.query(Location).filter(Location.id == location_id).first()
        if not location:
            return {"error": "Location not found"}

        city = getattr(location, 'city', '') or ''

        # Generate meta tags
        meta_tags = await self.generate_meta_tags(
            location_id=location_id,
            page_type="service",
            service_name=service_name,
        )

        # Generate content using AI
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

        content = await llm.generate(prompt)

        return {
            "service_name": service_name,
            "meta_tags": meta_tags,
            "content_html": content,
            "keywords": await self.analyze_local_keywords(location_id),
        }

    async def generate_blog_post(
        self,
        location_id: UUID,
        topic: str,
        keywords: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        Generate an SEO-optimized blog post.
        """
        from app.models.location import Location
        from app.integrations.llm import LLMClient

        location = self.db.query(Location).filter(Location.id == location_id).first()
        if not location:
            return {"error": "Location not found"}

        city = getattr(location, 'city', '') or ''
        category = getattr(location, 'category', 'business') or 'business'

        # Get keywords if not provided
        if not keywords:
            keywords = await self.analyze_local_keywords(location_id)

        # Generate blog post using AI
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

        content = await llm.generate(prompt)

        # Parse the response
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

        # Generate slug
        slug = re.sub(r'[^a-z0-9]+', '-', topic.lower()).strip('-')

        return {
            "title": title or topic,
            "slug": slug,
            "meta_description": meta_description,
            "content_markdown": body,
            "keywords": keywords[:10],
            "word_count": len(body.split()),
        }

    async def optimize_existing_page(
        self,
        location_id: UUID,
        page_url: str,
        current_content: str,
    ) -> dict[str, Any]:
        """
        Analyze and suggest optimizations for an existing page.
        """
        from app.integrations.llm import LLMClient

        # Analyze current content
        word_count = len(current_content.split())
        has_h1 = "<h1" in current_content.lower() or "# " in current_content
        has_h2 = "<h2" in current_content.lower() or "## " in current_content

        # Get target keywords
        keywords = await self.analyze_local_keywords(location_id)

        # Check keyword presence
        keyword_presence = {}
        content_lower = current_content.lower()
        for kw in keywords[:10]:
            count = content_lower.count(kw.lower())
            keyword_presence[kw] = count

        # Generate recommendations
        recommendations = []

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

        # Check for missing keywords
        missing_keywords = [kw for kw, count in keyword_presence.items() if count == 0]
        if missing_keywords:
            recommendations.append({
                "type": "keywords",
                "priority": "medium",
                "message": f"Missing keywords: {', '.join(missing_keywords[:5])}",
            })

        # Generate new meta tags
        meta_tags = await self.generate_meta_tags(location_id)

        return {
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

    def _generate_schema_json(self, location, page_type: str) -> str:
        """Generate Schema.org JSON-LD for local business."""
        import json

        category = getattr(location, 'category', 'LocalBusiness') or 'LocalBusiness'

        # Map category to Schema.org type
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
                "addressLocality": getattr(location, 'city', '') or '',
                "addressRegion": getattr(location, 'state', '') or '',
                "postalCode": getattr(location, 'zip_code', '') or '',
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
        content_type: str,  # "blog", "service_page"
        content: dict,
    ) -> dict[str, Any]:
        """
        Publish content to the website (GitHub/WordPress).
        """
        from app.models.location import Location
        from app.models.channel import Channel, ChannelType
        from app.integrations.website import WebsiteClient

        location = self.db.query(Location).filter(Location.id == location_id).first()
        if not location:
            return {"success": False, "error": "Location not found"}

        # Get website channel
        channel = self.db.query(Channel).filter(
            Channel.location_id == location_id,
            Channel.channel_type == ChannelType.WEBSITE,
            Channel.is_active == True,
        ).first()

        if not channel:
            return {"success": False, "error": "Website channel not configured"}

        # Decrypt credentials
        from app.core.encryption import decrypt_credentials
        credentials = decrypt_credentials(channel.credentials_encrypted)

        # Publish
        client = WebsiteClient(credentials)

        if content_type == "blog":
            result = await client.publish_markdown(
                title=content.get("title"),
                content=content.get("content_markdown"),
                slug=content.get("slug"),
            )
        else:
            result = await client.publish_markdown(
                title=content.get("service_name"),
                content=content.get("content_html"),
            )

        return {
            "success": True,
            "published_url": result,
        }
