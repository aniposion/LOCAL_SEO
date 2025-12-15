"""SEO scoring and recommendation service."""

from datetime import date, datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.analytics import Analytics
from app.models.post import Post, PostStatus
from app.models.seo_score import SEOScore
from app.schemas.seo import SEORecommendation


class SEOService:
    """Service for SEO scoring and recommendations."""

    def __init__(self, db: Session) -> None:
        self.db = db

    async def calculate_score(
        self,
        location_id: UUID,
        from_date: date,
        to_date: date,
    ) -> SEOScore:
        """Calculate SEO score based on analytics data."""
        # Fetch analytics for the period
        analytics = (
            self.db.query(Analytics)
            .filter(
                Analytics.location_id == location_id,
                Analytics.date >= from_date,
                Analytics.date <= to_date,
            )
            .all()
        )

        # Calculate weighted scores for each platform
        factors = {
            "gbp_score": 0,
            "instagram_score": 0,
            "website_score": 0,
            "posting_consistency": 0,
        }

        gbp_metrics = {"impressions": 0, "clicks": 0, "calls": 0, "directions": 0}
        ig_metrics = {"reach": 0, "engagement": 0}
        web_metrics = {"views": 0, "visitors": 0}

        for a in analytics:
            if a.platform == "GBP":
                gbp_metrics["impressions"] += a.impressions or 0
                gbp_metrics["clicks"] += a.clicks or 0
                gbp_metrics["calls"] += a.calls or 0
                gbp_metrics["directions"] += a.direction_requests or 0
            elif a.platform == "INSTAGRAM":
                ig_metrics["reach"] += a.reach or 0
                ig_metrics["engagement"] += (a.likes or 0) + (a.comments or 0) + (a.shares or 0)
            elif a.platform == "WEBSITE":
                web_metrics["views"] += a.page_views or 0
                web_metrics["visitors"] += a.unique_visitors or 0

        # Calculate platform scores (0-100)
        # GBP: weighted by conversions (calls + directions)
        if gbp_metrics["impressions"] > 0:
            gbp_ctr = gbp_metrics["clicks"] / gbp_metrics["impressions"]
            gbp_conversion = (gbp_metrics["calls"] + gbp_metrics["directions"]) / max(gbp_metrics["clicks"], 1)
            factors["gbp_score"] = min(100, (gbp_ctr * 50 + gbp_conversion * 50) * 100)

        # Instagram: engagement rate
        if ig_metrics["reach"] > 0:
            ig_engagement_rate = ig_metrics["engagement"] / ig_metrics["reach"]
            factors["instagram_score"] = min(100, ig_engagement_rate * 1000)

        # Website: visitor engagement
        if web_metrics["views"] > 0:
            factors["website_score"] = min(100, (web_metrics["visitors"] / web_metrics["views"]) * 100)

        # Posting consistency
        posts_count = (
            self.db.query(Post)
            .filter(
                Post.location_id == location_id,
                Post.status == PostStatus.POSTED,
                Post.posted_at >= datetime.combine(from_date, datetime.min.time()).replace(tzinfo=timezone.utc),
                Post.posted_at <= datetime.combine(to_date, datetime.max.time()).replace(tzinfo=timezone.utc),
            )
            .count()
        )
        days = (to_date - from_date).days + 1
        expected_posts = days / 2  # Expect posting every 2 days
        factors["posting_consistency"] = min(100, (posts_count / max(expected_posts, 1)) * 100)

        # Weighted final score
        weights = {"gbp_score": 0.35, "instagram_score": 0.30, "website_score": 0.20, "posting_consistency": 0.15}
        final_score = sum(factors[k] * weights[k] for k in weights)

        # Generate rationale
        rationale = self._generate_rationale(factors, final_score)

        # Save score
        seo_score = SEOScore(
            location_id=location_id,
            date=to_date,
            score=round(final_score, 2),
            factors=factors,
            rationale=rationale,
        )
        self.db.add(seo_score)
        self.db.commit()
        self.db.refresh(seo_score)

        return seo_score

    async def get_recommendation(self, location_id: UUID) -> SEORecommendation:
        """Generate content recommendations based on past performance."""
        # Get recent successful posts
        recent_posts = (
            self.db.query(Post)
            .filter(
                Post.location_id == location_id,
                Post.status == PostStatus.POSTED,
            )
            .order_by(Post.posted_at.desc())
            .limit(20)
            .all()
        )

        # Analyze hashtag performance
        hashtag_counts: dict[str, int] = {}
        for post in recent_posts:
            if post.hashtags:
                for tag in post.hashtags:
                    hashtag_counts[tag] = hashtag_counts.get(tag, 0) + 1

        top_hashtags = sorted(hashtag_counts.items(), key=lambda x: x[1], reverse=True)[:10]

        # Analyze topics from generation params
        topic_counts: dict[str, int] = {}
        for post in recent_posts:
            if post.generation_params and "theme" in post.generation_params:
                theme = post.generation_params["theme"]
                topic_counts[theme] = topic_counts.get(theme, 0) + 1

        top_topics = sorted(topic_counts.items(), key=lambda x: x[1], reverse=True)[:5]

        # Determine best posting time (simplified: morning on weekdays)
        next_best_time = datetime.now(timezone.utc).replace(hour=10, minute=0, second=0, microsecond=0)
        if next_best_time < datetime.now(timezone.utc):
            next_best_time += timedelta(days=1)

        # Generate rationale
        rationale = "Based on your recent posting history: "
        if top_topics:
            rationale += f"Topics like '{top_topics[0][0]}' have performed well. "
        if top_hashtags:
            rationale += f"Hashtags including #{top_hashtags[0][0]} show good engagement. "
        rationale += "Consider posting during morning hours for better reach."

        return SEORecommendation(
            location_id=location_id,
            next_best_time=next_best_time,
            topics=[t[0] for t in top_topics] if top_topics else ["seasonal-special", "service-highlight"],
            hashtags=[h[0] for h in top_hashtags] if top_hashtags else ["local", "smallbusiness"],
            rationale=rationale,
            confidence=0.7 if recent_posts else 0.3,
        )

    def _generate_rationale(self, factors: dict, score: float) -> str:
        """Generate human-readable rationale for the score."""
        parts = []

        if factors["gbp_score"] < 30:
            parts.append("GBP performance needs improvement - focus on increasing visibility and conversions")
        elif factors["gbp_score"] > 70:
            parts.append("Strong GBP performance with good conversion rates")

        if factors["instagram_score"] < 30:
            parts.append("Instagram engagement is low - try more engaging content and relevant hashtags")
        elif factors["instagram_score"] > 70:
            parts.append("Excellent Instagram engagement")

        if factors["posting_consistency"] < 50:
            parts.append("Posting frequency is below target - aim for more consistent content")

        if score >= 70:
            return "Overall strong SEO performance. " + " ".join(parts)
        elif score >= 40:
            return "Moderate SEO performance with room for improvement. " + " ".join(parts)
        else:
            return "SEO performance needs attention. " + " ".join(parts)
