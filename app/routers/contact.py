"""Public contact request API."""

from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.account import Account, AccountRole
from app.models.contact import ContactRequest, ContactRequestStatus
from app.routers.deps import get_current_user
from app.services.notification import NotificationService

router = APIRouter(prefix="/contact", tags=["contact"])

PUBLIC_PACKAGE_IDS = {"maps_starter", "calls_growth", "competitive_market"}


class ContactRequestCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    email: EmailStr
    subject: str = Field(default="Local SEO audit review request", min_length=1, max_length=200)
    message: str = Field(..., min_length=5, max_length=5000)
    phone: str | None = Field(default=None, max_length=50)
    business_name: str | None = Field(default=None, max_length=200)
    source: str = Field(default="contact_page", min_length=1, max_length=80)
    audit_id: str | None = Field(default=None, max_length=36)
    recommended_package: str | None = Field(default=None, max_length=80)
    metadata: dict | None = None


class ContactRequestResponse(BaseModel):
    id: str
    name: str
    email: str
    subject: str
    message: str
    phone: str | None
    business_name: str | None
    source: str
    recommended_package: str | None
    audit_id: str | None
    lead_score: int
    sales_notes: str | None
    close_reason: str | None
    contacted_at: datetime | None
    booked_at: datetime | None
    won_at: datetime | None
    lost_at: datetime | None
    closed_at: datetime | None
    status: ContactRequestStatus
    created_at: datetime
    updated_at: datetime


class ContactRequestListResponse(BaseModel):
    requests: list[ContactRequestResponse]
    total: int


class ContactRequestSummaryResponse(BaseModel):
    total: int
    by_status: dict[str, int]
    booked_conversion_rate: float
    won_conversion_rate: float
    avg_first_response_hours: float | None
    new_over_24h_total: int
    sla_target_hours: int


class ContactRequestStatusUpdate(BaseModel):
    status: ContactRequestStatus
    sales_notes: str | None = Field(default=None, max_length=2000)
    close_reason: str | None = Field(default=None, max_length=500)


def _metadata_value(metadata: dict | None, *keys: str) -> str | None:
    if not isinstance(metadata, dict):
        return None

    for key in keys:
        value = metadata.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _infer_recommended_package(payload: ContactRequestCreate) -> str:
    if payload.recommended_package and payload.recommended_package.strip().lower() in PUBLIC_PACKAGE_IDS:
        return payload.recommended_package.strip().lower()

    metadata_package = _metadata_value(payload.metadata, "recommended_package", "package", "plan")
    if metadata_package and metadata_package.strip().lower() in PUBLIC_PACKAGE_IDS:
        return metadata_package.strip().lower()

    text = " ".join(
        [
            payload.subject or "",
            payload.message or "",
            payload.business_name or "",
            payload.source or "",
            _metadata_value(payload.metadata, "source", "campaign", "utm_campaign") or "",
        ]
    ).lower()

    if any(
        keyword in text
        for keyword in (
            "competitive",
            "competitor",
            "competition",
            "competitive market",
            "local market",
            "ranking",
            "rank",
            "multi-location",
            "multiple locations",
            "franchise",
            "review gap",
        )
    ):
        return "competitive_market"

    if any(
        keyword in text
        for keyword in (
            "call",
            "lead",
            "booking",
            "appointment",
            "revenue",
            "growth",
            "plumbing",
            "hvac",
            "roofing",
            "dental",
            "emergency",
        )
    ):
        return "calls_growth"

    return "maps_starter"


def _score_contact_request(payload: ContactRequestCreate, recommended_package: str) -> int:
    score = 35
    message = payload.message.strip()
    source = payload.source.strip().lower()
    text = f"{payload.subject} {message} {source}".lower()

    if payload.phone and payload.phone.strip():
        score += 15
    if payload.business_name and payload.business_name.strip():
        score += 10
    if len(message) >= 120:
        score += 10
    if source in {"free_audit", "audit_results", "onboarding_solution", "pricing_page"}:
        score += 10
    if recommended_package == "calls_growth":
        score += 10
    elif recommended_package == "competitive_market":
        score += 20
    if any(keyword in text for keyword in ("pilot", "managed", "price", "pricing", "budget", "start")):
        score += 10

    return min(score, 100)


def _serialize(request: ContactRequest) -> ContactRequestResponse:
    return ContactRequestResponse(
        id=str(request.id),
        name=request.name,
        email=request.email,
        subject=request.subject,
        message=request.message,
        phone=request.phone,
        business_name=request.business_name,
        source=request.source,
        recommended_package=request.recommended_package,
        audit_id=request.audit_id,
        lead_score=request.lead_score,
        sales_notes=request.sales_notes,
        close_reason=request.close_reason,
        contacted_at=request.contacted_at,
        booked_at=request.booked_at,
        won_at=request.won_at,
        lost_at=request.lost_at,
        closed_at=request.closed_at,
        status=ContactRequestStatus(request.status),
        created_at=request.created_at,
        updated_at=request.updated_at,
    )


def _require_admin(account: Account) -> None:
    if account.role != AccountRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")


def _as_aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _first_response_at(request: ContactRequest) -> datetime | None:
    candidates = [
        request.contacted_at,
        request.booked_at,
        request.won_at,
        request.lost_at,
        request.closed_at,
    ]
    aware_candidates = [item for item in (_as_aware(value) for value in candidates) if item]
    return min(aware_candidates) if aware_candidates else None


def _notify_admins(db: Session, request: ContactRequest) -> None:
    admins = (
        db.query(Account)
        .filter(
            Account.role == AccountRole.ADMIN,
            Account.is_active == True,  # noqa: E712
        )
        .all()
    )
    if not admins:
        return

    notifier = NotificationService(db)
    message = (
        f"Name: {request.name}\n"
        f"Email: {request.email}\n"
        f"Package: {request.recommended_package or 'not inferred'}\n"
        f"Lead score: {request.lead_score}\n"
        f"Subject: {request.subject}\n\n"
        f"{request.message[:1000]}"
    )
    for admin in admins:
        notifier.send_inbox_notification(
            account_id=admin.id,
            title="New contact request",
            message=message,
            notification_type="contact_request_new",
            url="/admin",
        )


@router.post("/requests", response_model=ContactRequestResponse, status_code=status.HTTP_201_CREATED)
def create_contact_request(
    payload: ContactRequestCreate,
    db: Session = Depends(get_db),
) -> ContactRequestResponse:
    email = str(payload.email).strip().lower()
    source = payload.source.strip() or "contact_page"
    recent_cutoff = datetime.now(timezone.utc) - timedelta(minutes=5)
    recent_duplicate = (
        db.query(ContactRequest)
        .filter(
            ContactRequest.email == email,
            ContactRequest.source == source,
            ContactRequest.created_at >= recent_cutoff,
        )
        .first()
    )
    if recent_duplicate:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="A recent contact request already exists for this email. Please try again in a few minutes.",
        )

    recommended_package = _infer_recommended_package(payload)
    lead_score = _score_contact_request(payload, recommended_package)
    contact_request = ContactRequest(
        name=payload.name.strip(),
        email=email,
        subject=payload.subject.strip(),
        message=payload.message.strip(),
        phone=payload.phone.strip() if payload.phone else None,
        business_name=payload.business_name.strip() if payload.business_name else None,
        source=source,
        recommended_package=recommended_package,
        audit_id=payload.audit_id or _metadata_value(payload.metadata, "audit_id", "auditId"),
        lead_score=lead_score,
        extra_data=payload.metadata,
        status=ContactRequestStatus.NEW.value,
    )
    db.add(contact_request)
    db.commit()
    db.refresh(contact_request)

    _notify_admins(db, contact_request)
    return _serialize(contact_request)


@router.get("/requests", response_model=ContactRequestListResponse)
def list_contact_requests(
    status_filter: ContactRequestStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_user),
) -> ContactRequestListResponse:
    _require_admin(current_user)

    query = db.query(ContactRequest)
    if status_filter:
        query = query.filter(ContactRequest.status == status_filter.value)

    total = query.count()
    requests = (
        query.order_by(desc(ContactRequest.lead_score), desc(ContactRequest.created_at))
        .offset(offset)
        .limit(limit)
        .all()
    )
    return ContactRequestListResponse(
        requests=[_serialize(item) for item in requests],
        total=total,
    )


@router.get("/summary", response_model=ContactRequestSummaryResponse)
def get_contact_request_summary(
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_user),
) -> ContactRequestSummaryResponse:
    _require_admin(current_user)

    status_counts = {
        status_item.value: 0
        for status_item in ContactRequestStatus
    }
    rows = (
        db.query(ContactRequest.status, func.count(ContactRequest.id))
        .group_by(ContactRequest.status)
        .all()
    )
    for status_value, count in rows:
        status_counts[str(status_value)] = int(count)

    total = sum(status_counts.values())
    booked_total = status_counts.get(ContactRequestStatus.BOOKED.value, 0) + status_counts.get(
        ContactRequestStatus.WON.value,
        0,
    )
    won_total = status_counts.get(ContactRequestStatus.WON.value, 0)
    booked_conversion_rate = round((booked_total / total) * 100, 1) if total else 0.0
    won_conversion_rate = round((won_total / total) * 100, 1) if total else 0.0

    stale_cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    new_over_24h_total = (
        db.query(ContactRequest)
        .filter(
            ContactRequest.status == ContactRequestStatus.NEW.value,
            ContactRequest.created_at <= stale_cutoff,
        )
        .count()
    )

    response_hours: list[float] = []
    responded_requests = (
        db.query(ContactRequest)
        .filter(ContactRequest.status != ContactRequestStatus.NEW.value)
        .order_by(desc(ContactRequest.created_at))
        .limit(500)
        .all()
    )
    for request in responded_requests:
        created_at = _as_aware(request.created_at)
        first_response = _first_response_at(request)
        if created_at and first_response and first_response >= created_at:
            response_hours.append((first_response - created_at).total_seconds() / 3600)

    avg_first_response_hours = (
        round(sum(response_hours) / len(response_hours), 1)
        if response_hours
        else None
    )

    return ContactRequestSummaryResponse(
        total=total,
        by_status=status_counts,
        booked_conversion_rate=booked_conversion_rate,
        won_conversion_rate=won_conversion_rate,
        avg_first_response_hours=avg_first_response_hours,
        new_over_24h_total=new_over_24h_total,
        sla_target_hours=24,
    )


@router.patch("/requests/{request_id}", response_model=ContactRequestResponse)
def update_contact_request_status(
    request_id: UUID,
    payload: ContactRequestStatusUpdate,
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_user),
) -> ContactRequestResponse:
    _require_admin(current_user)

    contact_request = db.query(ContactRequest).filter(ContactRequest.id == request_id).first()
    if contact_request is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contact request not found")

    now = datetime.now(timezone.utc)
    contact_request.status = payload.status.value
    if payload.sales_notes is not None:
        contact_request.sales_notes = payload.sales_notes.strip() or None
    if payload.close_reason is not None:
        contact_request.close_reason = payload.close_reason.strip() or None
    if payload.status == ContactRequestStatus.CONTACTED and contact_request.contacted_at is None:
        contact_request.contacted_at = now
    if payload.status == ContactRequestStatus.BOOKED:
        if contact_request.contacted_at is None:
            contact_request.contacted_at = now
        if contact_request.booked_at is None:
            contact_request.booked_at = now
    if payload.status == ContactRequestStatus.WON:
        if contact_request.contacted_at is None:
            contact_request.contacted_at = now
        if contact_request.booked_at is None:
            contact_request.booked_at = now
        if contact_request.won_at is None:
            contact_request.won_at = now
        contact_request.closed_at = now
    if payload.status == ContactRequestStatus.LOST:
        if contact_request.contacted_at is None:
            contact_request.contacted_at = now
        if contact_request.lost_at is None:
            contact_request.lost_at = now
        contact_request.closed_at = now
    if payload.status in {ContactRequestStatus.CLOSED, ContactRequestStatus.SPAM}:
        if contact_request.contacted_at is None:
            contact_request.contacted_at = now
        contact_request.closed_at = now
    elif payload.status == ContactRequestStatus.NEW:
        contact_request.closed_at = None
        contact_request.close_reason = None

    db.commit()
    db.refresh(contact_request)
    return _serialize(contact_request)
