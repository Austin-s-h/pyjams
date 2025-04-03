from typing import Any

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


def validate_permissions_schema(value: dict[str, Any]) -> None:
    """
    Validates the permissions schema for playlist managers.

    Expected schema:
    {
        "can_add_songs": bool,
        "can_remove_songs": bool,
        "can_invite_users": bool,
        "can_remove_users": bool,
        "can_edit_settings": bool
    }
    """

    required_permissions = {
        "can_add_songs": bool,
        "can_remove_songs": bool,
        "can_invite_users": bool,
        "can_remove_users": bool,
        "can_edit_settings": bool,
    }

    # Validate all required permissions exist
    missing_perms = set(required_permissions.keys()) - set(value.keys())
    if missing_perms:
        raise ValidationError(_("Missing required permissions: %(perms)s"), params={"perms": ", ".join(missing_perms)})

    # Validate permission types
    for perm_name, perm_value in value.items():
        if perm_name not in required_permissions:
            raise ValidationError(_("Unknown permission: %(perm)s"), params={"perm": perm_name})

        if not isinstance(perm_value, required_permissions[perm_name]):
            raise ValidationError(_("Permission '%(perm)s' must be a boolean"), params={"perm": perm_name})
