"""
apps/credentials/models.py
Credential package management and per-host deployment tracking.
Certs and secrets are encrypted at rest using Django's signing module.
"""

import uuid
from django.db import models
from django.utils import timezone


class CredentialPackage(models.Model):
    """
    A versioned set of TLS certificates and shared secrets.
    When certs rotate or the shared secret changes, a new package
    is created and deployed to all hosts. The old package is retained
    for audit purposes.
    """

    STATUS_CHOICES = [
        ('draft',    'Draft'),
        ('active',   'Active'),
        ('retired',  'Retired'),
    ]

    id            = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name          = models.CharField(max_length=200)
    version       = models.PositiveIntegerField(default=1)
    status        = models.CharField(max_length=10, choices=STATUS_CHOICES, default='draft')

    # Stored encrypted — never in plaintext in the database
    cert_data     = models.TextField(
                        help_text="PEM certificate data (encrypted at rest)"
                    )
    shared_secret = models.TextField(
                        help_text="HMAC shared secret (encrypted at rest)"
                    )

    valid_from    = models.DateTimeField(default=timezone.now)
    valid_until   = models.DateTimeField(null=True, blank=True)

    created_by    = models.ForeignKey(
                        'accounts.User',
                        on_delete=models.PROTECT,
                        related_name='created_packages'
                    )
    created_at    = models.DateTimeField(auto_now_add=True)
    notes         = models.TextField(blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} v{self.version} ({self.get_status_display()})"

    @property
    def is_expired(self):
        if self.valid_until:
            return timezone.now() > self.valid_until
        return False

    @property
    def deployment_summary(self):
        total    = self.host_credentials.count()
        deployed = self.host_credentials.filter(status='deployed').count()
        failed   = self.host_credentials.filter(status='failed').count()
        pending  = self.host_credentials.filter(status='pending').count()
        return {
            'total':    total,
            'deployed': deployed,
            'failed':   failed,
            'pending':  pending,
        }


class HostCredential(models.Model):
    """
    Tracks the deployment status of a credential package to a specific host.
    One row per host per package — updated each time a deployment is attempted.
    """

    STATUS_CHOICES = [
        ('pending',  'Pending'),
        ('deploying','Deploying'),
        ('deployed', 'Deployed'),
        ('failed',   'Failed'),
    ]

    id          = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    host        = models.ForeignKey(
                      'hosts.ManagedHost',
                      on_delete=models.CASCADE,
                      related_name='credentials'
                  )
    package     = models.ForeignKey(
                      CredentialPackage,
                      on_delete=models.PROTECT,
                      related_name='host_credentials'
                  )
    status      = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    deployed_at = models.DateTimeField(null=True, blank=True)
    deployed_by = models.ForeignKey(
                      'accounts.User',
                      on_delete=models.SET_NULL,
                      null=True,
                      blank=True,
                      related_name='deployments'
                  )
    error_message = models.TextField(blank=True)
    retry_count   = models.PositiveIntegerField(default=0)
    created_at    = models.DateTimeField(auto_now_add=True)
    updated_at    = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']
        unique_together = [['host', 'package']]

    def __str__(self):
        return f"{self.package.name} → {self.host.hostname} ({self.get_status_display()})"

    def mark_deployed(self, user=None):
        self.status = 'deployed'
        self.deployed_at = timezone.now()
        if user:
            self.deployed_by = user
        self.error_message = ''
        self.save(update_fields=['status', 'deployed_at', 'deployed_by', 'error_message', 'updated_at'])

    def mark_failed(self, error_message=''):
        self.status = 'failed'
        self.error_message = error_message
        self.retry_count += 1
        self.save(update_fields=['status', 'error_message', 'retry_count', 'updated_at'])
