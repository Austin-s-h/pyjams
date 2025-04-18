from enum import Enum, Flag, auto
from typing import Any, ClassVar, Optional, TypedDict

from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.core.validators import MinLengthValidator, URLValidator
from django.db import models
from django.db.models import Index
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


def validate_permissions_schema(value: dict[str, Any]) -> None:
    """Validates the permissions schema for playlist managers."""

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


class Permission(Flag):
    NONE = 0
    VIEW = auto()
    SEARCH = auto()
    SUGGEST = auto()
    VOTE = auto()
    ADD_SONGS = auto()
    REMOVE_SONGS = auto()
    MANAGE_PLAYLIST = auto()
    MANAGE_USERS = auto()
    MODERATE = auto()
    ADMIN = auto()
    CREATE_FEATURED = auto()  # New permission for creating community featured playlists
    MANAGE_FEATURED = auto()  # New permission for managing site-wide featured playlist

    BASIC = VIEW | SEARCH
    CONTRIBUTOR = BASIC | SUGGEST | VOTE | CREATE_FEATURED
    MANAGER = CONTRIBUTOR | ADD_SONGS | REMOVE_SONGS | MANAGE_PLAYLIST
    MODERATOR = MANAGER | MODERATE | MANAGE_FEATURED
    ALL = ~NONE


class UserRole(str, Enum):
    GUEST = "guest"
    USER = "user"
    MANAGER = "manager"
    MODERATOR = "moderator"
    ADMIN = "admin"

    @property
    def permissions(self) -> Permission:
        return {
            self.GUEST: Permission.BASIC,
            self.USER: Permission.CONTRIBUTOR,
            self.MANAGER: Permission.MANAGER,
            self.MODERATOR: Permission.MODERATOR,
            self.ADMIN: Permission.ALL,
        }[self]


class User(AbstractUser):
    """
    Unified user model with minimal Spotify information
    """

    # Only essential Spotify fields
    spotify_id = models.CharField(
        max_length=64, unique=True, null=True, blank=True, db_index=True, validators=[MinLengthValidator(10)]
    )
    spotify_email = models.EmailField(
        null=True,
        blank=True,
        db_index=True,  # Add index for email lookups
    )
    spotify_display_name = models.CharField(max_length=255, null=True, blank=True)
    spotify_username = models.CharField(max_length=64, null=True, blank=True, db_index=True)

    # Role management
    role = models.CharField(
        max_length=20,
        choices=[(role.value, role.name) for role in UserRole],
        default=UserRole.USER.value,
    )

    class Meta:
        swappable = "AUTH_USER_MODEL"
        db_table = "pyjams_user"
        indexes: ClassVar[list[Index]] = [Index(fields=["role", "is_active"]), Index(fields=["date_joined"])]

    def has_permission(self, permission: Permission) -> bool:
        return bool(UserRole(self.role).permissions & permission)

    def has_permissions(self, *permissions: Permission) -> bool:
        required = Permission.NONE
        for permission in permissions:
            required |= permission
        return bool(UserRole(self.role).permissions & required == required)

    @property
    def is_admin(self) -> bool:
        return self.role == UserRole.ADMIN.value

    @property
    def is_moderator(self) -> bool:
        return self.role in (UserRole.MODERATOR.value, UserRole.ADMIN.value)

    @property
    def is_guest(self) -> bool:
        return self.role == UserRole.GUEST.value

    @property
    def display_name(self) -> str:
        """Returns spotify_display_name if available, otherwise username"""
        return self.spotify_display_name or self.username

    @classmethod
    def get_by_spotify_id(cls, spotify_id: str) -> Optional["User"]:
        return cls.objects.filter(spotify_id=spotify_id).first()


class BaseModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        abstract = True
        ordering: ClassVar[list[str]] = ["-created_at"]


class PermissionsDict(TypedDict):
    can_add_songs: bool
    can_remove_songs: bool
    can_invite_users: bool
    can_remove_users: bool
    can_edit_settings: bool


class FeaturedPlaylist(BaseModel):
    FEATURED_TYPES: ClassVar[list[tuple[str, str]]] = [
        ("site", "Site Featured"),
        ("community", "Community Featured"),
    ]

    spotify_id = models.CharField(max_length=64, unique=True, db_index=True, validators=[MinLengthValidator(10)])
    name = models.CharField(max_length=255, validators=[MinLengthValidator(1)])
    featured_type = models.CharField(max_length=20, choices=FEATURED_TYPES, default="community")
    description = models.TextField(max_length=1000, null=True, blank=True)
    image_url = models.URLField(null=True, blank=True, validators=[URLValidator()])
    creator = models.ForeignKey(User, on_delete=models.PROTECT, related_name="featured_playlists")
    contribution_rules = models.JSONField(default=dict)
    managers = models.ManyToManyField(User, through="PlaylistManager", related_name="managed_featured_playlists")
    featured_date = models.DateTimeField(default=timezone.now)
    unfeatured_date = models.DateTimeField(null=True, blank=True)

    class Meta(BaseModel.Meta):
        constraints: ClassVar[list[models.UniqueConstraint]] = [
            models.UniqueConstraint(
                fields=["featured_type"],
                condition=models.Q(featured_type="site", is_active=True),
                name="unique_active_site_featured",
            )
        ]
        ordering: ClassVar[list[str]] = ["-featured_date"]
        indexes: ClassVar[list[Index]] = [
            Index(fields=["featured_type", "is_active"]),
            Index(fields=["creator", "featured_type"]),
        ]
        permissions: ClassVar[list[tuple[str, str]]] = [
            ("can_feature_site", _("Can feature site playlists")),
            ("can_feature_community", _("Can feature community playlists")),
        ]

    def get_display_name(self) -> str:
        """Returns formatted display name for the playlist."""
        return self.name.strip() or "Untitled Playlist"

    def get_feature_status(self) -> str:
        """Returns human readable feature status."""
        if not self.is_active:
            return "Unfeatured"
        return "Site Featured" if self.is_site_featured else "Community Featured"

    def __str__(self) -> str:
        """Returns string representation of the playlist."""
        return f"{self.get_display_name()} ({self.get_feature_status()})"

    def clean(self) -> None:
        """Validate playlist type and status."""
        super().clean()
        if self.featured_type == "site" and self.is_active:
            # Check if another site featured playlist exists
            existing = FeaturedPlaylist.objects.filter(featured_type="site", is_active=True).exclude(pk=self.pk)
            if existing.exists():
                raise ValidationError("Only one active site featured playlist allowed")

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Custom save to handle validation and status changes."""
        self.clean()
        if not self.is_active and not self.unfeatured_date:
            self.unfeatured_date = timezone.now()
        super().save(*args, **kwargs)

    @property
    def is_site_featured(self) -> bool:
        """Check if this is the site featured playlist."""
        return self.featured_type == "site" and self.is_active

    @property
    def is_community_featured(self) -> bool:
        """Check if this is a community featured playlist."""
        return self.featured_type == "community" and self.is_active

    @classmethod
    def get_site_featured(cls) -> Optional["FeaturedPlaylist"]:
        """Get the current site featured playlist."""
        return cls.objects.filter(featured_type="site", is_active=True).first()

    @classmethod
    def get_community_featured(cls) -> models.QuerySet["FeaturedPlaylist"]:
        """Get all active community featured playlists."""
        return cls.objects.filter(featured_type="community", is_active=True).select_related("creator")

    @classmethod
    def user_has_featured(cls, user: User) -> bool:
        """Check if user already has a featured community playlist."""
        return cls.objects.filter(creator=user, featured_type="community", is_active=True).exists()

    @classmethod
    def set_site_featured(
        cls, spotify_id: str, name: str, description: str | None, image_url: str | None, creator: User
    ) -> "FeaturedPlaylist":
        """Set a new site-wide featured playlist."""
        # Deactivate current site featured playlist
        cls.objects.filter(featured_type="site", is_active=True).update(is_active=False, unfeatured_date=timezone.now())

        # Create new site featured playlist
        return cls.objects.create(
            spotify_id=spotify_id,
            name=name,
            description=description,
            image_url=image_url,
            featured_type="site",
            creator=creator,
            is_active=True,
            featured_date=timezone.now(),
        )

    @classmethod
    def get_previous_site_featured(cls) -> models.QuerySet[Any]:
        """Get previous site featured playlists."""
        return cls.objects.filter(featured_type="site", is_active=False).order_by("-unfeatured_date")

    def unfeature_site_playlist(self) -> None:
        """Unfeature the current site playlist."""
        if self.featured_type == "site" and self.is_active:
            self.is_active = False
            self.unfeatured_date = timezone.now()
            self.save()
        else:
            raise ValidationError("This is not an active site featured playlist")


class PlaylistManager(BaseModel):
    playlist = models.ForeignKey(FeaturedPlaylist, on_delete=models.CASCADE, related_name="managers_through")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="managed_playlists")
    permissions = models.JSONField(
        default=dict,
        validators=[validate_permissions_schema],
    )

    class Meta(BaseModel.Meta):
        unique_together: ClassVar[tuple[str, ...]] = ("playlist", "user")
        indexes: ClassVar[list[Index]] = [Index(fields=["playlist", "user", "is_active"])]

    def __str__(self) -> str:
        return f"{self.user.display_name} - {self.playlist.name}"  # Using display_name instead of name

    def has_permission(self, permission_key: str) -> bool:
        return self.permissions.get(permission_key, False)

    @classmethod
    def get_active_managers(cls, playlist_id: int) -> models.QuerySet[Any]:
        return cls.objects.filter(playlist_id=playlist_id, is_active=True).select_related("playlist")

    @classmethod
    def add_manager(cls, playlist_id: int, user_id: str) -> tuple[bool, str]:
        try:
            manager, created = cls.objects.get_or_create(
                playlist_id=playlist_id, user_id=user_id, defaults={"is_active": True}
            )
            if not created and not manager.is_active:
                manager.is_active = True
                manager.save()
                return True, "Manager reactivated successfully"
            return created, "Manager added successfully"
        except Exception as e:
            return False, str(e)

    @classmethod
    def remove_manager(cls, playlist_id: int, user_id: str) -> tuple[bool, str]:
        try:
            manager = cls.objects.get(playlist_id=playlist_id, user_id=user_id, is_active=True)
            manager.is_active = False
            manager.save()
            return True, "Manager removed successfully"
        except cls.DoesNotExist:
            return False, "Manager not found"
        except Exception as e:
            return False, str(e)


class ModerationAction(BaseModel):
    ACTION_TYPES: ClassVar[list[tuple[str, str]]] = [
        ("warn", "Warning"),
        ("remove", "Remove Content"),
        ("ban", "Ban User"),
        ("unfeature", "Unfeature Playlist"),
    ]

    playlist = models.ForeignKey(FeaturedPlaylist, on_delete=models.CASCADE, related_name="moderation_actions")
    moderator = models.ForeignKey(User, on_delete=models.PROTECT, related_name="moderation_actions")
    action_type = models.CharField(max_length=32, choices=ACTION_TYPES)
    reason = models.TextField(max_length=1000)
    action_metadata = models.JSONField(default=dict)
    permissions = models.JSONField(default=dict, validators=[validate_permissions_schema])

    class Meta(BaseModel.Meta):
        ordering: ClassVar[list[str]] = ["-created_at"]
        indexes: ClassVar[list[Index]] = [
            Index(fields=["playlist", "action_type"]),
            Index(fields=["moderator", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.moderator} - {self.action_type} - {self.playlist}"

    def get_permissions(self) -> PermissionsDict:
        return self.permissions
