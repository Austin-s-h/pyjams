from functools import wraps

from django.shortcuts import redirect
from spotipy.exceptions import SpotifyException

from .messages import error
from .spotify import TokenError

def spotify_error_handler(view_func):
    """Handle common Spotify API errors in Django views."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        try:
            return view_func(request, *args, **kwargs)
        except TokenError as te:
            error(request, te.message)
            if te.should_logout:
                request.session.flush()
                return redirect('pyjams:index')
            return redirect(request.META.get('HTTP_REFERER', 'pyjams:index'))
        except SpotifyException as e:
            error(request, str(e))
            return redirect(request.META.get('HTTP_REFERER', 'pyjams:index'))
        except Exception as e:
            print(f"Unexpected error in {view_func.__name__}: {e}")
            error(request, "An unexpected error occurred. Please try again.")
            return redirect('pyjams:index')
    return wrapper
