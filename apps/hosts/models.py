"""
apps/hosts/models.py
Managed host registry and per-host command definitions.
"""

import uuid
from django.db import models


class ManagedHost(models.Model):
    OS_CHOICES = [
        ('windows', 'Windows'),
        ('linux',   'Linux'),
        ('macos',   'macOS'),
    ]

    ENV_CHOICES = [
        ('production',  'Production'),
        ('staging',     'Staging'),
        ('development', 'Development'),
        ('lab',         'Lab'),
    ]

    id          = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    hostname    = models.CharField(max_length=255, unique=True)
    ip_address  = models.GenericIPAddressField(null=True, blank=True)
    os_type     = models.CharField(max_length=20, choices=OS_CHOICES, default='windows')
    environment = models.CharField(max_length=20, choices=ENV_CHOICES, default='production')
    description = models.TextField(blank=True)
    is_online   = models.BooleanField(default=False)
    last_seen   = models.DateTimeField(null=True, blank=True)
    registered_at = models.DateTimeField(auto_now_add=True)
    registered_by = models.ForeignKey(
                        'accounts.User',
                        on_delete=models.SET_NULL,
                        null=True,
                        blank=True,
                        related_name='registered_hosts'
                    )

    class Meta:
        ordering = ['hostname']

    def __str__(self):
        return f"{self.hostname} ({self.get_os_type_display()})"

    @property
    def available_commands(self):
        return self.commands.filter(is_active=True).order_by('category', 'command_name')


class HostCommand(models.Model):
    """
    Per-host command registry.
    Each host has its own list of available commands — a Windows failover
    cluster node has different commands than a standard Linux VM.
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

    id                = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    host              = models.ForeignKey(ManagedHost, on_delete=models.CASCADE, related_name='commands')
    command_name      = models.CharField(max_length=100)
    description       = models.CharField(max_length=255, blank=True)
    category          = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='custom')
    requires_elevation = models.BooleanField(default=False)
    is_active         = models.BooleanField(default=True)
    created_at        = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['category', 'command_name']
        unique_together = [['host', 'command_name']]

    def __str__(self):
        return f"{self.host.hostname} → {self.command_name}"
