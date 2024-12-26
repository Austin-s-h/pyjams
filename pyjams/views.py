from django.contrib import auth, messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, JsonResponse
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.views.decorators.http import require_http_methods

from pyjams.decorators import spotify_error_handler
from pyjams.models import FeaturedPlaylist, PlaylistManager
from pyjams.utils.messages import error, success
from pyjams.utils.spotify import get_playlist_info, get_spotify, get_spotify_auth


@spotify_error_handler
def index(request):
    """Render index page with login or search interface."""
    user = None
    playlists = []
    managed_playlists = []

    if request.user.is_authenticated:
        spotify = get_spotify(request.session)
        user = spotify.current_user()
        playlists = FeaturedPlaylist.objects.filter(is_active=True)
        
        # Get playlists managed by current user
        managed_playlists = [
            p for p in playlists 
            if PlaylistManager.objects.filter(
                playlist=p, 
                user_id=user['id'], 
                is_active=True
            ).exists()
        ]

    context = {
        "user": user,
        "playlists": playlists,
        "managed_playlists": managed_playlists,
    }
    if request.headers.get('HX-Request'):
        # Return just the content for HTMX requests
        return render(request, "components/playlist_list.html", context)
    return render(request, "index.html", context)

@spotify_error_handler
@login_required
def playlist_details(request, playlist_id):
    spotify = get_spotify(request.session)
    current_user = spotify.current_user()
    
    playlist, tracks = get_playlist_info(spotify, playlist_id)
    public_playlist = FeaturedPlaylist.objects.get(spotify_id=playlist_id)
    
    managers = PlaylistManager.get_active_managers(public_playlist.id)
    
    total_ms = sum(item["track"]["duration_ms"] for item in tracks["items"] if item["track"])
    stats = {
        "followers": playlist["followers"]["total"],
        "track_count": len(tracks["items"]),
        "duration": f"{round(total_ms / (1000 * 60))} min",
    }
    
    return render(
        request,
        "playlist.html",
        {
            "playlist": playlist,
            "tracks": tracks["items"],
            "current_user": current_user,
            "public_playlist": public_playlist,
            "playlist_managers": managers,
            "is_manager": any(m.user_id == current_user["id"] for m in managers),
            "stats": stats,
        },
    )

@spotify_error_handler
@login_required
def get_playlists(request):
    """Get all playlists for the authenticated user."""
    spotify = get_spotify(request.session)
    playlists = spotify.current_user_playlists()
    return JsonResponse({"playlists": playlists["items"]})

@spotify_error_handler
@login_required 
def get_playlist(request, playlist_id):
    """Get a specific playlist by ID."""
    try:
        spotify = get_spotify(request.session)
        playlist = spotify.playlist(playlist_id)
        return JsonResponse(playlist)
    except Exception as e:
        raise Http404(f"Playlist not found: {e!s}")

@spotify_error_handler
@login_required
@require_http_methods(["POST"])
def create_playlist(request):
    """Create a new playlist."""
    spotify = get_spotify(request.session)
    name = request.POST.get('name')
    description = request.POST.get('description', '')
    
    if not name:
        return JsonResponse({"error": "Name is required"}, status=400)
        
    try:
        user_id = spotify.current_user()["id"]
        playlist = spotify.user_playlist_create(
            user_id,
            name,
            public=True,
            description=description
        )
        success(request, "Playlist created successfully!")
        return JsonResponse({"playlist": playlist})
    except Exception as e:
        error(request, f"Failed to create playlist: {e!s}")
        return JsonResponse({"error": str(e)}, status=400)

@spotify_error_handler
@login_required
@require_http_methods(["POST"])
def add_track(request):
    """Add a track to a playlist."""
    spotify = get_spotify(request.session)
    track_id = request.POST.get('track_id')
    playlist_id = request.POST.get('playlist_id')
    
    if not all([track_id, playlist_id]):
        return JsonResponse({"error": "Missing required parameters"}, status=400)
        
    try:
        spotify.playlist_add_items(playlist_id, [track_id])
        success(request, "Track added successfully!")
        # Render updated track list
        playlist, tracks = get_playlist_info(spotify, playlist_id)
        html = render_to_string(
            "components/track_list.html",
            {"tracks": tracks["items"], "is_manager": True},
            request=request
        )
        return JsonResponse({
            "message": "Track added successfully",
            "html": html
        })
    except Exception as e:
        error(request, f"Failed to add track: {e!s}")
        return JsonResponse({"error": str(e)}, status=400)

@spotify_error_handler
@login_required
@require_http_methods(["POST"])
def remove_track(request):
    """Remove a track from a playlist."""
    spotify = get_spotify(request.session)
    track_id = request.POST.get('track_id')
    playlist_id = request.POST.get('playlist_id')
    
    if not all([track_id, playlist_id]):
        return JsonResponse({"error": "Missing required parameters"}, status=400)
        
    try:
        spotify.playlist_remove_all_occurrences_of_items(playlist_id, [track_id])
        success(request, "Track removed successfully!")
        return JsonResponse({"message": "Track removed successfully"})
    except Exception as e:
        error(request, f"Failed to remove track: {e!s}")
        return JsonResponse({"error": str(e)}, status=400)

@spotify_error_handler
@require_http_methods(["GET"])
def search_tracks(request):
    q = request.GET.get('q', '')
    if len(q) < 2:
        return render(request, "components/search_results.html", {"tracks": []})

    spotify = get_spotify(request.session)
    results = spotify.search(q=q, type="track", limit=5)
    
    tracks = [
        {
            "id": track["id"],
            "name": track["name"],
            "artists": [artist["name"] for artist in track["artists"]],
            "album": {
                "name": track["album"]["name"],
                "image": track["album"]["images"][0]["url"] if track["album"]["images"] else None,
            },
            "duration_ms": track["duration_ms"],
            "preview_url": track.get("preview_url"),
        }
        for track in results["tracks"]["items"]
    ]
    
    if request.headers.get('HX-Request'):
        return render(request, "components/search_results.html", {"tracks": tracks})
    return JsonResponse({"tracks": tracks})

def privacy(request):
    """Render privacy policy page."""
    return render(request, "privacy.html")

def terms(request):
    """Render terms of service page."""
    return render(request, "terms.html")

def logout(request):
    """Logout user and clear session."""
    if request.user.is_authenticated:
        auth.logout(request)
        messages.success(request, "You have been logged out.")
    request.session.clear()
    return redirect('pyjams:index')

def spotify_login(request):
    """Initiate Spotify OAuth flow"""      
    sp_oauth = get_spotify_auth(request)
    auth_url = sp_oauth.get_authorize_url()
    
    # Generate and store state parameter
    state = sp_oauth.state
    request.session['spotify_state'] = state
    
    # Store next URL in session if provided
    next_url = request.GET.get('next')
    if next_url:
        request.session['next'] = next_url
        
    return redirect(auth_url)

def spotify_callback(request):
    """Handle Spotify OAuth callback"""
    if error := request.GET.get('error'):
        messages.error(request, f"Spotify authorization failed: {error}", extra_tags='bg-danger text-white')
        return redirect('pyjams:index')
    
    state = request.GET.get('state')
    code = request.GET.get('code')
    
    if not code:
        messages.error(request, "No authorization code received")
        return redirect('pyjams:index')
        
    try:
        # Verify state parameter
        verify_spotify_state(request, state)
        
        sp_oauth = get_spotify_auth(request)
        token_info = sp_oauth.get_access_token(code)
        request.session['spotify_token'] = token_info
        
        # Authenticate with our custom backend
        user = auth.authenticate(request, access_token=token_info['access_token'])
        if user:
            auth.login(request, user)
            messages.success(request, f"Welcome {user.first_name}!", extra_tags='bg-success text-white')
            
            # Redirect to next URL if stored in session
            next_url = request.session.pop('next', None)
            if next_url:
                return redirect(next_url)
        else:
            messages.error(request, "Authentication failed")
            
    except TokenError as e:
        messages.error(request, str(e))
        if e.should_logout:
            return redirect('pyjams:logout')
    except Exception as e:
        messages.error(request, f"Authentication failed: {e!s}", extra_tags='bg-danger text-white')
        
    return redirect('pyjams:index')