from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import Request
from fastapi.templating import Jinja2Templates
from starlette.templating import _TemplateResponse

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
templates_dir = BASE_DIR / "src" / "pyjams" / "templates"
templates = Jinja2Templates(directory=str(templates_dir))


def static_url(path: str) -> str:
    """Generate URL for static assets."""
    # ...existing code...


def url_for(name: str, **params: dict) -> str:
    """Enhanced URL generator supporting both routes and static files."""
    # ...existing code...


def flash(request: Request, message: str, category: str = "info") -> None:
    """Add a flash message to the session."""
    # ...existing code...


def get_flashed_messages(request: Request, with_categories: bool = False) -> list[tuple[str, str]] | list[str]:
    """Get and clear flash messages from session."""
    # ...existing code...


def render_template(template_name: str, context: dict[str, Any]) -> _TemplateResponse:
    """Render template with common context data."""
    # ...existing code...


# Initialize template globals
templates.env.globals.update(
    {
        "url_for": url_for,
        "static_url": static_url,
        "current_year": lambda: datetime.now().year,
    }
)
