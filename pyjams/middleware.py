import logging
from collections.abc import Callable

from django.core.exceptions import SuspiciousOperation
from django.db import transaction
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.urls import reverse

from pyjams.utils.spotify import SpotifySessionManager, TokenError

logger = logging.getLogger(__name__)


class SpotifySessionMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def _clear_session(self, request: HttpRequest) -> None:
        try:
            request.session.flush()
        except Exception:
            request.session.clear()

    def __call__(self, request: HttpRequest) -> HttpResponse:
        # Skip auth paths to prevent redirect loops
        if request.path.startswith("/auth/spotify") or request.path.startswith("/callback"):
            return self.get_response(request)

        try:
            if request.user.is_authenticated:
                manager = SpotifySessionManager(request.session)

                try:
                    token = manager.get_token()
                    if not token:
                        logger.warning("No token found in session")
                        self._clear_session(request)
                        return redirect(reverse("spotify:login"))

                    if manager.is_token_expired(token):
                        # Ensure atomic token refresh
                        with transaction.atomic():
                            try:
                                token = manager.refresh_token(token)
                                request.session.modified = True
                                request.session.save()
                            except Exception as e:
                                logger.error(f"Token refresh failed: {e!s}")
                                self._clear_session(request)
                                return redirect(reverse("spotify:login"))

                except (TokenError, SuspiciousOperation) as e:
                    logger.warning(f"Session error: {e!s}")
                    self._clear_session(request)
                    return redirect(reverse("spotify:login"))

            return self.get_response(request)

        except Exception as e:
            logger.error(f"Middleware error: {e!s}", exc_info=True)
            self._clear_session(request)
            return redirect(reverse("spotify:login"))
