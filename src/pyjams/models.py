import os
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import Field as PydanticField
from pydantic_settings import BaseSettings
from spotipy import Spotify
from spotipy.oauth2 import SpotifyOAuth
from sqlalchemy import JSON, Column
from sqlmodel import Field, Relationship, Session, SQLModel, create_engine


class Settings(BaseSettings):
    """Application settings."""

    SPOTIFY_CLIENT_ID: str = PydanticField(..., description="Spotify API client ID")
    SPOTIFY_CLIENT_SECRET: str = PydanticField(..., description="Spotify API client secret")
    SPOTIFY_ADMIN_USERNAME: str = PydanticField(..., description="Spotify admin user ID")
    PUBLIC_PLAYLIST_ID: str = PydanticField("", description="Current public playlist ID")
    SECRET_KEY: str = PydanticField(default_factory=lambda: os.urandom(24).hex())
    BASE_URL: str = "http://127.0.0.1:4884"
    DATABASE_URL: str = "sqlite:///pyjams.db"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()


class UserRole(str, Enum):
    GUEST = "guest"
    USER = "user"
    ADMIN = "admin"


class User(SQLModel, table=True):
    """Replaces the Admin model with expanded user management."""

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


class PlaylistManager(SQLModel, table=True):
    """Model for users who can manage a featured playlist."""

    id: int | None = Field(default=None, primary_key=True)
    playlist_id: int = Field(foreign_key="featuredplaylist.id")
    user_id: int = Field(foreign_key="user.id")
    added_at: datetime = Field(default_factory=datetime.utcnow)
    is_active: bool = Field(default=True)
    permissions: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))

    # Relationships
    playlist: FeaturedPlaylist = Relationship(back_populates="managers")
    manager: User = Relationship(back_populates="managed_playlists")


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
