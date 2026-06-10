"""Content suggestion service for multiple-choice UX."""

from datetime import date
from typing import Any


def _topic(emoji: str, title: str, **extra: Any) -> dict[str, Any]:
    """Build a suggestion row with a safe localized-title fallback."""
    return {
        "emoji": emoji,
        "title_en": title,
        "title_ko": title,
        **extra,
    }


class ContentSuggestionService:
    """Generate content topic suggestions from simple business context."""

    WEATHER_SUGGESTIONS = {
        "rainy": _topic("RAIN", "Rainy Day Warm Specials"),
        "hot": _topic("SUN", "Beat the Heat Specials"),
        "cold": _topic("COLD", "Winter Warmers"),
        "snowy": _topic("SNOW", "Snow Day Specials"),
    }

    SEASONAL_SUGGESTIONS = {
        "new_year": _topic(
            "NY",
            "New Year Special Promotion",
            months=[1],
            days=list(range(1, 15)),
        ),
        "valentines": _topic(
            "LOVE",
            "Valentine's Day Special",
            months=[2],
            days=list(range(7, 15)),
        ),
        "spring": _topic("SPRING", "Spring New Menu Launch", months=[3, 4]),
        "summer": _topic("SUMMER", "Summer Season Special", months=[6, 7, 8]),
        "back_to_school": _topic("SCHOOL", "Back to School Promotion", months=[8, 9]),
        "halloween": _topic(
            "HALLOWEEN",
            "Halloween 10% Off",
            months=[10],
            days=list(range(20, 32)),
        ),
        "thanksgiving": _topic(
            "THANKS",
            "Thanksgiving Special",
            months=[11],
            days=list(range(20, 30)),
        ),
        "black_friday": _topic(
            "SALE",
            "Black Friday Big Sale",
            months=[11],
            days=list(range(24, 30)),
        ),
        "christmas": _topic(
            "XMAS",
            "Christmas Season Event",
            months=[12],
            days=list(range(15, 26)),
        ),
        "year_end": _topic(
            "YEAR",
            "Year-End Appreciation",
            months=[12],
            days=list(range(26, 32)),
        ),
    }

    WEEKDAY_SUGGESTIONS = {
        0: _topic("MON", "Monday Kickoff Special"),
        1: _topic("TUE", "Tuesday Special"),
        2: _topic("WED", "Midweek Special"),
        3: _topic("THU", "Almost Friday Special"),
        4: _topic("FRI", "Friday Special"),
        5: _topic("SAT", "Weekend Family Special"),
        6: _topic("SUN", "Sunday Brunch Special"),
    }

    CATEGORY_SUGGESTIONS = {
        "restaurant": [
            _topic("MENU", "New Menu Launch"),
            _topic("CHEF", "Chef's Recommendation"),
        ],
        "cafe": [
            _topic("DRINK", "Seasonal Drink Launch"),
            _topic("DESSERT", "Dessert Pairing"),
        ],
        "spa": [
            _topic("SPA", "Treatment of the Month"),
            _topic("RELAX", "Stress Relief Package"),
        ],
        "beauty_salon": [
            _topic("HAIR", "Hair Trend of the Month"),
            _topic("MAKEUP", "Makeup Special"),
        ],
        "dentist": [
            _topic("CHECK", "Regular Checkup Reminder"),
            _topic("WHITE", "Whitening Special"),
        ],
        "gym": [
            _topic("FIT", "Monthly Challenge"),
            _topic("PT", "PT Program Introduction"),
        ],
        "car_repair": [
            _topic("CAR", "Seasonal Checkup Campaign"),
            _topic("SERVICE", "Maintenance Discount"),
        ],
    }

    UNIVERSAL_SUGGESTIONS = [
        _topic("REVIEW", "Customer Review Thank You"),
        _topic("TEAM", "Meet Our Team"),
        _topic("ANNIV", "Anniversary Celebration"),
        _topic("HOURS", "Hours Update"),
        _topic("NEWS", "Award or Certification News"),
        _topic("LOYAL", "Loyal Customer Appreciation"),
    ]

    def get_suggestions(
        self,
        category: str | None = None,
        weather: str | None = None,
        target_date: date | None = None,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        """Get content suggestions based on simple context."""
        suggestions: list[dict[str, Any]] = []
        today = target_date or date.today()
        weekday = today.weekday()
        month = today.month
        day = today.day

        if weather and weather in self.WEATHER_SUGGESTIONS:
            ws = self.WEATHER_SUGGESTIONS[weather]
            suggestions.append(
                {
                    "id": f"weather_{weather}",
                    "type": "weather",
                    "emoji": ws["emoji"],
                    "title_ko": ws["title_ko"],
                    "title_en": ws["title_en"],
                    "priority": 1,
                }
            )

        for event_id, event in self.SEASONAL_SUGGESTIONS.items():
            if month in event.get("months", []):
                if "days" not in event or day in event.get("days", []):
                    suggestions.append(
                        {
                            "id": f"seasonal_{event_id}",
                            "type": "seasonal",
                            "emoji": event["emoji"],
                            "title_ko": event["title_ko"],
                            "title_en": event["title_en"],
                            "priority": 2,
                        }
                    )

        if weekday in self.WEEKDAY_SUGGESTIONS:
            ws = self.WEEKDAY_SUGGESTIONS[weekday]
            suggestions.append(
                {
                    "id": f"weekday_{weekday}",
                    "type": "weekday",
                    "emoji": ws["emoji"],
                    "title_ko": ws["title_ko"],
                    "title_en": ws["title_en"],
                    "priority": 3,
                }
            )

        if category and category in self.CATEGORY_SUGGESTIONS:
            for i, cs in enumerate(self.CATEGORY_SUGGESTIONS[category][:2]):
                suggestions.append(
                    {
                        "id": f"category_{category}_{i}",
                        "type": "category",
                        "emoji": cs["emoji"],
                        "title_ko": cs["title_ko"],
                        "title_en": cs["title_en"],
                        "priority": 4,
                    }
                )

        for i, us in enumerate(self.UNIVERSAL_SUGGESTIONS):
            if len(suggestions) >= limit:
                break
            suggestions.append(
                {
                    "id": f"universal_{i}",
                    "type": "universal",
                    "emoji": us["emoji"],
                    "title_ko": us["title_ko"],
                    "title_en": us["title_en"],
                    "priority": 5,
                }
            )

        suggestions.sort(key=lambda x: x["priority"])
        return suggestions[:limit]

    def get_suggestion_by_id(self, suggestion_id: str) -> dict[str, Any] | None:
        """Get a specific suggestion by its ID."""
        all_suggestions = self.get_suggestions(limit=100)
        for suggestion in all_suggestions:
            if suggestion["id"] == suggestion_id:
                return suggestion
        return None

    def build_prompt_from_suggestion(
        self,
        suggestion: dict[str, Any],
        business_name: str,
        category: str | None = None,
        language: str = "en",
    ) -> str:
        """Build a GBP content prompt from a suggestion."""
        title_key = "title_en" if language == "en" else "title_ko"
        title = suggestion.get(title_key) or suggestion.get("title_en", "")

        return f"""Create a Google Business Profile post for {business_name}.

Topic: {title}
Business Type: {category or 'local business'}
Tone: Friendly, professional, engaging
Length: 2-3 short paragraphs

Include:
- A catchy opening line
- Key details about the offer or topic
- A clear call-to-action

Do NOT include:
- Hashtags (not supported on GBP)
- External links in the body
- Overly promotional language
"""
