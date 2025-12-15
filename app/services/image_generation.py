"""Image generation service using Google AI Studio (Nano Banana Pro / Gemini 3)."""

import base64
import logging
import mimetypes
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import settings

logger = logging.getLogger(__name__)


class ImageGenerationService:
    """Service for generating images using Google AI Studio Gemini 3 Pro Image."""

    # Model name for image generation
    MODEL_NAME = "gemini-3-pro-image-preview"

    def __init__(self, db: Session | None = None) -> None:
        self.db = db
        self.api_key = settings.gemini_api_key
        self._client = None

    def _get_client(self):
        """Get or create Google GenAI client."""
        if self._client is None:
            from google import genai
            self._client = genai.Client(api_key=self.api_key)
        return self._client

    async def generate_image(
        self,
        prompt: str,
        image_size: str = "1K",
        style: str | None = None,
    ) -> dict[str, Any]:
        """
        Generate image using Google AI Studio Gemini 3 Pro Image.

        Args:
            prompt: Image generation prompt
            image_size: Image size (1K, 2K, etc.)
            style: Style preset (photorealistic, artistic, etc.)

        Returns:
            dict with generated image data
        """
        if not self.api_key:
            raise ValueError("Gemini API key not configured")

        from google.genai import types

        # Build enhanced prompt
        enhanced_prompt = self._enhance_prompt(prompt, style)

        client = self._get_client()

        contents = [
            types.Content(
                role="user",
                parts=[
                    types.Part.from_text(text=enhanced_prompt),
                ],
            ),
        ]

        generate_content_config = types.GenerateContentConfig(
            response_modalities=["IMAGE", "TEXT"],
            image_config=types.ImageConfig(
                image_size=image_size,
            ),
        )

        images = []
        text_response = None

        try:
            # Use streaming to handle response
            for chunk in client.models.generate_content_stream(
                model=self.MODEL_NAME,
                contents=contents,
                config=generate_content_config,
            ):
                if (
                    chunk.candidates is None
                    or chunk.candidates[0].content is None
                    or chunk.candidates[0].content.parts is None
                ):
                    continue

                part = chunk.candidates[0].content.parts[0]

                if part.inline_data and part.inline_data.data:
                    # Image data received
                    inline_data = part.inline_data
                    images.append({
                        "data": inline_data.data,
                        "mime_type": inline_data.mime_type,
                    })
                    logger.info(f"Image generated with mime_type: {inline_data.mime_type}")
                elif hasattr(chunk, 'text') and chunk.text:
                    # Text response (description, etc.)
                    text_response = chunk.text

            return {
                "images": images,
                "count": len(images),
                "text_response": text_response,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }

        except Exception as e:
            logger.error(f"Image generation error: {e}")
            raise ValueError(f"Image generation failed: {e}")

    def _enhance_prompt(self, prompt: str, style: str | None = None) -> str:
        """Enhance prompt for better image generation."""
        # 기본 품질 향상 키워드
        quality_keywords = [
            "high quality",
            "professional photography",
            "sharp focus",
            "well-lit",
        ]

        # 스타일별 키워드
        style_keywords = {
            "photorealistic": ["photorealistic", "realistic", "natural lighting", "DSLR quality"],
            "artistic": ["artistic", "creative", "stylized", "vibrant colors"],
            "commercial": ["commercial photography", "product shot", "clean background", "studio lighting"],
            "social_media": ["instagram worthy", "eye-catching", "vibrant", "engaging"],
            "local_business": ["welcoming", "professional", "trustworthy", "local business"],
        }

        enhanced = prompt

        # 스타일 키워드 추가
        if style and style in style_keywords:
            style_additions = ", ".join(style_keywords[style])
            enhanced = f"{enhanced}, {style_additions}"

        # 품질 키워드 추가 (이미 포함되어 있지 않은 경우)
        for keyword in quality_keywords:
            if keyword.lower() not in enhanced.lower():
                enhanced = f"{enhanced}, {keyword}"

        return enhanced

    async def generate_and_upload(
        self,
        prompt: str,
        upload_to_s3: bool = True,
        image_size: str = "1K",
        style: str | None = None,
    ) -> str | None:
        """Generate image and optionally upload to S3."""
        try:
            result = await self.generate_image(
                prompt=prompt,
                image_size=image_size,
                style=style,
            )

            if not result["images"]:
                logger.warning("No images generated")
                return None

            image_data = result["images"][0]
            image_bytes = image_data["data"]
            mime_type = image_data.get("mime_type", "image/png")

            if upload_to_s3:
                # S3에 업로드
                url = await self._upload_to_s3(image_bytes, mime_type)
                return url
            else:
                # Base64 데이터 URL 반환
                b64_data = base64.b64encode(image_bytes).decode('utf-8')
                return f"data:{mime_type};base64,{b64_data}"

        except Exception as e:
            logger.error(f"Failed to generate and upload image: {e}")
            return None

    async def generate_and_save_local(
        self,
        prompt: str,
        output_path: str,
        image_size: str = "1K",
        style: str | None = None,
    ) -> str | None:
        """Generate image and save to local file."""
        try:
            result = await self.generate_image(
                prompt=prompt,
                image_size=image_size,
                style=style,
            )

            if not result["images"]:
                logger.warning("No images generated")
                return None

            image_data = result["images"][0]
            image_bytes = image_data["data"]
            mime_type = image_data.get("mime_type", "image/png")

            # Determine file extension
            file_extension = mimetypes.guess_extension(mime_type) or ".png"
            if not output_path.endswith(file_extension):
                output_path = f"{output_path}{file_extension}"

            # Save to file
            with open(output_path, "wb") as f:
                f.write(image_bytes)

            logger.info(f"Image saved to: {output_path}")
            return output_path

        except Exception as e:
            logger.error(f"Failed to generate and save image: {e}")
            return None

    async def _upload_to_s3(self, image_bytes: bytes, mime_type: str) -> str:
        """Upload image to S3 and return URL."""
        import uuid

        import boto3
        from botocore.exceptions import ClientError

        if not settings.aws_access_key_id or not settings.aws_secret_access_key:
            raise ValueError("AWS credentials not configured")

        s3_client = boto3.client(
            "s3",
            region_name=settings.aws_region,
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
        )

        # 파일 확장자 결정
        ext = mimetypes.guess_extension(mime_type) or ".png"
        ext = ext.lstrip(".")
        filename = f"generated-images/{uuid.uuid4()}.{ext}"

        try:
            s3_client.put_object(
                Bucket=settings.s3_bucket,
                Key=filename,
                Body=image_bytes,
                ContentType=mime_type,
                ACL="public-read",
            )

            url = f"https://{settings.s3_bucket}.s3.{settings.aws_region}.amazonaws.com/{filename}"
            logger.info(f"Image uploaded to S3: {url}")
            return url

        except ClientError as e:
            logger.error(f"S3 upload failed: {e}")
            raise


class ImagePromptBuilder:
    """Helper class for building effective image prompts."""

    @staticmethod
    def build_local_business_prompt(
        business_type: str,
        service: str,
        location: str | None = None,
        season: str | None = None,
        mood: str = "welcoming",
    ) -> str:
        """Build prompt for local business imagery."""
        prompt_parts = [
            f"Professional photograph of a {business_type}",
            f"showcasing {service}",
        ]

        if location:
            prompt_parts.append(f"in {location}")

        if season:
            season_moods = {
                "spring": "bright spring day, cherry blossoms, fresh atmosphere",
                "summer": "sunny summer day, vibrant colors, energetic",
                "fall": "autumn colors, warm golden light, cozy",
                "winter": "winter atmosphere, warm interior lighting, inviting",
            }
            prompt_parts.append(season_moods.get(season.lower(), ""))

        mood_descriptions = {
            "welcoming": "warm and inviting atmosphere, friendly environment",
            "professional": "clean and professional setting, trustworthy",
            "modern": "modern and sleek design, contemporary",
            "cozy": "cozy and comfortable, homey feel",
            "luxurious": "upscale and elegant, premium quality",
        }
        prompt_parts.append(mood_descriptions.get(mood, mood_descriptions["welcoming"]))

        # 기술적 세부사항
        prompt_parts.extend([
            "shot with Canon EOS R5",
            "35mm lens",
            "natural lighting",
            "shallow depth of field",
            "high resolution",
        ])

        return ", ".join(filter(None, prompt_parts))

    @staticmethod
    def build_product_prompt(
        product: str,
        style: str = "commercial",
        background: str = "clean white",
    ) -> str:
        """Build prompt for product photography."""
        return f"""Professional {style} product photography of {product}, 
        {background} background, studio lighting, 
        sharp focus, high detail, commercial quality, 
        shot with macro lens, soft shadows, 
        professional product shot for e-commerce"""

    @staticmethod
    def build_social_media_prompt(
        subject: str,
        platform: str = "instagram",
        style: str = "engaging",
    ) -> str:
        """Build prompt for social media content."""
        platform_styles = {
            "instagram": "instagram-worthy, vibrant colors, eye-catching composition",
            "facebook": "friendly and approachable, community feel",
            "gbp": "professional business image, trustworthy, local business",
        }

        platform_style = platform_styles.get(platform.lower(), platform_styles["instagram"])

        return f"""{subject}, {platform_style}, 
        {style} visual style, high engagement potential, 
        perfect for social media, trending aesthetic, 
        professional quality, well-composed"""
