"""Content suggestion service for multiple-choice UX."""

import logging
from datetime import datetime, date
from typing import Any

logger = logging.getLogger(__name__)


class ContentSuggestionService:
    """
    Service for generating content topic suggestions.
    
    Provides multiple-choice options instead of free-form prompts.
    사장님들은 프롬프트를 입력할 줄 모른다. UX는 무조건 객관식이어야 한다.
    """

    # Weather-based suggestions
    WEATHER_SUGGESTIONS = {
        "rainy": {
            "emoji": "🌧️",
            "title_ko": "비 오는 날 따뜻한 스페셜 메뉴",
            "title_en": "Rainy Day Warm Specials",
            "description": "Perfect for cozy indoor experiences",
            "themes": ["comfort-food", "warm-drinks", "indoor-relaxation"],
        },
        "hot": {
            "emoji": "☀️",
            "title_ko": "무더운 날 시원한 메뉴",
            "title_en": "Beat the Heat Specials",
            "description": "Cool down with refreshing options",
            "themes": ["cold-drinks", "summer-specials", "cooling-services"],
        },
        "cold": {
            "emoji": "❄️",
            "title_ko": "추운 날 따뜻하게",
            "title_en": "Winter Warmers",
            "description": "Warm up with our cozy offerings",
            "themes": ["hot-drinks", "winter-specials", "warming-services"],
        },
        "snowy": {
            "emoji": "🌨️",
            "title_ko": "눈 오는 날 특별 혜택",
            "title_en": "Snow Day Specials",
            "description": "Special treats for snowy days",
            "themes": ["snow-day-deals", "cozy-atmosphere"],
        },
    }

    # Seasonal/Event suggestions
    SEASONAL_SUGGESTIONS = {
        "new_year": {
            "emoji": "🎆",
            "title_ko": "새해 맞이 특별 프로모션",
            "title_en": "New Year Special Promotion",
            "months": [1],
            "days": list(range(1, 15)),
        },
        "valentines": {
            "emoji": "💝",
            "title_ko": "발렌타인 데이 스페셜",
            "title_en": "Valentine's Day Special",
            "months": [2],
            "days": list(range(7, 15)),
        },
        "spring": {
            "emoji": "🌸",
            "title_ko": "봄맞이 신메뉴 출시",
            "title_en": "Spring New Menu Launch",
            "months": [3, 4],
        },
        "easter": {
            "emoji": "🐰",
            "title_ko": "이스터 스페셜",
            "title_en": "Easter Special",
            "months": [3, 4],
        },
        "mothers_day": {
            "emoji": "💐",
            "title_ko": "어머니의 날 감사 이벤트",
            "title_en": "Mother's Day Appreciation",
            "months": [5],
            "days": list(range(8, 15)),
        },
        "summer": {
            "emoji": "🏖️",
            "title_ko": "여름 시즌 특가",
            "title_en": "Summer Season Special",
            "months": [6, 7, 8],
        },
        "independence_day": {
            "emoji": "🇺🇸",
            "title_ko": "독립기념일 스페셜",
            "title_en": "4th of July Special",
            "months": [7],
            "days": list(range(1, 8)),
        },
        "back_to_school": {
            "emoji": "📚",
            "title_ko": "개학 시즌 프로모션",
            "title_en": "Back to School Promotion",
            "months": [8, 9],
        },
        "halloween": {
            "emoji": "🎃",
            "title_ko": "할로윈 맞이 10% 할인",
            "title_en": "Halloween 10% Off",
            "months": [10],
            "days": list(range(20, 32)),
        },
        "thanksgiving": {
            "emoji": "🦃",
            "title_ko": "추수감사절 스페셜",
            "title_en": "Thanksgiving Special",
            "months": [11],
            "days": list(range(20, 30)),
        },
        "black_friday": {
            "emoji": "🏷️",
            "title_ko": "블랙프라이데이 대할인",
            "title_en": "Black Friday Big Sale",
            "months": [11],
            "days": list(range(24, 30)),
        },
        "christmas": {
            "emoji": "🎄",
            "title_ko": "크리스마스 시즌 이벤트",
            "title_en": "Christmas Season Event",
            "months": [12],
            "days": list(range(15, 26)),
        },
        "year_end": {
            "emoji": "🎊",
            "title_ko": "연말 감사 이벤트",
            "title_en": "Year-End Appreciation",
            "months": [12],
            "days": list(range(26, 32)),
        },
    }

    # Day-of-week suggestions
    WEEKDAY_SUGGESTIONS = {
        0: {  # Monday
            "emoji": "😴",
            "title_ko": "월요병 극복 스페셜",
            "title_en": "Monday Blues Buster",
            "description": "Start the week right",
        },
        1: {  # Tuesday
            "emoji": "🌮",
            "title_ko": "화요일 특가",
            "title_en": "Tuesday Special",
            "description": "Midweek treat",
        },
        2: {  # Wednesday
            "emoji": "🐪",
            "title_ko": "수요일 힘내세요",
            "title_en": "Hump Day Special",
            "description": "Halfway through the week",
        },
        3: {  # Thursday
            "emoji": "🍻",
            "title_ko": "불금 전야제",
            "title_en": "Almost Friday Special",
            "description": "Pre-weekend celebration",
        },
        4: {  # Friday
            "emoji": "🎉",
            "title_ko": "불금 스페셜",
            "title_en": "TGIF Special",
            "description": "Weekend kickoff",
        },
        5: {  # Saturday
            "emoji": "👨‍👩‍👧‍👦",
            "title_ko": "주말 가족 세트 홍보",
            "title_en": "Weekend Family Special",
            "description": "Family time deals",
        },
        6: {  # Sunday
            "emoji": "☕",
            "title_ko": "일요일 브런치 스페셜",
            "title_en": "Sunday Brunch Special",
            "description": "Relaxing Sunday",
        },
    }

    # Business category specific suggestions
    CATEGORY_SUGGESTIONS = {
        "restaurant": [
            {"emoji": "🆕", "title_ko": "신메뉴 출시 알림", "title_en": "New Menu Launch"},
            {"emoji": "👨‍🍳", "title_ko": "셰프 추천 메뉴", "title_en": "Chef's Recommendation"},
            {"emoji": "🥗", "title_ko": "건강한 메뉴 소개", "title_en": "Healthy Options"},
            {"emoji": "🍝", "title_ko": "인기 메뉴 베스트 3", "title_en": "Top 3 Popular Dishes"},
        ],
        "cafe": [
            {"emoji": "☕", "title_ko": "시즌 음료 출시", "title_en": "Seasonal Drink Launch"},
            {"emoji": "🍰", "title_ko": "디저트 페어링 추천", "title_en": "Dessert Pairing"},
            {"emoji": "📖", "title_ko": "카페에서 보내는 여유", "title_en": "Cafe Relaxation"},
        ],
        "spa": [
            {"emoji": "💆", "title_ko": "이달의 추천 트리트먼트", "title_en": "Treatment of the Month"},
            {"emoji": "🧖", "title_ko": "스트레스 해소 패키지", "title_en": "Stress Relief Package"},
            {"emoji": "💅", "title_ko": "뷰티 케어 스페셜", "title_en": "Beauty Care Special"},
        ],
        "beauty_salon": [
            {"emoji": "💇", "title_ko": "이달의 헤어 트렌드", "title_en": "Hair Trend of the Month"},
            {"emoji": "💄", "title_ko": "메이크업 스페셜", "title_en": "Makeup Special"},
            {"emoji": "✨", "title_ko": "변신 프로젝트", "title_en": "Transformation Project"},
        ],
        "dentist": [
            {"emoji": "🦷", "title_ko": "정기 검진 안내", "title_en": "Regular Checkup Reminder"},
            {"emoji": "😁", "title_ko": "화이트닝 스페셜", "title_en": "Whitening Special"},
            {"emoji": "👨‍⚕️", "title_ko": "전문의 상담 안내", "title_en": "Specialist Consultation"},
        ],
        "gym": [
            {"emoji": "💪", "title_ko": "이달의 챌린지", "title_en": "Monthly Challenge"},
            {"emoji": "🏋️", "title_ko": "PT 프로그램 소개", "title_en": "PT Program Introduction"},
            {"emoji": "🧘", "title_ko": "새 클래스 오픈", "title_en": "New Class Opening"},
        ],
        "car_repair": [
            {"emoji": "🚗", "title_ko": "시즌 점검 캠페인", "title_en": "Seasonal Checkup Campaign"},
            {"emoji": "🔧", "title_ko": "정비 할인 이벤트", "title_en": "Maintenance Discount"},
            {"emoji": "🛞", "title_ko": "타이어 교체 시즌", "title_en": "Tire Change Season"},
        ],
    }

    # Universal suggestions (for any business)
    UNIVERSAL_SUGGESTIONS = [
        {"emoji": "⭐", "title_ko": "고객 리뷰 감사 포스트", "title_en": "Customer Review Thank You"},
        {"emoji": "👋", "title_ko": "팀 소개", "title_en": "Meet Our Team"},
        {"emoji": "🎂", "title_ko": "오픈 기념일 이벤트", "title_en": "Anniversary Celebration"},
        {"emoji": "📢", "title_ko": "영업시간 변경 안내", "title_en": "Hours Update"},
        {"emoji": "🏆", "title_ko": "수상/인증 소식", "title_en": "Award/Certification News"},
        {"emoji": "💝", "title_ko": "단골 고객 감사 이벤트", "title_en": "Loyal Customer Appreciation"},
    ]

    def get_suggestions(
        self,
        category: str | None = None,
        weather: str | None = None,
        target_date: date | None = None,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        """
        Get content suggestions based on context.
        
        Returns a list of multiple-choice options for the user.
        """
        suggestions = []
        today = target_date or date.today()
        weekday = today.weekday()
        month = today.month
        day = today.day

        # 1. Weather-based suggestion (if provided)
        if weather and weather in self.WEATHER_SUGGESTIONS:
            ws = self.WEATHER_SUGGESTIONS[weather]
            suggestions.append({
                "id": f"weather_{weather}",
                "type": "weather",
                "emoji": ws["emoji"],
                "title_ko": ws["title_ko"],
                "title_en": ws["title_en"],
                "priority": 1,
            })

        # 2. Seasonal/Event suggestions
        for event_id, event in self.SEASONAL_SUGGESTIONS.items():
            if month in event.get("months", []):
                if "days" not in event or day in event.get("days", []):
                    suggestions.append({
                        "id": f"seasonal_{event_id}",
                        "type": "seasonal",
                        "emoji": event["emoji"],
                        "title_ko": event["title_ko"],
                        "title_en": event["title_en"],
                        "priority": 2,
                    })

        # 3. Weekday suggestion
        if weekday in self.WEEKDAY_SUGGESTIONS:
            ws = self.WEEKDAY_SUGGESTIONS[weekday]
            suggestions.append({
                "id": f"weekday_{weekday}",
                "type": "weekday",
                "emoji": ws["emoji"],
                "title_ko": ws["title_ko"],
                "title_en": ws["title_en"],
                "priority": 3,
            })

        # 4. Category-specific suggestions
        if category and category in self.CATEGORY_SUGGESTIONS:
            for i, cs in enumerate(self.CATEGORY_SUGGESTIONS[category][:2]):
                suggestions.append({
                    "id": f"category_{category}_{i}",
                    "type": "category",
                    "emoji": cs["emoji"],
                    "title_ko": cs["title_ko"],
                    "title_en": cs["title_en"],
                    "priority": 4,
                })

        # 5. Universal suggestions (fill remaining slots)
        for i, us in enumerate(self.UNIVERSAL_SUGGESTIONS):
            if len(suggestions) >= limit:
                break
            suggestions.append({
                "id": f"universal_{i}",
                "type": "universal",
                "emoji": us["emoji"],
                "title_ko": us["title_ko"],
                "title_en": us["title_en"],
                "priority": 5,
            })

        # Sort by priority and limit
        suggestions.sort(key=lambda x: x["priority"])
        return suggestions[:limit]

    def get_suggestion_by_id(self, suggestion_id: str) -> dict[str, Any] | None:
        """Get a specific suggestion by its ID."""
        all_suggestions = self.get_suggestions(limit=100)
        for s in all_suggestions:
            if s["id"] == suggestion_id:
                return s
        return None

    def build_prompt_from_suggestion(
        self,
        suggestion: dict[str, Any],
        business_name: str,
        category: str | None = None,
        language: str = "en",
    ) -> str:
        """Build a content generation prompt from a suggestion."""
        title = suggestion.get("title_en" if language == "en" else "title_ko", "")
        
        prompt = f"""Create a Google Business Profile post for {business_name}.

Topic: {title}
Business Type: {category or 'local business'}
Tone: Friendly, professional, engaging
Length: 2-3 short paragraphs

Include:
- A catchy opening line
- Key details about the offer/topic
- A clear call-to-action

Do NOT include:
- Hashtags (not supported on GBP)
- External links in the body
- Overly promotional language
"""
        return prompt
