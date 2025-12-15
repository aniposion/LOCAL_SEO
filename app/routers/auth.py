"""Authentication router."""

import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    get_password_hash,
    verify_password,
    verify_refresh_token,
)
from app.db.session import get_db
from app.integrations.email import EmailClient
from app.models.account import Account
from app.models.subscription import PlanType, Subscription, SubscriptionStatus
from app.routers.deps import get_current_user
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


@router.post("/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def signup(
    request: SignupRequest,
    req: Request,
    db: Session = Depends(get_db),
) -> TokenResponse:
    """Register a new user account with email verification."""
    # Check if email exists
    existing = db.query(Account).filter(Account.email == request.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    # Generate verification token
    verification_token = secrets.token_urlsafe(32)

    # Create account
    account = Account(
        email=request.email,
        password_hash=get_password_hash(request.password),
        full_name=request.full_name,
        company_name=request.company_name,
        phone=request.phone,
        timezone=request.timezone,
        language=request.language,
        verification_token=verification_token,
        terms_accepted_at=datetime.now(timezone.utc),
        privacy_accepted_at=datetime.now(timezone.utc),
        is_verified=False,
    )
    db.add(account)
    db.flush()

    # Create free subscription
    subscription = Subscription(
        account_id=account.id,
        plan_type=PlanType.FREE,
        status=SubscriptionStatus.ACTIVE,
        locations_limit=1,
        posts_per_month=10,
        api_calls_per_day=100,
    )
    db.add(subscription)
    db.commit()
    db.refresh(account)

    # Send verification email (async, don't block)
    try:
        email_client = EmailClient()
        verification_url = f"{settings.app_url}/verify-email?token={verification_token}"
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

    # Generate tokens
    access_token = create_access_token(subject=str(account.id))
    refresh_token = create_refresh_token(subject=str(account.id))

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.jwt_access_token_expire_minutes * 60,
    )


@router.post("/login", response_model=TokenResponse)
def login(
    request: LoginRequest,
    req: Request,
    db: Session = Depends(get_db),
) -> TokenResponse:
    """Authenticate user and return tokens."""
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

    access_token = create_access_token(subject=str(account.id))
    refresh_token = create_refresh_token(subject=str(account.id))

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.jwt_access_token_expire_minutes * 60,
    )


@router.post("/refresh", response_model=TokenResponse)
def refresh(request: RefreshRequest, db: Session = Depends(get_db)) -> TokenResponse:
    """Refresh access token using refresh token."""
    account_id = verify_refresh_token(request.refresh_token)

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

    access_token = create_access_token(subject=str(account.id))
    new_refresh_token = create_refresh_token(subject=str(account.id))

    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh_token,
        expires_in=settings.jwt_access_token_expire_minutes * 60,
    )


@router.post("/verify-email")
def verify_email(
    request: EmailVerificationRequest,
    db: Session = Depends(get_db),
) -> dict:
    """Verify email with token."""
    account = db.query(Account).filter(
        Account.verification_token == request.token
    ).first()

    if not account:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification token",
        )

    account.is_verified = True
    account.email_verified_at = datetime.now(timezone.utc)
    account.verification_token = None
    db.commit()

    return {"message": "Email verified successfully"}


@router.post("/resend-verification")
async def resend_verification(
    request: ResendVerificationRequest,
    db: Session = Depends(get_db),
) -> dict:
    """Resend verification email."""
    account = db.query(Account).filter(Account.email == request.email).first()

    if not account:
        # Don't reveal if email exists
        return {"message": "If the email exists, a verification link has been sent"}

    if account.is_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already verified",
        )

    # Generate new token
    account.verification_token = secrets.token_urlsafe(32)
    db.commit()

    # Send email
    try:
        email_client = EmailClient()
        verification_url = f"{settings.app_url}/verify-email?token={account.verification_token}"
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
    db: Session = Depends(get_db),
) -> dict:
    """Request password reset."""
    account = db.query(Account).filter(Account.email == request.email).first()

    if account:
        # Generate reset token
        account.password_reset_token = secrets.token_urlsafe(32)
        account.password_reset_expires = datetime.now(timezone.utc) + timedelta(hours=1)
        db.commit()

        # Send email
        try:
            email_client = EmailClient()
            reset_url = f"{settings.app_url}/reset-password?token={account.password_reset_token}"
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
    account = db.query(Account).filter(
        Account.password_reset_token == request.token,
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
