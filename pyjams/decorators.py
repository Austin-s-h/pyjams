from functools import wraps

from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from spotipy import SpotifyException


def spotify_error_handler(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        try:
            return view_func(request, *args, **kwargs)
        except SpotifyException as e:
            return JsonResponse({"error": str(e)}, status=400)
    return wrapper

def require_permissions(*permissions):
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                raise PermissionDenied("Authentication required")
            
            if not request.user.has_permissions(*permissions):
                raise PermissionDenied("Insufficient permissions")
                
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator
