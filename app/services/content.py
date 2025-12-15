"""Content generation service using LLM."""

import json
from typing import Any

from app.core.config import settings
from app.integrations.llm import LLMAdapter
from app.models.location import Location
from app.schemas.content import GeneratedContent, GBPContent, InstagramContent, WebContent


class ContentService:
    """Service for generating content using LLM."""

    def __init__(self) -> None:
        self.llm = LLMAdapter()
        self.model_name = settings.llm_model

    async def generate(
        self,
        location: Location,
        theme: str,
        services: list[str],
        tone: str = "expert yet friendly",
        language: str = "en",
        platform_targets: list[str] | None = None,
        audience: str | None = None,
        promo: str | None = None,
    ) -> GeneratedContent:
        """Generate content for all target platforms."""
        platform_targets = platform_targets or ["GBP", "INSTAGRAM", "WEBSITE"]

        prompt = self._build_prompt(
            location=location,
            theme=theme,
            services=services,
            tone=tone,
            language=language,
            platform_targets=platform_targets,
            audience=audience,
            promo=promo,
        )

        response = await self.llm.generate(prompt)
        return self._parse_response(response, platform_targets)

    def _build_prompt(
        self,
        location: Location,
        theme: str,
        services: list[str],
        tone: str,
        language: str,
        platform_targets: list[str],
        audience: str | None,
        promo: str | None,
    ) -> str:
        """Build the LLM prompt for content generation."""
        services_str = ", ".join(services) if services else "general services"
        audience_str = audience or "local customers"

        prompt = f"""[Role] You are a Local SEO content strategist for small businesses in {location.city or 'the local area'}, {location.state or ''}.

[Inputs]
- Business: {location.name}
- Address: {location.address or 'N/A'}
- Services: {services_str}
- Season/Promo: {theme}{f' - {promo}' if promo else ''}
- Language: {language}
- Tone: {tone}
- Audience: {audience_str}

[Outputs by platform]
Generate content ONLY for these platforms: {', '.join(platform_targets)}

"""
        if "GBP" in platform_targets:
            prompt += """- GBP: title (<=58 chars), body (300~700 chars), 1 CTA, 1 offer (optional), hashtags (<=6)
"""
        if "INSTAGRAM" in platform_targets:
            prompt += """- IG: caption (700~1500 chars), 15~25 hashtags (mix: geo + service + trending)
"""
        if "WEBSITE" in platform_targets:
            prompt += """- WEB: markdown blog with H2/H3 headings, bullets, meta_description, internal link anchor text suggestions
"""

        prompt += f"""- Image Prompt: photorealistic prompt with shooting details (lens, light, framing) for {theme}

[Constraints]
- Avoid claims requiring medical approval; use compliant wording.
- Include local keywords naturally (e.g., "{location.city or 'local'} {services[0] if services else 'service'}")
- Produce valid JSON only, no markdown code blocks:
{{
  "gbp": {{"title": "...", "body": "...", "cta": "...", "offer": "...", "hashtags": [...]}},
  "instagram": {{"caption": "...", "hashtags": [...]}},
  "web": {{"title": "...", "markdown": "...", "meta_description": "...", "internal_links": [...]}},
  "image_prompt": "..."
}}

Only include keys for the requested platforms. Respond with JSON only."""

        return prompt

    def _parse_response(
        self, response: str, platform_targets: list[str]
    ) -> GeneratedContent:
        """Parse LLM response into structured content."""
        try:
            # Clean response - remove markdown code blocks if present
            cleaned = response.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("```")[1]
                if cleaned.startswith("json"):
                    cleaned = cleaned[4:]
            cleaned = cleaned.strip()

            data = json.loads(cleaned)
        except json.JSONDecodeError:
            # Return empty content if parsing fails
            return GeneratedContent()

        result = GeneratedContent()

        if "GBP" in platform_targets and "gbp" in data:
            gbp_data = data["gbp"]
            result.gbp = GBPContent(
                title=gbp_data.get("title", "")[:58],
                body=gbp_data.get("body", ""),
                cta=gbp_data.get("cta"),
                offer=gbp_data.get("offer"),
                hashtags=gbp_data.get("hashtags", [])[:6],
            )

        if "INSTAGRAM" in platform_targets and "instagram" in data:
            ig_data = data["instagram"]
            result.instagram = InstagramContent(
                caption=ig_data.get("caption", ""),
                hashtags=ig_data.get("hashtags", [])[:25],
            )

        if "WEBSITE" in platform_targets and "web" in data:
            web_data = data["web"]
            result.web = WebContent(
                title=web_data.get("title", ""),
                markdown=web_data.get("markdown", ""),
                meta_description=web_data.get("meta_description"),
                internal_links=web_data.get("internal_links"),
            )

        result.image_prompt = data.get("image_prompt")

        return result
