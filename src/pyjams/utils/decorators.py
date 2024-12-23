from collections.abc import Callable


def spotify_error_handler(func: Callable) -> Callable:
    """Handle common Spotify API errors."""
    # ...existing code...
