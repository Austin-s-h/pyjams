from datetime import datetime
from pathlib import Path
from typing import Any

from django.conf import settings
from django.http import HttpRequest
from django.shortcuts import render
from django.template.response import TemplateResponse


def get_templates_dir() -> Path:
    """Get templates directory path."""
    return Path(settings.BASE_DIR) / "pyjams" / "templates"


def render_template(request: HttpRequest, template_name: str, context: dict[str, Any] = None) -> TemplateResponse:
    """Render template with common context data."""
    context = context or {}
    
    # Add common context data
    context.update({
        'request': request,
        'settings': settings,
        'current_year': datetime.now().year,
    })

    return render(
        request=request,
        template_name=template_name,
        context=context,
    )
