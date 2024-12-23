from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import JSONResponse
from spotipy import SpotifyException

from pyjams.app import spotify_error_handler
from pyjams.models import (
    FeaturedPlaylist,
    Permission,
    PlaylistManager,
    get_playlist_info,
    get_session,
    get_spotify,
)
from pyjams.routes.auth import require_permissions

router = APIRouter(prefix="/api")


# Playlist Management Routes
@router.get("/playlists")
@spotify_error_handler
@require_permissions(Permission.VIEW)
async def get_playlists(request: Request):
    """Get user's playlists."""
    spotify = await get_spotify(request.session)
    playlists = spotify.current_user_playlists()

    return {
        "playlists": [
            {
                "id": playlist["id"],
                "name": playlist["name"],
                "image": playlist["images"][0]["url"] if playlist["images"] else None,
                "tracks_total": playlist["tracks"]["total"],
            }
            for playlist in playlists["items"]
        ]
    }


@router.get("/playlists/{playlist_id}")
@spotify_error_handler
@require_permissions(Permission.VIEW)
async def get_playlist(playlist_id: str, request: Request):
    """Get details of a specific playlist."""
    spotify = await get_spotify(request.session)
    playlist, tracks = await get_playlist_info(spotify, playlist_id)

    return {
        "id": playlist["id"],
        "name": playlist["name"],
        "description": playlist.get("description", ""),
        "image": playlist["images"][0]["url"] if playlist["images"] else None,
        "tracks": [
            {
                "id": item["track"]["id"],
                "name": item["track"]["name"],
                "artists": [artist["name"] for artist in item["track"]["artists"]],
                "album": {
                    "name": item["track"]["album"]["name"],
                    "image": item["track"]["album"]["images"][0]["url"] if item["track"]["album"]["images"] else None,
                },
                "duration_ms": item["track"]["duration_ms"],
            }
            for item in tracks["items"]
            if item["track"]  # Filter out None tracks
        ],
    }


@router.post("/playlists/create")
@spotify_error_handler
@require_permissions(Permission.MANAGE_PLAYLIST)
async def create_playlist(
    request: Request, name: str = Form(...), description: str | None = Form(None), public: bool = Form(False)
):
    """Create a new playlist."""
    spotify = await get_spotify(request.session)
    user_id = spotify.current_user()["id"]

    playlist = spotify.user_playlist_create(user_id, name, public=public, description=description)

    return {"id": playlist["id"], "name": playlist["name"], "message": f"Created playlist '{name}'"}


# Track Management Routes
@router.post("/songs/add")
@spotify_error_handler
@require_permissions(Permission.ADD_SONGS)
async def add_track(request: Request, track_id: str = Form(...), playlist_id: str = Form(...)):
    """Add a track to the playlist."""
    spotify = await get_spotify(request.session)

    session = next(get_session())
    featured_playlist = (
        session.query(FeaturedPlaylist)
        .filter(FeaturedPlaylist.spotify_id == playlist_id, PlaylistManager.is_active)
        .first()
    )

    if not featured_playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")

    track = spotify.track(track_id)
    playlist = spotify.playlist(playlist_id)

    existing_tracks = spotify.playlist_tracks(playlist_id)
    if any(item["track"]["id"] == track_id for item in existing_tracks["items"]):
        return JSONResponse(status_code=409, content={"message": f'"{track["name"]}" is already in the playlist'})

    spotify.playlist_add_items(playlist_id, [track_id])
    return {
        "message": f'Added "{track["name"]}" to {playlist["name"]}',
        "track": {
            "name": track["name"],
            "artist": track["artists"][0]["name"],
            "album": track["album"]["name"],
            "image": track["album"]["images"][0]["url"] if track["album"]["images"] else None,
        },
    }


@router.post("/songs/remove")
@spotify_error_handler
@require_permissions(Permission.REMOVE_SONGS)
async def remove_track(request: Request, track_id: str = Form(...), playlist_id: str = Form(...)):
    """Remove a track from the playlist."""
    spotify = await get_spotify(request.session)
    if not playlist_id:
        raise HTTPException(status_code=400, detail="Playlist ID is required")

    track = spotify.track(track_id)
    spotify.playlist_remove_all_occurrences_of_items(playlist_id, [track_id])

    return {"message": f'Removed "{track["name"]}" from the playlist', "track_id": track_id}


# Featured Playlist Routes
@router.post("/featured_playlists")
@spotify_error_handler
@require_permissions(Permission.MANAGE_PLAYLIST)
async def manage_featured_playlists(request: Request, playlist_ids: list[str] = Form(...)):
    """Set featured playlists."""
    if not request.session.get("admin"):
        raise HTTPException(status_code=403, detail="Not authorized")

    spotify = await get_spotify(request.session)
    current_user = spotify.current_user()

    session = next(get_session())

    # Deactivate all current featured playlists
    session.query(FeaturedPlaylist).update({"is_active": False})

    for playlist_id in playlist_ids[:3]:  # Limit to 3 playlists
        try:
            playlist = spotify.playlist(playlist_id)
            featured = FeaturedPlaylist(
                spotify_id=playlist_id,
                name=playlist["name"],
                description=playlist.get("description"),
                created_by_id=current_user["id"],
            )
            session.add(featured)
        except SpotifyException:
            continue

    session.commit()
    return {"message": "Featured playlists updated"}


# Playlist Manager Routes
@router.post("/playlist/{playlist_id}/managers")
@spotify_error_handler
@require_permissions(Permission.MANAGE_USERS)
async def add_playlist_manager(
    request: Request, playlist_id: int, user_id: str = Form(...), permissions: dict = Form(default_factory=dict)
):
    """Add a manager to a playlist."""
    async with get_session() as session:
        playlist = await FeaturedPlaylist.get_by_id(session, playlist_id)
        if not playlist:
            raise HTTPException(status_code=404, detail="Playlist not found")

        manager = await playlist.add_manager(session, user_id, permissions)
        return {"message": "Manager added successfully", "manager": manager.to_dict()}


# Search Routes
@router.get("/search")
@spotify_error_handler
async def search_tracks(q: str, request: Request):
    """Search for tracks available to the user."""
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


# Playlist Stats Routes
@router.get("/playlist_stats/{playlist_id}")
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


# Suggestions Routes
@router.get("/suggestions")
@spotify_error_handler
async def get_suggestions(request: Request, playlist_id: str | None = None):
    """Get track suggestions."""
    spotify = await get_spotify(request.session)

    if not playlist_id:
        # Return popular tracks if no playlist selected
        recommendations = spotify.recommendations(limit=6, seed_genres=["pop"])
    else:
        # Get recommendations based on selected playlist tracks
        playlist_tracks = spotify.playlist_tracks(playlist_id)
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
