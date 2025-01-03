import logging
from collections.abc import Callable

from django.contrib import messages
from django.core.exceptions import SuspiciousOperation
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.urls import reverse

from pyjams.utils.spotify import SpotifySessionManager, TokenError

logger = logging.getLogger(__name__)


class SpotifySessionMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        # Skip auth paths to prevent redirect loops
        if request.path.startswith("/auth/spotify") or request.path.startswith("/callback"):
            return self.get_response(request)

        try:
            if request.user.is_authenticated:
                try:
                    manager = SpotifySessionManager(request.session)
                    token = manager.get_token()

                    if not token:
                        raise TokenError("No token found")

                    if manager.is_token_expired(token):
                        token = manager.refresh_token(token)
                        request.session.modified = True

                except (TokenError, SuspiciousOperation) as e:
                    logger.warning(f"Token error: {e!s}")
                    request.session.flush()
                    messages.warning(request, "Your Spotify session expired. Please log in again.")
                    return redirect(reverse("pyjams:spotify_login"))

            return self.get_response(request)

        except Exception as e:
            logger.error(f"Middleware error: {e!s}")
            request.session.flush()
            messages.error(request, "Session error occurred. Please try logging in again.")
            return redirect(reverse("pyjams:spotify_login"))
