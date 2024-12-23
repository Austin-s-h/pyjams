from collections.abc import Callable
from datetime import datetime
from functools import wraps
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from spotipy import Spotify
from spotipy.exceptions import SpotifyException
from starlette.middleware.sessions import SessionMiddleware
from whitenoise import WhiteNoise

from pyjams.models import (
    FeaturedPlaylist,
    PlaylistManager,
    SQLModel,
    TokenError,
    engine,
    get_session,
    get_spotify,
    settings,
)
from pyjams.routes import admin, api, auth, playlist
from pyjams.utils.templates import render_template

# Configuration
BASE_DIR = Path(__file__).resolve().parent.parent.parent
STATIC_ROOT = BASE_DIR / settings.STATIC_ROOT
STATIC_DIR = BASE_DIR / "src" / "pyjams" / "static"

app = FastAPI(
    title="PyJams",
    description="A collaborative playlist manager for Spotify",
    version="1.0.0",  # TODO: version from pyproject.toml function
    root_path=settings.BASE_URL,
)

app = WhiteNoise(app, root=STATIC_DIR, prefix="/static/")
templates_dir = BASE_DIR / "src" / "pyjams" / "templates"
templates = Jinja2Templates(directory=str(templates_dir))


# Update the url_for function to handle both development and production URLs
def static_url(path: str) -> str:
    """Generate URL for static assets."""
    return f"/static/{path.lstrip('/')}"


def url_for(name: str, **params: dict) -> str:
    """Enhanced URL generator supporting both routes and static files."""
    if isinstance(name, str) and name.startswith(("css/", "js/", "images/")):
        return static_url(name)
    return app.url_path_for(name, **params)


# Update template globals with both functions
templates.env.globals.update(
    {
        "url_for": url_for,
        "static_url": static_url,
        "current_year": lambda: datetime.now().year,
    }
)

# Initialize database
SQLModel.metadata.create_all(engine)

# Add session middleware
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SECRET_KEY,
    session_cookie="session",
)


# Helper Functions
def flash(request: Request, message: str, category: str = "info") -> None:
    """Add a flash message to the session."""
    if "flash_messages" not in request.session:
        request.session["flash_messages"] = []
    request.session["flash_messages"].append((category, message))


def get_flashed_messages(request: Request, with_categories: bool = False) -> list[tuple[str, str]] | list[str]:
    """Get and clear flash messages from session."""
    messages = request.session.pop("flash_messages", [])
    return messages if with_categories else [msg for _, msg in messages]


async def get_playlist_info(spotify: Spotify, playlist_id: str) -> tuple[dict, dict]:
    """Get playlist and its tracks."""
    playlist = spotify.playlist(playlist_id)
    tracks = spotify.playlist_tracks(playlist_id)
    return playlist, tracks


def spotify_error_handler(func: Callable) -> Callable:
    """Handle common Spotify API errors."""

    @wraps(func)
    async def wrapper(*args, **kwargs) -> Any:
        request = next((arg for arg in args if isinstance(arg, Request)), kwargs.get("request"))
        if not request:
            raise ValueError("Request object not found in arguments")

        try:
            return await func(*args, **kwargs)
        except TokenError as te:
            print(f"TokenError: {te}")
            request.session.clear()
            return render_template(
                "error.html",
                {
                    "request": request,
                    "title": "Session Expired",
                    "message": "Your session has expired. Please log in again.",
                    "back_url": "/",
                },
            )
        except SpotifyException as e:
            return render_template(
                "error.html",
                {
                    "request": request,
                    "title": "Spotify Error",
                    "message": str(e),
                    "back_url": request.headers.get("referer", "/"),
                },
            )
        except Exception as e:
            print(f"Error in {func.__name__}: {e}")
            return render_template(
                "error.html",
                {
                    "request": request,
                    "title": "Unexpected Error",
                    "message": "Something went wrong. Please try again.",
                    "back_url": request.headers.get("referer", "/"),
                },
            )

    return wrapper


# Middleware
@app.middleware("http")
async def add_template_context(request: Request, call_next) -> Any:
    """Add common context to all templates."""
    response = await call_next(request)
    if hasattr(response, "context"):
        response.context["request"] = request
        response.context["settings"] = settings
    return response


# Routes - Main
@app.get("/")
@spotify_error_handler
async def index(request: Request):
    """Render index page with login or search interface."""
    if "token_info" not in request.session:
        return render_template("login.html", {"request": request})

    spotify = await get_spotify(request.session)
    query = request.query_params.get("q", "")
    tracks = None

    # Get public playlists and enrich with Spotify data
    session = next(get_session())
    public_playlists = session.query(FeaturedPlaylist).filter(FeaturedPlaylist.is_active).all()

    # Get managed playlist IDs for the current user
    managed_playlist_ids = set()
    if request.session.get("user_id"):
        managed_playlist_ids = {
            manager.playlist_id
            for manager in session.query(PlaylistManager)
            .filter(PlaylistManager.user_id == request.session["user_id"], PlaylistManager.is_active)
            .all()
        }

    if query:
        results = spotify.search(q=query, type="track", limit=12)
        tracks = results["tracks"]["items"] if results else None

    return render_template(
        "index.html",
        {
            "request": request,
            "tracks": tracks,
            "query": query,
            "public_playlists": public_playlists,
            "managed_playlist_ids": managed_playlist_ids,
        },
    )


@app.get("/privacy")
@spotify_error_handler
async def privacy_policy(request: Request):
    """Render privacy policy page."""
    return render_template("privacy.html", {"request": request})


# Register route groups
app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(api.router)
app.include_router(playlist.router)
