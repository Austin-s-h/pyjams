from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

from pyjams.models import FeaturedPlaylist, PlaylistManager, get_session
from pyjams.spotify import get_playlist_info, get_spotify
from pyjams.utils.decorators import spotify_error_handler
from pyjams.utils.templates import render_template

router = APIRouter(prefix="/playlists")


@router.get("/{playlist_id}", response_class=HTMLResponse)
@spotify_error_handler
async def playlist_details(playlist_id: str, request: Request):
    """Show playlist details."""
    spotify = await get_spotify(request.session)
    current_user = spotify.current_user()

    async with get_session() as session:
        public_playlist = await session.get(FeaturedPlaylist, playlist_id)
        if not public_playlist:
            raise HTTPException(status_code=404, detail="Playlist not found")

        playlist, tracks = await get_playlist_info(spotify, playlist_id)

        # Get playlist managers
        managers = await PlaylistManager.get_active_managers(session, public_playlist.id)

        # Calculate stats
        total_ms = sum(item["track"]["duration_ms"] for item in tracks["items"] if item["track"])
        stats = {
            "followers": playlist["followers"]["total"],
            "track_count": len(tracks["items"]),
            "duration": f"{round(total_ms / (1000 * 60))} min",
        }

        return render_template(
            "playlist.html",
            {
                "request": request,
                "playlist": playlist,
                "tracks": tracks["items"],
                "current_user": current_user,
                "public_playlist": public_playlist,
                "playlist_managers": managers,
                "is_manager": any(m.user_id == current_user["id"] for m in managers),
                "stats": stats,
            },
        )
