from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, JSONResponse
from spotipy import Spotify, SpotifyException

from pyjams.app import spotify_error_handler
from pyjams.models import FeaturedPlaylist, Permission, PlaylistManager, get_session
from pyjams.routes.auth import require_admin, require_permissions
from pyjams.utils.templates import render_template

router = APIRouter(prefix="/admin")


@router.get("", response_class=HTMLResponse)
@spotify_error_handler
@require_permissions(Permission.ADMIN)
async def admin_panel(request: Request):
    """Render admin panel."""
    async with get_session() as session:
        # Get current featured playlist
        featured = await FeaturedPlaylist.get_current(session)

        # Get all playlists this user can access
        sp: Spotify = request.session["sp"]
        playlists = sp.current_user_playlists()["items"]

        return render_template("admin/panel.html", request=request, featured=featured, playlists=playlists)


@router.post("/playlists")
@spotify_error_handler
@require_permissions(Permission.ADMIN)
async def create_public_playlist(request: Request, playlist_id: str = Form(...), description: str | None = Form(None)):
    """Create a new public playlist."""
    async with get_session() as session:
        # Check if playlist exists
        sp: Spotify = request.session["sp"]
        try:
            playlist = sp.playlist(playlist_id)
        except SpotifyException:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Playlist not found")

        # Create new featured playlist
        featured = FeaturedPlaylist(
            spotify_id=playlist_id,
            name=playlist["name"],
            description=description or playlist["description"],
            image_url=playlist["images"][0]["url"] if playlist["images"] else None,
        )

        await featured.save(session)

        return JSONResponse({"message": "Public playlist created successfully", "playlist": featured.to_dict()})


@router.delete("/playlists/{playlist_id}")
@spotify_error_handler
@require_permissions(Permission.ADMIN)
async def delete_public_playlist(request: Request, playlist_id: int, current_user: dict = Depends(require_admin)):
    """Delete a public playlist."""
    async with get_session() as session:
        playlist = await FeaturedPlaylist.get_by_id(session, playlist_id)
        if not playlist:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Playlist not found")

        await playlist.delete(session)

        return JSONResponse({"message": "Public playlist deleted successfully"})


@router.post("/managers")
@router.delete("/managers/{manager_id}")
@spotify_error_handler
@require_permissions(Permission.ADMIN)
async def manage_playlist_managers(
    request: Request,
    manager_id: int | None = None,
    playlist_id: int | None = Form(None),
    user_id: str | None = Form(None),
    current_user: dict = Depends(require_admin),
):
    """Add or remove playlist managers."""
    async with get_session() as session:
        if request.method == "POST":
            # Verify playlist exists
            playlist = await FeaturedPlaylist.get_by_id(session, playlist_id)
            if not playlist:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Playlist not found")

            # Add manager
            manager = PlaylistManager(playlist_id=playlist_id, user_id=user_id)
            await manager.save(session)

            return JSONResponse({"message": "Manager added successfully", "manager": manager.to_dict()})

        elif request.method == "DELETE":
            manager = await PlaylistManager.get_by_id(session, manager_id)
            if not manager:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Manager not found")

            await manager.delete(session)

            return JSONResponse({"message": "Manager removed successfully"})
