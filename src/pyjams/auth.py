from collections.abc import Callable
from functools import wraps

from fastapi import HTTPException, Request
from starlette.status import HTTP_403_FORBIDDEN

from .models import Permission, User


def require_permissions(*permissions: Permission) -> Callable:
    """Decorator to check if user has required permissions."""

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(request: Request, *args, **kwargs):
            user = request.session.get("user")
            if not user or not isinstance(user, User):
                raise HTTPException(status_code=403, detail="Authentication required")

            if not user.has_permissions(*permissions):
                raise HTTPException(status_code=HTTP_403_FORBIDDEN, detail="You don't have the required permissions")

            return await func(request, *args, **kwargs)

        return wrapper

    return decorator


def playlist_permission_required(permission_key: str) -> Callable:
    """Decorator to check playlist-specific permissions."""

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
    """Check if user can manage featured playlists."""
    return user.is_admin or any(pm.is_active for pm in user.managed_playlists)
