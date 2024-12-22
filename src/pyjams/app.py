from collections.abc import Callable
from datetime import datetime
from functools import wraps
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from spotipy import Spotify
from spotipy.exceptions import SpotifyException
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import JSONResponse
from starlette.templating import _TemplateResponse

from pyjams.models import (
    Admin,
    PlaylistManager,
    PublicPlaylist,
    SQLModel,
    TokenError,
    engine,
    get_session,
    get_spotify,
    init_spotify_oauth,
    settings,
)

# Configuration
BASE_DIR = Path(__file__).resolve().parent
app = FastAPI(
    title="PyJams",
    description="A collaborative playlist manager for Spotify",
    version="1.0.0",
)

# Static files and templates setup
static_dir = BASE_DIR / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

# Update the url_for function in globals
templates.env.globals.update(
    {
        "url_for": lambda name, **params: (
            app.url_path_for(name, **params) if not name.startswith(("css/", "js/", "images/")) else f"/static/{name}"
        ),
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


def render_template(template_name: str, context: dict[str, Any]) -> _TemplateResponse:
    """Render template with common context data."""
    context.update(
        {
            "settings": settings,
            "get_flashed_messages": lambda **kwargs: get_flashed_messages(context["request"], **kwargs),
        }
    )
    return templates.TemplateResponse(template_name, context)


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

    # Get public playlists
    session = next(get_session())
    public_playlists = session.query(PublicPlaylist).filter(PublicPlaylist.is_active == True).all()

    # Get managed playlist IDs for the current user
    managed_playlist_ids = set()
    if request.session.get("user_id"):
        managed_playlist_ids = {
            manager.playlist_id
            for manager in session.query(PlaylistManager)
            .filter(PlaylistManager.user_id == request.session["user_id"], PlaylistManager.is_active == True)
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


# Routes - Auth
@app.get("/auth")
@spotify_error_handler
async def auth(request: Request):
    """Initialize Spotify OAuth login flow."""
    oauth = init_spotify_oauth()

    if "token_info" in request.session:
        token_info = request.session["token_info"]
        if not oauth.is_token_expired(token_info):
            return RedirectResponse(url="/")

        try:
            token_info = oauth.refresh_access_token(token_info["refresh_token"])
            request.session["token_info"] = token_info
            return RedirectResponse(url="/")
        except Exception as e:
            print(f"Token refresh error: {e}")
            request.session.pop("token_info", None)

    return RedirectResponse(url=oauth.get_authorize_url())


@app.get("/callback")
async def callback(code: str, request: Request):
    """Handle Spotify OAuth callback."""
    try:
        if not code:
            return RedirectResponse(url="/")

        oauth = init_spotify_oauth()
        token_info = oauth.get_access_token(code, as_dict=True, check_cache=False)
        if not token_info:
            return RedirectResponse(url="/")

        # Store token info in session
        request.session.clear()  # Clear any existing session data
        request.session["token_info"] = token_info

        # Get and store user info
        spotify = Spotify(auth=token_info["access_token"])
        current_user = spotify.current_user()
        request.session["user_name"] = current_user["display_name"]
        request.session["user_id"] = current_user["id"]  # Store user ID

        # Set admin status if applicable
        if current_user["id"] == settings.SPOTIFY_ADMIN_USERNAME:
            request.session["admin"] = True
            session = next(get_session())
            # Check if admin already exists
            admin = session.query(Admin).filter(Admin.spotify_id == current_user["id"]).first()
            if not admin:
                admin = Admin(spotify_id=current_user["id"], name=current_user["display_name"])
                session.add(admin)
                session.commit()

        return RedirectResponse(url="/")
    except Exception as e:
        print(f"Callback error: {e}")  # Add logging
        request.session.clear()
        return RedirectResponse(url="/")


# Routes - Admin
@app.get("/admin")
@spotify_error_handler
async def admin_panel(request: Request):
    """Render admin panel."""
    # Check if user is admin
    if not request.session.get("admin"):
        raise HTTPException(status_code=403, detail="Not authorized")

    spotify = await get_spotify(request.session)
    current_user = spotify.current_user()

    # Get user's playlists from Spotify
    playlists = spotify.user_playlists(current_user["id"])["items"]

    # Get managed public playlists from database
    session = next(get_session())
    managed_playlists = (
        session.query(PublicPlaylist)
        .join(PlaylistManager)
        .filter(PlaylistManager.user_id == current_user["id"])
        .filter(PublicPlaylist.is_active == True)
        .all()
    )

    return render_template(
        "admin.html",
        {
            "request": request,
            "playlists": playlists,
            "managed_playlists": managed_playlists,
        },
    )


@app.post("/admin/create_public_playlist")
@spotify_error_handler
async def create_public_playlist(
    request: Request,
    playlist_id: str = Form(...),
    description: str = Form(None),
):
    """Create a new public playlist."""
    spotify = await get_spotify(request.session)
    current_user = spotify.current_user()

    # Verify playlist exists and user has access
    try:
        playlist = spotify.playlist(playlist_id)
    except SpotifyException:
        raise HTTPException(status_code=404, detail="Playlist not found")

    session = next(get_session())

    # Create public playlist entry
    public_playlist = PublicPlaylist(
        spotify_id=playlist_id,
        name=playlist["name"],
        description=description,
        created_by_id=current_user["id"],
    )
    session.add(public_playlist)
    session.flush()  # Get the ID before committing

    # Add creator as manager
    manager = PlaylistManager(
        playlist_id=public_playlist.id,
        user_id=current_user["id"],
    )
    session.add(manager)
    session.commit()

    return {
        "message": f'Created public playlist "{playlist["name"]}"',
        "playlist": {
            "id": public_playlist.id,
            "spotify_id": playlist_id,
            "name": playlist["name"],
        },
    }


@app.post("/admin/add_manager")
@spotify_error_handler
async def add_playlist_manager(
    request: Request,
    playlist_id: int = Form(...),
    user_id: str = Form(...),
):
    """Add a manager to a public playlist."""
    spotify = await get_spotify(request.session)
    current_user = spotify.current_user()

    session = next(get_session())
    playlist = session.get(PublicPlaylist, playlist_id)

    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")

    # Verify requester is a manager
    is_manager = (
        session.query(PlaylistManager)
        .filter(
            PlaylistManager.playlist_id == playlist_id,
            PlaylistManager.user_id == current_user["id"],
            PlaylistManager.is_active == True,
        )
        .first()
    )

    if not is_manager:
        raise HTTPException(status_code=403, detail="Not authorized to manage this playlist")

    # Add new manager
    manager = PlaylistManager(
        playlist_id=playlist_id,
        user_id=user_id,
    )
    session.add(manager)
    session.commit()

    return {"message": "Added manager to playlist"}


# Routes - Playlist
@app.get("/playlist/{playlist_id}")
@spotify_error_handler
async def playlist_details(playlist_id: str, request: Request):
    """Show playlist details."""
    spotify = await get_spotify(request.session)
    current_user = spotify.current_user()

    session = next(get_session())
    public_playlist = session.query(PublicPlaylist).filter(PublicPlaylist.spotify_id == playlist_id).first()

    if not public_playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")

    playlist, tracks = await get_playlist_info(spotify, playlist_id)

    # Get playlist managers
    playlist_managers = (
        session.query(PlaylistManager)
        .filter(PlaylistManager.playlist_id == public_playlist.id, PlaylistManager.is_active == True)
        .order_by(PlaylistManager.added_at.desc())
        .all()
    )

    # Calculate stats
    total_ms = sum(item["track"]["duration_ms"] for item in tracks["items"] if item["track"])
    total_minutes = round(total_ms / (1000 * 60))

    stats = {
        "followers": playlist["followers"]["total"],
        "track_count": len(tracks["items"]),
        "duration": f"{total_minutes} min",
    }

    # Check if user is a manager
    is_manager = any(manager.user_id == current_user["id"] for manager in playlist_managers)

    return render_template(
        "playlist.html",
        {
            "request": request,
            "playlist": playlist,
            "tracks": tracks["items"],
            "current_user": current_user,
            "public_playlist": public_playlist,
            "playlist_managers": playlist_managers,
            "is_manager": is_manager,
            "stats": stats,
        },
    )


# Routes - API
@app.get("/api/search_tracks")
@spotify_error_handler
async def search_tracks(q: str, request: Request):
    """Search for tracks."""
    if len(q) < 2:
        return {"tracks": []}

    spotify = await get_spotify(request.session)
    results = spotify.search(q=q, type="track", limit=5)
    if not results or not results["tracks"]["items"]:
        return {"tracks": []}

    return {
        "tracks": [
            {
                "id": track["id"],
                "name": track["name"],
                "artists": [artist["name"] for artist in track["artists"]],
                "album": {
                    "name": track["album"]["name"],
                    "image": track["album"]["images"][0]["url"] if track["album"]["images"] else None,
                },
                "duration_ms": track["duration_ms"],
            }
            for track in results["tracks"]["items"]
        ]
    }


@app.post("/add_song")
@spotify_error_handler
async def add_song(request: Request, track_id: str = Form(...)):
    """Add a song to the playlist."""
    spotify = await get_spotify(request.session)
    if not settings.PUBLIC_PLAYLIST_ID:
        flash(request, "No public playlist configured", "error")
        raise HTTPException(status_code=400, detail="No public playlist configured")

    track = spotify.track(track_id)
    playlist = spotify.playlist(settings.PUBLIC_PLAYLIST_ID)

    existing_tracks = spotify.playlist_tracks(settings.PUBLIC_PLAYLIST_ID)
    if any(item["track"]["id"] == track_id for item in existing_tracks["items"]):
        return JSONResponse(status_code=409, content={"message": f'"{track["name"]}" is already in the playlist'})

    spotify.playlist_add_items(settings.PUBLIC_PLAYLIST_ID, [track_id])
    return {
        "message": f'Added "{track["name"]}" to {playlist["name"]}',
        "track": {
            "name": track["name"],
            "artist": track["artists"][0]["name"],
            "album": track["album"]["name"],
            "image": track["album"]["images"][0]["url"] if track["album"]["images"] else None,
        },
    }


@app.post("/remove_song")
@spotify_error_handler
async def remove_song(request: Request, track_id: str = Form(...), playlist_id: str | None = Form(None)):
    """Remove a song from the playlist."""
    spotify = await get_spotify(request.session)
    playlist_id = playlist_id or settings.PUBLIC_PLAYLIST_ID
    if not playlist_id:
        raise HTTPException(status_code=400, detail="No playlist specified")

    track = spotify.track(track_id)
    spotify.playlist_remove_all_occurrences_of_items(playlist_id, [track_id])

    return {"message": f'Removed "{track["name"]}" from the playlist', "track_id": track_id}


@app.get("/api/playlist_stats/{playlist_id}")
@spotify_error_handler
async def playlist_stats(playlist_id: str, request: Request):
    """Get playlist statistics."""
    spotify = await get_spotify(request.session)
    playlist, tracks = await get_playlist_info(spotify, playlist_id)

    total_ms = sum(item["track"]["duration_ms"] for item in tracks["items"] if item["track"])
    total_minutes = round(total_ms / (1000 * 60))

    return {
        "followers": playlist["followers"]["total"],
        "track_count": playlist["tracks"]["total"],
        "duration": f"{total_minutes} min",
    }


@app.get("/api/suggestions")
@spotify_error_handler
async def get_suggestions(request: Request):
    """Get track suggestions."""
    spotify = await get_spotify(request.session)

    if not settings.PUBLIC_PLAYLIST_ID:
        # Return popular tracks if no public playlist
        recommendations = spotify.recommendations(limit=6, seed_genres=["pop"])
    else:
        # Get recommendations based on current playlist tracks
        playlist_tracks = spotify.playlist_tracks(settings.PUBLIC_PLAYLIST_ID)
        seed_tracks = [item["track"]["id"] for item in playlist_tracks["items"][:5]]

        recommendations = spotify.recommendations(limit=6, seed_tracks=seed_tracks, min_popularity=30)

    return {
        "tracks": [
            {
                "id": track["id"],
                "name": track["name"],
                "artists": [artist["name"] for artist in track["artists"]],
                "album": {
                    "name": track["album"]["name"],
                    "image": track["album"]["images"][0]["url"] if track["album"]["images"] else None,
                },
            }
            for track in recommendations["tracks"]
        ]
    }


# Routes - Static Pages
@app.get("/privacy")
async def privacy_policy(request: Request):
    """Render privacy policy page."""
    return render_template("privacy.html", {"request": request})
