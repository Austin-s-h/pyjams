from enum import Enum, Flag, auto
from typing import ClassVar

from django.contrib.auth.models import AbstractUser
from django.db import models


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

    BASIC = VIEW | SEARCH
    CONTRIBUTOR = BASIC | SUGGEST | VOTE
    MANAGER = CONTRIBUTOR | ADD_SONGS | REMOVE_SONGS | MANAGE_PLAYLIST
    MODERATOR = MANAGER | MODERATE
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
    spotify_id = models.CharField(max_length=64, unique=True, null=True, blank=True, db_index=True)
    spotify_email = models.EmailField(null=True, blank=True)
    spotify_display_name = models.CharField(max_length=255, null=True, blank=True)
    
    # Role management
    role = models.CharField(
        max_length=20,
        choices=[(role.value, role.name) for role in UserRole],
        default=UserRole.USER.value,  # Changed default from GUEST to USER
    )

    class Meta:
        swappable = 'AUTH_USER_MODEL'
        db_table = 'pyjams_user'

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
    def get_by_spotify_id(cls, spotify_id: str):
        return cls.objects.filter(spotify_id=spotify_id).first()

class FeaturedPlaylist(models.Model):
    spotify_id = models.CharField(max_length=64, unique=True, db_index=True)
    name = models.CharField(max_length=255)
    description = models.TextField(max_length=1000, null=True, blank=True)
    image_url = models.URLField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    creator = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='featured_playlists'
    )
    is_active = models.BooleanField(default=True)
    is_visible = models.BooleanField(default=True)
    contribution_rules = models.JSONField(default=dict)
    managers = models.ManyToManyField(
        User,
        through='PlaylistManager',
        related_name='managed_featured_playlists'
    )

    def __str__(self):
        return self.name

    def user_can_manage(self, user: User) -> bool:
        if user.is_admin or user.id == self.creator.id:
            return True
        return self.managers_through.filter(
            user=user,
            is_active=True
        ).exists()

class PlaylistManager(models.Model):
    playlist = models.ForeignKey(FeaturedPlaylist, on_delete=models.CASCADE, related_name='managers_through')
    user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE,
        related_name='managed_playlists'
    )
    permissions = models.JSONField(default=dict)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together: ClassVar[list[str]] = ['playlist', 'user']

    def __str__(self):
        return f"{self.user.name} - {self.playlist.name}"  # Using name instead of username

    def has_permission(self, permission_key):
        return self.permissions.get(permission_key, False)

    @classmethod
    def get_active_managers(cls, playlist_id):
        return cls.objects.filter(playlist_id=playlist_id, is_active=True)

class ModerationAction(models.Model):
    playlist = models.ForeignKey(FeaturedPlaylist, on_delete=models.CASCADE)
    moderator = models.ForeignKey(
        User,
        on_delete=models.PROTECT
    )
    action_type = models.CharField(max_length=32)
    reason = models.TextField(max_length=1000)
    created_at = models.DateTimeField(auto_now_add=True)
    action_metadata = models.JSONField(default=dict)
