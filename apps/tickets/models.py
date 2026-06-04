"""
apps/tickets/models.py
Ticketing system integration and work log export tracking.
"""

import uuid
from django.db import models
from django.utils import timezone
from apps.sessions.models import Session as RAdminSession


class TicketIntegration(models.Model):
    """
    Connection details for an external ticketing system.
    Auth config is stored encrypted — never plaintext.
    Multiple integrations can be active simultaneously.
    """

    SYSTEM_CHOICES = [
        ('servicenow', 'ServiceNow'),
        ('jira',       'Jira Service Management'),
        ('remedy',     'BMC Remedy'),
        ('custom',     'Custom'),
    ]

    AUTH_CHOICES = [
        ('oauth',  'OAuth 2.0'),
        ('apikey', 'API Key'),
        ('basic',  'Basic Auth'),
    ]

    id          = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name        = models.CharField(max_length=200)
    system_name = models.CharField(max_length=20, choices=SYSTEM_CHOICES)
    base_url    = models.URLField()
    auth_type   = models.CharField(max_length=10, choices=AUTH_CHOICES)
    auth_config = models.TextField(
                      help_text="Encrypted auth credentials (API key, OAuth tokens, etc.)"
                  )
    is_active   = models.BooleanField(default=True)
    created_by  = models.ForeignKey(
                      'accounts.User',
                      on_delete=models.PROTECT,
                      related_name='ticket_integrations'
                  )
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.get_system_name_display()})"


class WorkLogExport(models.Model):
    """
    Records every attempt to export a session work log to a ticketing system.
    Retains the exported content for audit purposes even if the ticket is later
    modified or deleted in the external system.
    """

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('sent',    'Sent'),
        ('failed',  'Failed'),
    ]

    id               = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session          = models.ForeignKey(
                           RAdminSession,
                           on_delete=models.PROTECT,
                           related_name='work_log_exports'
                       )
    integration      = models.ForeignKey(
                           TicketIntegration,
                           on_delete=models.PROTECT,
                           related_name='exports'
                       )
    external_ticket_id = models.CharField(max_length=200, blank=True)
    status           = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    exported_content = models.TextField(help_text="The work log text that was sent")
    exported_by      = models.ForeignKey(
                           'accounts.User',
                           on_delete=models.PROTECT,
                           related_name='work_log_exports'
                       )
    exported_at      = models.DateTimeField(null=True, blank=True)
    error_message    = models.TextField(blank=True)
    retry_count      = models.PositiveIntegerField(default=0)
    created_at       = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.session} → {self.integration.name} ({self.get_status_display()})"

    def mark_sent(self, external_ticket_id=''):
        self.status = 'sent'
        self.exported_at = timezone.now()
        self.external_ticket_id = external_ticket_id
        self.error_message = ''
        self.save(update_fields=['status', 'exported_at', 'external_ticket_id', 'error_message'])

    def mark_failed(self, error_message=''):
        self.status = 'failed'
        self.error_message = error_message
        self.retry_count += 1
        self.save(update_fields=['status', 'error_message', 'retry_count'])
