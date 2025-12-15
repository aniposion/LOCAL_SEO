"""Pytest configuration and fixtures."""

import os
from collections.abc import Generator
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import create_access_token, get_password_hash
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.account import Account, AccountRole
from app.models.location import Location

# Use SQLite for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db() -> Generator[Session, None, None]:
    """Create a fresh database for each test."""
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db: Session) -> Generator[TestClient, None, None]:
    """Create a test client with database override."""

    def override_get_db() -> Generator[Session, None, None]:
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def test_user(db: Session) -> Account:
    """Create a test user."""
    user = Account(
        id=uuid4(),
        email="test@example.com",
        password_hash=get_password_hash("testpassword123"),
        role=AccountRole.OWNER,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def test_user_token(test_user: Account) -> str:
    """Create an access token for test user."""
    return create_access_token(subject=str(test_user.id))


@pytest.fixture
def auth_headers(test_user_token: str) -> dict[str, str]:
    """Create authorization headers."""
    return {"Authorization": f"Bearer {test_user_token}"}


@pytest.fixture
def test_location(db: Session, test_user: Account) -> Location:
    """Create a test location."""
    location = Location(
        id=uuid4(),
        account_id=test_user.id,
        name="Test Business",
        address="123 Test St",
        city="Test City",
        state="TS",
        country="US",
        phone="555-1234",
        services=["service1", "service2"],
    )
    db.add(location)
    db.commit()
    db.refresh(location)
    return location
