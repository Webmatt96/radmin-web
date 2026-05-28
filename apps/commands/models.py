"""
apps/commands/models.py
Global command library.
Commands are defined here and assigned to hosts via HostCommand in the hosts app.
"""

import uuid
from django.db import models


class CommandDefinition(models.Model):
    """
    The global library of commands available in RAdmin.
    These are the canonical definitions — name, description, category,
    and which platforms support them.
    Individual hosts get their own subset via HostCommand (hosts app).
    """

    CATEGORY_CHOICES = [
        ('system',   'System Info'),
        ('services', 'Service Management'),
        ('logs',     'Log Access'),
        ('network',  'Network'),
        ('storage',  'Storage'),
        ('cluster',  'Cluster'),
        ('backup',   'Backup'),
        ('custom',   'Custom'),
    ]

    PLATFORM_CHOICES = [
        ('all',     'All Platforms'),
        ('windows', 'Windows Only'),
        ('linux',   'Linux Only'),
    ]

    id               = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    command_name     = models.CharField(max_length=100, unique=True)
    display_name     = models.CharField(max_length=200)
    description      = models.TextField(blank=True)
    category         = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='custom')
    platform         = models.CharField(max_length=10, choices=PLATFORM_CHOICES, default='all')
    takes_argument   = models.BooleanField(
                          default=False,
                          help_text="Whether this command accepts an argument (e.g. service_status <name>)"
                       )
    argument_hint    = models.CharField(
                          max_length=100,
                          blank=True,
                          help_text="Hint shown in the UI for the argument (e.g. 'service name')"
                       )
    requires_elevation = models.BooleanField(default=False)
    is_active        = models.BooleanField(default=True)
    created_at       = models.DateTimeField(auto_now_add=True)
    updated_at       = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['category', 'command_name']

    def __str__(self):
        return f"{self.display_name} ({self.command_name})"
