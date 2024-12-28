from django.shortcuts import redirect
from django.urls import reverse

from pyjams.utils.spotify import SpotifySessionManager, TokenError


class SpotifySessionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            try:
                manager = SpotifySessionManager(request.session)
                token = manager.get_token()

                if token and manager.is_token_expired(token):
                    manager.refresh_token(token)

            except TokenError:
                # Clear session on token error
                request.session.flush()
                return redirect(reverse("pyjams:spotify_login"))

        response = self.get_response(request)
        return response
