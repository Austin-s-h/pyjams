import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from pyjams.app import app
from pyjams.models import User, UserRole


@pytest.fixture(scope="session")
@pytest.mark.unit
def client():
    return TestClient(app)


@pytest.fixture(scope="session")
@pytest.mark.unit
def test_db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    yield engine
    SQLModel.metadata.drop_all(engine)


@pytest.fixture
@pytest.mark.unit
def session(test_db):
    with Session(test_db) as session:
        yield session


@pytest.fixture
@pytest.mark.unit
def test_user(session):
    user = User(spotify_id="testuser123", name="Test User", email="test@example.com", role=UserRole.USER)
    session.add(user)
    session.commit()
    return user
