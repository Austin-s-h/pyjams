from django.contrib import auth
from django.shortcuts import redirect

from pyjams.utils.spotify import get_spotify_auth


class SpotifyTokenMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            token_info = request.session.get('spotify_token')
            if token_info:
                sp_oauth = get_spotify_auth()
                if sp_oauth.is_token_expired(token_info):
                    try:
                        token_info = sp_oauth.refresh_access_token(token_info['refresh_token'])
                        request.session['spotify_token'] = token_info
                    except Exception:
                        auth.logout(request)
                        return redirect('pyjams:spotify_login')

        response = self.get_response(request)
        return response
