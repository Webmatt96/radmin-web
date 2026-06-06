"""
apps/diagnostics/models.py
Diagnostic engine — rule library, findings, and remediation log.
"""
import uuid
from django.db import models
from django.utils import timezone


class DiagnosticRule(models.Model):
    """
    A diagnostic rule loaded from a YAML file in the rules/ directory.
    The YAML file is the source of truth — this model is a cached
    representation for querying and auditing.
    """
    SEVERITY_CHOICES = [
        ('info',     'Info'),
        ('warning',  'Warning'),
        ('critical', 'Critical'),
    ]
    PLATFORM_CHOICES = [
        ('windows', 'Windows'),
        ('linux',   'Linux'),
        ('both',    'Both'),
    ]
    STATUS_CHOICES = [
        ('active',   'Active'),
        ('disabled', 'Disabled'),
        ('testing',  'Testing'),
    ]

    id           = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    rule_id      = models.CharField(max_length=20, unique=True, help_text="e.g. HV-004")
    name         = models.CharField(max_length=200)
    version      = models.CharField(max_length=20, default='1.0')
    severity     = models.CharField(max_length=10, choices=SEVERITY_CHOICES)
    platform     = models.CharField(max_length=10, choices=PLATFORM_CHOICES)
    category     = models.CharField(max_length=50, help_text="e.g. hyperv, storage, network")
    description  = models.TextField(blank=True)
    yaml_path    = models.CharField(max_length=500, help_text="Relative path to YAML file")
    autonomous   = models.BooleanField(
                       default=False,
                       help_text="Whether this rule can take autonomous remediation action"
                   )
    status       = models.CharField(max_length=10, choices=STATUS_CHOICES, default='active')
    loaded_at    = models.DateTimeField(auto_now=True)
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['rule_id']

    def __str__(self):
        return f"{self.rule_id} — {self.name} (v{self.version})"


class DiagnosticFinding(models.Model):
    """
    A finding produced by the diagnostic engine when a rule's
    conditions are matched against collected data.
    """
    SEVERITY_CHOICES = [
        ('info',     'Info'),
        ('warning',  'Warning'),
        ('critical', 'Critical'),
    ]
    CONFIDENCE_CHOICES = [
        ('low',    'Low'),
        ('medium', 'Medium'),
        ('high',   'High'),
    ]
    STATUS_CHOICES = [
        ('open',       'Open'),
        ('remediated', 'Remediated'),
        ('escalated',  'Escalated'),
        ('dismissed',  'Dismissed'),
    ]

    id              = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    rule            = models.ForeignKey(
                          DiagnosticRule,
                          on_delete=models.PROTECT,
                          related_name='findings'
                      )
    host            = models.ForeignKey(
                          'hosts.ManagedHost',
                          on_delete=models.PROTECT,
                          related_name='findings'
                      )
    severity        = models.CharField(max_length=10, choices=SEVERITY_CHOICES)
    confidence      = models.CharField(max_length=10, choices=CONFIDENCE_CHOICES)
    probable_cause  = models.TextField()
    detail          = models.TextField(blank=True, help_text="Raw command output that triggered this finding")
    recommendation  = models.TextField(blank=True)
    status          = models.CharField(max_length=15, choices=STATUS_CHOICES, default='open')
    rule_version    = models.CharField(max_length=20, help_text="Version of rule at time of finding")
    detected_at     = models.DateTimeField(default=timezone.now)
    resolved_at     = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-detected_at']

    def __str__(self):
        return f"{self.rule.rule_id} on {self.host.hostname} @ {self.detected_at:%Y-%m-%d %H:%M}"

    def resolve(self, status='remediated'):
        self.status = status
        self.resolved_at = timezone.now()
        self.save(update_fields=['status', 'resolved_at'])


class RemediationLog(models.Model):
    """
    Audit log of every remediation action taken by the engine.
    Every autonomous action is recorded here with the rule version
    that authorized it — full audit trail for DOD compliance.
    """
    OUTCOME_CHOICES = [
        ('success', 'Success'),
        ('failure', 'Failure'),
        ('skipped', 'Skipped'),
    ]
    TRIGGER_CHOICES = [
        ('autonomous', 'Autonomous'),
        ('approved',   'Operator Approved'),
        ('manual',     'Manual'),
    ]

    id              = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    finding         = models.ForeignKey(
                          DiagnosticFinding,
                          on_delete=models.PROTECT,
                          related_name='remediation_logs'
                      )
    action          = models.CharField(max_length=200, help_text="The action that was taken")
    command         = models.TextField(blank=True, help_text="Command executed on the host")
    output          = models.TextField(blank=True, help_text="Command output / result")
    outcome         = models.CharField(max_length=10, choices=OUTCOME_CHOICES)
    trigger         = models.CharField(max_length=15, choices=TRIGGER_CHOICES)
    triggered_by    = models.ForeignKey(
                          'accounts.User',
                          on_delete=models.PROTECT,
                          null=True,
                          blank=True,
                          related_name='remediation_logs',
                          help_text="Null if autonomous"
                      )
    rule_id         = models.CharField(max_length=20)
    rule_version    = models.CharField(max_length=20)
    executed_at     = models.DateTimeField(default=timezone.now)
    error_message   = models.TextField(blank=True)

    class Meta:
        ordering = ['-executed_at']

    def __str__(self):
        return f"{self.action} on {self.finding.host.hostname} — {self.outcome} @ {self.executed_at:%Y-%m-%d %H:%M}"
