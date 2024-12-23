import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from pyjams.models import FeaturedPlaylist, Permission, PlaylistManager, User, UserRole


# Test database setup
@pytest.fixture(name="session")
@pytest.mark.unit
def session_fixture():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    SQLModel.metadata.drop_all(engine)


# Model Tests
@pytest.mark.unit
def test_user_creation(session: Session):
    user = User(spotify_id="test123", name="Test User", email="test@example.com", role=UserRole.USER)
    session.add(user)
    session.commit()

    db_user = session.get(User, user.id)
    assert db_user is not None  # Add None check
    assert db_user.spotify_id == "test123"
    assert db_user.name == "Test User"
    assert db_user.role == UserRole.USER


@pytest.mark.unit
def test_user_permissions():
    user = User(role=UserRole.USER)
    admin = User(role=UserRole.ADMIN)

    assert user.has_permission(Permission.SEARCH)
    assert user.has_permission(Permission.SUGGEST)
    assert not user.has_permission(Permission.ADMIN)

    assert admin.has_permission(Permission.ADMIN)
    assert admin.has_permission(Permission.MODERATE)


@pytest.mark.unit
def test_featured_playlist_creation(session: Session):
    user = User(spotify_id="creator123", name="Creator")
    session.add(user)
    session.commit()

    playlist = FeaturedPlaylist(
        spotify_id="playlist123", name="Test Playlist", description="Test Description", creator_id=user.id
    )
    session.add(playlist)
    session.commit()

    db_playlist = session.get(FeaturedPlaylist, playlist.id)
    assert db_playlist is not None  # Add None check
    assert db_playlist.spotify_id == "playlist123"
    assert db_playlist.name == "Test Playlist"
    assert db_playlist.creator_id == user.id


@pytest.mark.unit
def test_playlist_manager_assignment(session: Session):
    # Create and commit user first
    user = User(spotify_id="manager123", name="Manager")
    session.add(user)
    session.commit()  # Ensure user is committed and has an ID

    # Create playlist with the committed user's ID
    playlist = FeaturedPlaylist(
        spotify_id="playlist123",
        name="Test Playlist",
        creator_id=user.id,  # Now user.id is guaranteed to exist
    )
    session.add(playlist)
    session.commit()  # Commit playlist separately

    # Create manager association
    manager = PlaylistManager(
        playlist_id=playlist.id, user_id=user.id, permissions={"can_edit": True, "can_delete": True}
    )
    session.add(manager)
    session.commit()

    # Verify the manager was created correctly
    db_manager = session.get(PlaylistManager, manager.id)
    assert db_manager is not None
    assert db_manager.playlist_id == playlist.id
    assert db_manager.user_id == user.id
    assert db_manager.permissions["can_edit"] is True


@pytest.mark.unit
def test_user_get_by_spotify_id(session: Session):
    user = User(spotify_id="spotify123", name="Spotify User", email="spotify@example.com")
    session.add(user)
    session.commit()

    found_user = User.get_by_spotify_id(session, "spotify123")
    assert found_user is not None
    assert found_user.spotify_id == "spotify123"
    assert found_user.name == "Spotify User"


@pytest.mark.unit
def test_playlist_user_can_manage(session: Session):
    creator = User(spotify_id="creator123", name="Creator", role=UserRole.ADMIN)
    normal_user = User(spotify_id="user123", name="Normal User", role=UserRole.USER)
    session.add_all([creator, normal_user])
    session.commit()

    playlist = FeaturedPlaylist(spotify_id="playlist123", name="Test Playlist", creator_id=creator.id)
    session.add(playlist)
    session.commit()

    assert playlist.user_can_manage(creator) is True
    assert playlist.user_can_manage(normal_user) is False
