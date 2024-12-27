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
    playlists = []
    managed_playlists = []

    if request.user.is_authenticated:
        try:
            spotify = get_spotify(request.session)
            playlists = FeaturedPlaylist.objects.filter(is_active=True)
            
            # Get playlists managed by current user
            managed_playlists = [
                p for p in playlists 
                if PlaylistManager.objects.filter(
                    playlist=p, 
                    user_id=request.user.spotify_id, 
                    is_active=True
                ).exists()
            ]
        except Exception as e:
            print(f"Error fetching Spotify data: {e}")
            
    context = {
        "playlists": playlists,
        "managed_playlists": managed_playlists,
    }
    
    if request.headers.get('HX-Request'):
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
    
    print("Generating new state parameter") # Debug logging
    state = sp_oauth.state
    print(f"State parameter generated: {state}") # Debug logging
    
    # Store state in session immediately
    request.session['spotify_state'] = state
    request.session.modified = True
    request.session.save()
    
    print(f"Stored state in session: {request.session.get('spotify_state')}") # Debug logging
    
    return redirect(auth_url)

def spotify_callback(request):
    """Handle Spotify OAuth callback"""
    print("Session contents:", dict(request.session)) # Debug logging
    
    error = request.GET.get('error')
    if error:
        messages.error(request, f"Spotify authorization failed: {error}")
        return redirect('pyjams:index')
    
    code = request.GET.get('code')
    state = request.GET.get('state')
    stored_state = request.session.get('spotify_state')
    
    # Debug logging
    print(f"Received state: {state}")
    print(f"Stored state: {stored_state}")
    
    if not code:
        messages.error(request, "No authorization code received")
        return redirect('pyjams:index')
    
    if not stored_state:
        messages.error(request, "No state found in session")
        return redirect('pyjams:index')
    
    if not state:
        messages.error(request, "No state received from Spotify")
        return redirect('pyjams:index')
        
    if state != stored_state:
        messages.error(request, "State mismatch - possible CSRF attack")
        return redirect('pyjams:index')

    try:
        sp_oauth = get_spotify_auth(request)
        token_info = sp_oauth.get_access_token(code, check_cache=False)
        
        # Store minimal token info
        request.session['spotify_token'] = {
            'access_token': token_info['access_token'],
            'refresh_token': token_info['refresh_token'],
            'expires_at': token_info['expires_at'],
            'scope': token_info['scope']
        }
        request.session.modified = True
        
        # Force session save
        request.session.save()
        
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
            
    except Exception as e:
        messages.error(request, f"Authentication failed: {e!s}", extra_tags='bg-danger text-white')
        return redirect('pyjams:logout')
        
    return redirect('pyjams:index')