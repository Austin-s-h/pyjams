from django.contrib import messages
from django.http import HttpRequest


def add_message(request: HttpRequest, level: int, message: str, extra_tags: str = "") -> None:
    """Add a message to the messages framework with optional extra tags."""
    messages.add_message(request, level, message, extra_tags=extra_tags)


def error(request: HttpRequest, message: str, extra_tags: str = "") -> None:
    """Add an error message."""
    add_message(request, messages.ERROR, message, extra_tags)


def success(request: HttpRequest, message: str, extra_tags: str = "") -> None:
    """Add a success message."""
    add_message(request, messages.SUCCESS, message, extra_tags)


def info(request: HttpRequest, message: str, extra_tags: str = "") -> None:
    """Add an info message."""
    add_message(request, messages.INFO, message, extra_tags)


def warning(request: HttpRequest, message: str, extra_tags: str = "") -> None:
    """Add a warning message."""
    add_message(request, messages.WARNING, message, extra_tags)
