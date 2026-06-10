"""Pytest configuration and fixtures."""

from collections.abc import Generator
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import ARRAY as SA_ARRAY, create_engine
from sqlalchemy.dialects.postgresql import ARRAY as PG_ARRAY, JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.types import JSON

from app.core.security import create_access_token, get_password_hash
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.account import Account, AccountRole
from app.models.location import Location


@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(_type, _compiler, **_kwargs) -> str:
    """Treat PostgreSQL JSONB as JSON in SQLite-backed tests."""
    return "JSON"


@compiles(SA_ARRAY, "sqlite")
@compiles(PG_ARRAY, "sqlite")
def compile_array_sqlite(_type, _compiler, **_kwargs) -> str:
    """Treat PostgreSQL ARRAY as JSON in SQLite-backed tests."""
    return "JSON"


def _array_bind_processor(_self, dialect):
    """Serialize ARRAY payloads as JSON for SQLite tests."""
    return JSON().bind_processor(dialect)


def _array_result_processor(_self, dialect, coltype):
    """Deserialize ARRAY payloads from JSON for SQLite tests."""
    return JSON().result_processor(dialect, coltype)


SA_ARRAY.bind_processor = _array_bind_processor
PG_ARRAY.bind_processor = _array_bind_processor
SA_ARRAY.result_processor = _array_result_processor
PG_ARRAY.result_processor = _array_result_processor

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
def other_user(db: Session) -> Account:
    """Create a second account for ownership tests."""
    user = Account(
        id=uuid4(),
        email="other@example.com",
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
def other_user_token(other_user: Account) -> str:
    """Create an access token for the second test user."""
    return create_access_token(subject=str(other_user.id))


@pytest.fixture
def other_auth_headers(other_user_token: str) -> dict[str, str]:
    """Create authorization headers for the second test user."""
    return {"Authorization": f"Bearer {other_user_token}"}


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


@pytest.fixture
def other_location(db: Session, other_user: Account) -> Location:
    """Create a location for the second test user."""
    location = Location(
        id=uuid4(),
        account_id=other_user.id,
        name="Other Business",
        address="999 Other St",
        city="Other City",
        state="OS",
        country="US",
        phone="555-9999",
        services=["other-service"],
    )
    db.add(location)
    db.commit()
    db.refresh(location)
    return location
