from datetime import datetime
from pathlib import Path
from typing import Any, Protocol

from fastapi import Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.templating import _TemplateResponse

from pyjams.models import settings


class TemplateContext(Protocol):
    """Protocol for template context data."""

    request: Request
    settings: Any
    user: Any | None


def get_templates_dir() -> Path:
    """Get templates directory path."""
    base_dir = Path(__file__).resolve().parent.parent
    return base_dir / "templates"


# Initialize templates with proper path
templates = Jinja2Templates(directory=str(get_templates_dir()))

# Initialize static files
static = StaticFiles(directory=str(Path(settings.STATIC_ROOT)))


def url_for(name: str, **path_params: Any) -> str:
    """Generate URL for named endpoint."""
    # TODO: Implement proper URL generation
    return f"/{name}"


def static_url(path: str) -> str:
    """Generate URL for static asset."""
    return f"/static/{path}"


def flash(request: Request, message: str, category: str = "info") -> None:
    """Add a flash message to the session.

    Args:
        request: The current request
        message: The message to flash
        category: Message category (default: info)
    """
    if "flash_messages" not in request.session:
        request.session["flash_messages"] = []
    request.session["flash_messages"].append((category, message))


def get_flashed_messages(request: Request, with_categories: bool = False) -> list[tuple[str, str]] | list[str]:
    """Get and clear flash messages from session.

    Args:
        request: The current request
        with_categories: Include message categories in result

    Returns:
        List of messages or (category, message) tuples
    """
    messages = request.session.pop("flash_messages", [])
    return messages if with_categories else [msg for _, msg in messages]


def render_template(template_name: str, request: Request, **context: Any) -> _TemplateResponse:
    """Render template with common context data.

    Args:
        template_name: Name of template to render
        request: The current request
        **context: Additional template context

    Returns:
        Rendered template response
    """
    # Add common context data
    context.update(
        {
            "request": request,
            "settings": settings,
            "get_flashed_messages": lambda **kwargs: get_flashed_messages(request, **kwargs),
            "url_for": url_for,
            "static_url": static_url,
            "current_year": datetime.now().year,
        }
    )

    return templates.TemplateResponse(
        template_name, context, headers={"Cache-Control": "no-store"} if settings.DEBUG else None
    )


# Remove redundant globals since we pass them in context
# templates.env.globals.update({
#     "url_for": url_for,
#     "static_url": static_url,
#     "current_year": lambda: datetime.now().year,
# })
