"""Authentication router."""

from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.auth_rate_limit import enforce_auth_rate_limit
from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    generate_opaque_token,
    get_password_hash,
    hash_opaque_token,
    verify_password,
    verify_refresh_token,
)
from app.db.session import get_db
from app.integrations.email import EmailClient
from app.models.account import Account
from app.models.subscription import PlanType, Subscription, SubscriptionStatus
from app.routers.deps import get_current_user
from app.services.plan_limits import PLAN_LIMITS_BY_PLAN
from app.schemas.auth import (
    EmailVerificationRequest,
    LoginRequest,
    PasswordChangeRequest,
    PasswordResetConfirm,
    PasswordResetRequest,
    RefreshRequest,
    ResendVerificationRequest,
    SignupRequest,
    TokenResponse,
    UserProfileResponse,
    UserProfileUpdate,
)

router = APIRouter(prefix="/auth", tags=["auth"])

EMAIL_VERIFICATION_TTL = timedelta(hours=24)
PASSWORD_RESET_TTL = timedelta(hours=1)
REFRESH_COOKIE_NAME = "refresh_token"


def _issue_account_token(ttl: timedelta) -> tuple[str, str, datetime]:
    """Generate a raw token for email delivery plus a stored hash and expiry."""
    raw_token = generate_opaque_token()
    return raw_token, hash_opaque_token(raw_token), datetime.now(timezone.utc) + ttl


def _refresh_cookie_same_site() -> Literal["lax", "none"]:
    """Choose the safest refresh cookie policy that still works in the current env."""
    return "lax" if settings.app_env == "dev" else "none"


def _refresh_cookie_path() -> str:
    """Return the configured refresh-cookie path for direct or proxy-prefixed APIs."""
    return settings.auth_cookie_path


def _set_refresh_cookie(response: Response, refresh_token: str) -> None:
    """Persist the refresh token in an httpOnly cookie."""
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=refresh_token,
        httponly=True,
        secure=settings.app_env in {"staging", "prod"},
        samesite=_refresh_cookie_same_site(),
        max_age=settings.jwt_refresh_token_expire_days * 24 * 60 * 60,
        path=_refresh_cookie_path(),
    )


def _clear_refresh_cookie(response: Response) -> None:
    """Remove the refresh token cookie."""
    response.delete_cookie(
        key=REFRESH_COOKIE_NAME,
        httponly=True,
        secure=settings.app_env in {"staging", "prod"},
        samesite=_refresh_cookie_same_site(),
        path=_refresh_cookie_path(),
    )


def _issue_session_tokens(response: Response, account_id: str) -> TokenResponse:
    """Issue a new access token plus httpOnly refresh cookie."""
    access_token = create_access_token(subject=account_id)
    refresh_token = create_refresh_token(subject=account_id)
    _set_refresh_cookie(response, refresh_token)
    return TokenResponse(
        access_token=access_token,
        refresh_token=None,
        expires_in=settings.jwt_access_token_expire_minutes * 60,
    )


@router.post("/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def signup(
    request: SignupRequest,
    req: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> TokenResponse:
    """Register a new user account with email verification."""
    enforce_auth_rate_limit(req, db, action="signup", identity=request.email)

    # Check if email exists
    existing = db.query(Account).filter(Account.email == request.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    raw_verification_token, verification_token_hash, verification_token_expires = _issue_account_token(
        EMAIL_VERIFICATION_TTL
    )

    # Create account
    account = Account(
        email=request.email,
        password_hash=get_password_hash(request.password),
        full_name=request.full_name,
        company_name=request.company_name,
        phone=request.phone,
        timezone=request.timezone,
        language=request.language,
        verification_token=verification_token_hash,
        verification_token_expires=verification_token_expires,
        terms_accepted_at=datetime.now(timezone.utc),
        privacy_accepted_at=datetime.now(timezone.utc),
        is_verified=False,
    )
    db.add(account)
    db.flush()

    # Create free subscription
    free_plan_limits = PLAN_LIMITS_BY_PLAN[PlanType.FREE]
    subscription = Subscription(
        account_id=account.id,
        plan_type=PlanType.FREE,
        status=SubscriptionStatus.ACTIVE,
        locations_limit=free_plan_limits["locations"],
        posts_per_month=free_plan_limits["posts_per_month"],
        api_calls_per_day=free_plan_limits["api_calls_per_day"],
    )
    db.add(subscription)
    db.commit()
    db.refresh(account)

    # Send verification email (async, don't block)
    try:
        email_client = EmailClient()
        verification_url = f"{settings.app_url}/verify-email?token={raw_verification_token}"
        await email_client.send(
            to_email=account.email,
            subject="Verify your email - Local SEO Optimizer",
            body=f"""
Welcome to Local SEO Optimizer!

Please verify your email by clicking the link below:
{verification_url}

This link expires in 24 hours.

If you didn't create this account, please ignore this email.
            """,
        )
    except Exception:
        pass  # Don't fail signup if email fails

    return _issue_session_tokens(response, str(account.id))


@router.post("/login", response_model=TokenResponse)
def login(
    request: LoginRequest,
    req: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> TokenResponse:
    """Authenticate user and return tokens."""
    enforce_auth_rate_limit(req, db, action="login", identity=request.email)

    account = db.query(Account).filter(Account.email == request.email).first()

    if not account or not account.password_hash:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    if not verify_password(request.password, account.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    if not account.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled",
        )

    # Update last login
    account.last_login_at = datetime.now(timezone.utc)
    account.last_login_ip = req.client.host if req.client else None
    db.commit()

    return _issue_session_tokens(response, str(account.id))


@router.post("/refresh", response_model=TokenResponse)
def refresh(
    req: Request,
    response: Response,
    request: RefreshRequest | None = None,
    db: Session = Depends(get_db),
) -> TokenResponse:
    """Refresh access token using refresh token."""
    enforce_auth_rate_limit(req, db, action="refresh")

    refresh_token = request.refresh_token if request and request.refresh_token else req.cookies.get(REFRESH_COOKIE_NAME)

    account_id = verify_refresh_token(refresh_token) if refresh_token else None

    if not account_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    account = db.query(Account).filter(Account.id == account_id).first()

    if not account or not account.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account not found or disabled",
        )

    return _issue_session_tokens(response, str(account.id))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response) -> None:
    """Clear the refresh token cookie for the current browser session."""
    _clear_refresh_cookie(response)


@router.post("/verify-email")
def verify_email(
    request: EmailVerificationRequest,
    db: Session = Depends(get_db),
) -> dict:
    """Verify email with token."""
    now = datetime.now(timezone.utc)
    token_hash = hash_opaque_token(request.token)
    account = db.query(Account).filter(
        or_(
            Account.verification_token == token_hash,
            Account.verification_token == request.token,
        ),
        or_(
            Account.verification_token_expires.is_(None),
            Account.verification_token_expires > now,
        ),
    ).first()

    if not account:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification token",
        )

    account.is_verified = True
    account.email_verified_at = datetime.now(timezone.utc)
    account.verification_token = None
    account.verification_token_expires = None
    db.commit()

    return {"message": "Email verified successfully"}


@router.post("/resend-verification")
async def resend_verification(
    request: ResendVerificationRequest,
    req: Request,
    db: Session = Depends(get_db),
) -> dict:
    """Resend verification email."""
    enforce_auth_rate_limit(req, db, action="resend_verification", identity=request.email)

    account = db.query(Account).filter(Account.email == request.email).first()

    if not account:
        # Don't reveal if email exists
        return {"message": "If the email exists, a verification link has been sent"}

    if account.is_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already verified",
        )

    raw_verification_token, verification_token_hash, verification_token_expires = _issue_account_token(
        EMAIL_VERIFICATION_TTL
    )
    account.verification_token = verification_token_hash
    account.verification_token_expires = verification_token_expires
    db.commit()

    # Send email
    try:
        email_client = EmailClient()
        verification_url = f"{settings.app_url}/verify-email?token={raw_verification_token}"
        await email_client.send(
            to_email=account.email,
            subject="Verify your email - Local SEO Optimizer",
            body=f"Please verify your email: {verification_url}",
        )
    except Exception:
        pass

    return {"message": "If the email exists, a verification link has been sent"}


@router.post("/forgot-password")
async def forgot_password(
    request: PasswordResetRequest,
    req: Request,
    db: Session = Depends(get_db),
) -> dict:
    """Request password reset."""
    enforce_auth_rate_limit(req, db, action="forgot_password", identity=request.email)

    account = db.query(Account).filter(Account.email == request.email).first()

    if account:
        raw_reset_token, password_reset_token_hash, password_reset_expires = _issue_account_token(
            PASSWORD_RESET_TTL
        )
        account.password_reset_token = password_reset_token_hash
        account.password_reset_expires = password_reset_expires
        db.commit()

        # Send email
        try:
            email_client = EmailClient()
            reset_url = f"{settings.app_url}/reset-password?token={raw_reset_token}"
            await email_client.send(
                to_email=account.email,
                subject="Reset your password - Local SEO Optimizer",
                body=f"Reset your password: {reset_url}\n\nThis link expires in 1 hour.",
            )
        except Exception:
            pass

    # Always return success to prevent email enumeration
    return {"message": "If the email exists, a password reset link has been sent"}


@router.post("/reset-password")
def reset_password(
    request: PasswordResetConfirm,
    db: Session = Depends(get_db),
) -> dict:
    """Reset password with token."""
    token_hash = hash_opaque_token(request.token)
    account = db.query(Account).filter(
        or_(
            Account.password_reset_token == token_hash,
            Account.password_reset_token == request.token,
        ),
        Account.password_reset_expires > datetime.now(timezone.utc),
    ).first()

    if not account:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        )

    account.password_hash = get_password_hash(request.new_password)
    account.password_reset_token = None
    account.password_reset_expires = None
    db.commit()

    return {"message": "Password reset successfully"}


@router.post("/change-password")
def change_password(
    request: PasswordChangeRequest,
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_user),
) -> dict:
    """Change password for authenticated user."""
    if not verify_password(request.current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )

    current_user.password_hash = get_password_hash(request.new_password)
    db.commit()

    return {"message": "Password changed successfully"}


@router.get("/me", response_model=UserProfileResponse)
def get_profile(
    current_user: Account = Depends(get_current_user),
) -> Account:
    """Get current user profile."""
    return current_user


@router.patch("/me", response_model=UserProfileResponse)
def update_profile(
    request: UserProfileUpdate,
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_user),
) -> Account:
    """Update current user profile."""
    update_data = request.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(current_user, field, value)

    db.commit()
    db.refresh(current_user)
    return current_user
