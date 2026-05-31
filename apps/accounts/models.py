"""
apps/accounts/models.py
Custom User model based on CAC authentication.
No passwords — identity comes from the CAC certificate.

Supports two identifier formats:
  - DoD CAC EDIPI:  10-digit numeric (e.g. 1234567890)
  - Ascendant AGID: division-prefixed alphanumeric (e.g. TAG-000001)
"""
import uuid
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models


class Role(models.Model):
    id          = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name        = models.CharField(max_length=50, unique=True)
    permissions = models.JSONField(default=dict, help_text="Command whitelist per role")
    description = models.TextField(blank=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class UserManager(BaseUserManager):
    def create_user(self, edipi, distinguished_name, **extra_fields):
        if not edipi:
            raise ValueError("EDIPI or AGID is required")
        user = self.model(edipi=edipi, distinguished_name=distinguished_name, **extra_fields)
        user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, edipi, distinguished_name, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        return self.create_user(edipi, distinguished_name, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Supports both DoD EDIPI (10-digit numeric) and Ascendant AGID (e.g. TAG-000001)
    edipi = models.CharField(
        max_length=20,
        unique=True,
        help_text="CAC identifier — DoD EDIPI (10-digit) or Ascendant AGID (e.g. TAG-000001)"
    )

    distinguished_name = models.TextField(
        unique=True,
        help_text="Full DN from certificate subject"
    )
    display_name = models.CharField(max_length=200, blank=True)
    email        = models.EmailField(blank=True)

    role = models.ForeignKey(
        Role,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='users'
    )

    is_active  = models.BooleanField(default=True)
    is_staff   = models.BooleanField(default=False)
    last_login = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = UserManager()

    USERNAME_FIELD  = 'edipi'
    REQUIRED_FIELDS = ['distinguished_name']

    class Meta:
        ordering = ['display_name', 'edipi']

    def __str__(self):
        return self.display_name or self.edipi

    @property
    def is_dod_user(self):
        """True if this user authenticated with a DoD CAC (numeric EDIPI)."""
        return self.edipi.isdigit() and len(self.edipi) == 10

    @property
    def is_ascendant_user(self):
        """True if this user authenticated with an Ascendant Group AGID."""
        return '-' in self.edipi

    @property
    def allowed_commands(self):
        """Return the command whitelist for this user's role."""
        if self.role:
            return self.role.permissions.get('commands', [])
        return []
