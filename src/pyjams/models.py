import os
from datetime import datetime
from enum import Enum, Flag, auto
from typing import Any, Self

from pydantic import Field as PydanticField
from pydantic_settings import BaseSettings
from spotipy import Spotify
from spotipy.oauth2 import SpotifyOAuth
from sqlalchemy import JSON, Column
from sqlmodel import Field, Relationship, Session, SQLModel, create_engine


class Settings(BaseSettings):
    """Application settings."""

    SPOTIFY_CLIENT_ID: str = PydanticField(..., description="Spotify API client ID (pyjams)")
    SPOTIFY_CLIENT_SECRET: str = PydanticField(..., description="Spotify API client secret (pyjams)")
    SPOTIFY_ADMIN_USERNAME: str = PydanticField(..., description="The Spotify username (numerical) of the admin user")
    SECRET_KEY: str = PydanticField(default_factory=lambda: os.urandom(24).hex())
    BASE_URL: str = "http://127.0.0.1:4884"
    DATABASE_URL: str = "sqlite:///pyjams.db"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()


class Permission(Flag):
    NONE = 0
    VIEW = auto()  # Basic viewing permission
    SEARCH = auto()  # Can search for songs
    SUGGEST = auto()  # Can suggest songs
    VOTE = auto()  # Can vote on songs
    ADD_SONGS = auto()  # Can directly add songs
    REMOVE_SONGS = auto()  # Can remove songs
    MANAGE_PLAYLIST = auto()  # Can edit playlist details
    MANAGE_USERS = auto()  # Can manage other users
    MODERATE = auto()  # Can moderate content
    ADMIN = auto()  # Full administrative access

    # Common permission sets
    BASIC = VIEW | SEARCH
    CONTRIBUTOR = BASIC | SUGGEST | VOTE
    MANAGER = CONTRIBUTOR | ADD_SONGS | REMOVE_SONGS | MANAGE_PLAYLIST
    MODERATOR = MANAGER | MODERATE
    ALL = ~NONE


class UserRole(str, Enum):
    GUEST = "guest"
    USER = "user"
    MANAGER = "manager"
    MODERATOR = "moderator"
    ADMIN = "admin"

    @property
    def permissions(self) -> Permission:
        return {
            self.GUEST: Permission.BASIC,
            self.USER: Permission.CONTRIBUTOR,
            self.MANAGER: Permission.MANAGER,
            self.MODERATOR: Permission.MODERATOR,
            self.ADMIN: Permission.ALL,
        }[self]


class User(SQLModel, table=True):
    """User model with role-based permissions."""

    id: int | None = Field(default=None, primary_key=True)
    spotify_id: str | None = Field(unique=True, index=True, nullable=True)  # Nullable for guest users
    name: str | None = None
    email: str | None = Field(unique=True, index=True, nullable=True)
    role: UserRole = Field(default=UserRole.GUEST)
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_login: datetime | None = None

    # Relationships
    featured_playlists: list["FeaturedPlaylist"] = Relationship(back_populates="creator")
    managed_playlists: list["PlaylistManager"] = Relationship(back_populates="manager")

    def has_permission(self, permission: Permission) -> bool:
        """Check if user has specific permission."""
        return bool(self.role.permissions & permission)

    def has_permissions(self, *permissions: Permission) -> bool:
        """Check if user has all specified permissions."""
        required = Permission.NONE
        for permission in permissions:
            required |= permission
        return bool(self.role.permissions & required == required)

    def can_manage_playlist(self, playlist_id: int) -> bool:
        """Check if user can manage a specific playlist."""
        if self.is_admin:
            return True
        return any(pm.is_active and pm.playlist_id == playlist_id for pm in self.managed_playlists)

    @property
    def is_admin(self) -> bool:
        return self.role == UserRole.ADMIN

    @property
    def is_moderator(self) -> bool:
        return self.role in (UserRole.MODERATOR, UserRole.ADMIN)

    @classmethod
    def get_by_spotify_id(cls, session: Session, spotify_id: str) -> Self | None:
        return session.query(cls).filter(cls.spotify_id == spotify_id).first()


class FeaturedPlaylist(SQLModel, table=True):
    """Renamed from PublicPlaylist for better clarity."""

    id: int | None = Field(default=None, primary_key=True)
    spotify_id: str = Field(unique=True, index=True)
    name: str = Field()
    description: str | None = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    creator_id: int = Field(foreign_key="user.id")
    is_active: bool = Field(default=True)
    is_visible: bool = Field(default=True)  # For moderation
    contribution_rules: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))

    # Relationships
    creator: User = Relationship(back_populates="featured_playlists")
    managers: list["PlaylistManager"] = Relationship(back_populates="playlist")

    def user_can_manage(self, user: User) -> bool:
        """Check if user can manage this playlist."""
        if user.is_admin or user.id == self.creator_id:
            return True
        return any(pm.is_active for pm in self.managers if pm.user_id == user.id)

    def add_manager(self, session: Session, user: User, permissions: dict[str, Any] | None = None) -> "PlaylistManager":
        manager = PlaylistManager(
            playlist_id=self.id, user_id=user.id, permissions=permissions or {"can_edit": True, "can_delete": False}
        )
        session.add(manager)
        return manager


class PlaylistManager(SQLModel, table=True):
    """Model for users who can manage a featured playlist."""

    id: int | None = Field(default=None, primary_key=True)
    playlist_id: int = Field(foreign_key="featuredplaylist.id")
    user_id: int = Field(foreign_key="user.id")
    added_at: datetime = Field(default_factory=datetime.utcnow)
    is_active: bool = Field(default=True)
    permissions: dict[str, Any] = Field(
        default_factory=lambda: {
            "can_edit": True,
            "can_delete": False,
            "can_manage_users": False,
            "can_moderate": False,
        },
        sa_column=Column(JSON),
    )

    # Relationships
    playlist: FeaturedPlaylist = Relationship(back_populates="managers")
    manager: User = Relationship(back_populates="managed_playlists")

    def has_permission(self, permission_key: str) -> bool:
        """Check if manager has specific playlist permission."""
        return bool(self.is_active and self.permissions.get(permission_key, False))


class ModerationAction(SQLModel, table=True):
    """Track moderation actions on playlists."""

    id: int | None = Field(default=None, primary_key=True)
    playlist_id: int = Field(foreign_key="featuredplaylist.id")
    moderator_id: int = Field(foreign_key="user.id")
    action_type: str  # e.g., "hide", "unhide", "warn", etc.
    reason: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    action_metadata: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))  # Renamed from metadata

    # Relationships
    playlist: FeaturedPlaylist = Relationship()
    moderator: User = Relationship()


class Admin(SQLModel, table=True):
    """Admin model for storing admin users."""

    id: int | None = Field(default=None, primary_key=True)
    spotify_id: str = Field(unique=True, index=True)
    name: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    is_active: bool = Field(default=True)

    @property
    def user(self) -> User | None:
        """Get associated user record."""
        from sqlmodel import Session

        with Session(engine) as session:
            return session.query(User).filter(User.spotify_id == self.spotify_id).first()


# Database setup
engine = create_engine(settings.DATABASE_URL)


def get_session():
    with Session(engine) as session:
        yield session


def init_spotify_oauth() -> SpotifyOAuth:
    """Initialize Spotify OAuth instance."""
    return SpotifyOAuth(
        client_id=settings.SPOTIFY_CLIENT_ID,
        client_secret=settings.SPOTIFY_CLIENT_SECRET,
        redirect_uri=f"{settings.BASE_URL}/callback",  # Use configured base URL
        scope=[
            "playlist-modify-public",
            "playlist-modify-private",
            "playlist-read-private",
            "playlist-read-collaborative",
            "user-read-private",
            "user-read-email",
        ],
    )


class TokenError(Exception):
    """Raised when there are issues with the Spotify token."""

    pass


async def get_spotify(session) -> Spotify:
    """Get authenticated Spotify client."""
    if "token_info" not in session:
        raise TokenError("No token info in session")

    token_info = session["token_info"]

    # Validate token info structure
    if not isinstance(token_info, dict) or "access_token" not in token_info:
        raise TokenError("Invalid token info structure")

    # Check if token is expired
    oauth = init_spotify_oauth()
    if oauth.is_token_expired(token_info):
        try:
            token_info = oauth.refresh_access_token(token_info["refresh_token"])
            session["token_info"] = token_info
        except Exception as e:
            raise TokenError(f"Failed to refresh token: {e!s}")

    return Spotify(auth=token_info["access_token"])
