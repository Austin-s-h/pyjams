from collections.abc import Callable
from functools import wraps

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordBearer
from starlette.status import HTTP_403_FORBIDDEN

from pyjams.models import Permission, User, get_spotify

router = APIRouter(prefix="/auth")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


async def get_current_user(request: Request) -> User:
    """Get current authenticated user."""
    user = request.session.get("user")
    if not user or not isinstance(user, User):
        raise HTTPException(status_code=403, detail="Not authenticated")
    return user


def require_permissions(*permissions: Permission):
    """Require specific permissions for route."""

    async def dependency(request: Request, user: User = Depends(get_current_user)):
        if not user.has_permissions(*permissions):
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user

    return dependency


def playlist_permission_required(permission_key: str) -> Callable:
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(request: Request, playlist_id: int, *args, **kwargs):
            user = request.session.get("user")
            if not user or not isinstance(user, User):
                raise HTTPException(status_code=403, detail="Authentication required")

            if not user.is_admin:
                manager = next(
                    (pm for pm in user.managed_playlists if pm.playlist_id == playlist_id and pm.is_active), None
                )
                if not manager or not manager.has_permission(permission_key):
                    raise HTTPException(status_code=HTTP_403_FORBIDDEN, detail="Insufficient playlist permissions")

            return await func(request, playlist_id, *args, **kwargs)

        return wrapper

    return decorator


def can_manage_featured_playlists(user: User) -> bool:
    return user.is_admin or any(pm.is_active for pm in user.managed_playlists)


@router.get("/me")
async def get_current_user(request: Request):
    """Get current user info."""
    spotify = await get_spotify(request.session)
    user = spotify.current_user()
    return {"user": user}


@router.post("/logout")
async def logout(request: Request):
    """Clear session data."""
    request.session.clear()
    return {"message": "Logged out successfully"}
