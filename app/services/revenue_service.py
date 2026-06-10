"""Revenue profile service."""

from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.location import Location
from app.models.metrics import MetricSnapshot
from app.models.revenue import RevenueProfile
from app.schemas.revenue import (
    RevenueProfileCreate,
    RevenueProfileResponse,
    RevenueProfileUpdate,
    RevenueProjectionResponse,
)


class RevenueService:
    """Manage revenue profile inputs and projections."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_location_for_account(self, location_id: UUID, account_id: UUID) -> Location | None:
        return (
            self.db.query(Location)
            .filter(Location.id == location_id, Location.account_id == account_id)
            .first()
        )

    def get_or_create_profile(self, location_id: UUID) -> RevenueProfile:
        profile = (
            self.db.query(RevenueProfile)
            .filter(RevenueProfile.location_id == location_id)
            .first()
        )
        if profile:
            return profile

        profile = RevenueProfile(location_id=location_id)
        self.db.add(profile)
        self.db.commit()
        self.db.refresh(profile)
        return profile

    def update_profile(self, location_id: UUID, payload: RevenueProfileCreate | RevenueProfileUpdate) -> RevenueProfile:
        profile = self.get_or_create_profile(location_id)
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(profile, field, value)
        self.db.commit()
        self.db.refresh(profile)
        return profile

    def build_projection(self, location_id: UUID) -> RevenueProjectionResponse:
        profile = self.get_or_create_profile(location_id)
        call_total = (
            self.db.query(MetricSnapshot)
            .filter(MetricSnapshot.location_id == location_id)
            .order_by(MetricSnapshot.snapshot_date.desc())
            .limit(30)
            .all()
        )
        calls = sum(snapshot.calls for snapshot in call_total)
        missed_calls = max(0, round(calls * Decimal("0.15")))

        bookings = self._apply_rate(calls, profile.call_to_booking_rate)
        visits = self._apply_rate(bookings, profile.booking_to_visit_rate)
        sales = self._apply_rate(visits, profile.visit_to_sale_rate)

        estimated_revenue = self._money(Decimal(sales) * profile.average_order_value)
        estimated_profit = self._money(
            estimated_revenue * (profile.gross_margin_percent / Decimal("100"))
        )

        recovered_calls = self._apply_rate(missed_calls, profile.missed_call_recovery_rate)
        recovered_bookings = self._apply_rate(recovered_calls, profile.call_to_booking_rate)
        recovered_visits = self._apply_rate(recovered_bookings, profile.booking_to_visit_rate)
        recovered_sales = self._apply_rate(recovered_visits, profile.visit_to_sale_rate)
        recovery_revenue = self._money(Decimal(recovered_sales) * profile.average_order_value)

        return RevenueProjectionResponse(
            location_id=location_id,
            estimated_bookings_from_calls=bookings,
            estimated_visits_from_calls=visits,
            estimated_sales_from_calls=sales,
            estimated_revenue_from_calls=estimated_revenue,
            estimated_gross_profit_from_calls=estimated_profit,
            missed_call_recovery_revenue=recovery_revenue,
        )

    @staticmethod
    def _apply_rate(count: int, rate_percent: Decimal) -> int:
        return int((Decimal(count) * (rate_percent / Decimal("100"))).quantize(Decimal("1"), rounding=ROUND_HALF_UP))

    @staticmethod
    def _money(amount: Decimal) -> Decimal:
        return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
