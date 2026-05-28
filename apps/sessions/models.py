"""
apps/sessions/models.py
Work sessions and command audit log.
Every command executed through RAdmin is recorded here.
"""

import uuid
from django.db import models
from django.utils import timezone


class Session(models.Model):
    """
    A work session — one user connected to one host.
    Started when the user opens a host in the web interface,
    ended when they close it or the connection drops.
    """

    TERMINATION_CHOICES = [
        ('user_closed',   'Closed by user'),
        ('timeout',       'Session timeout'),
        ('disconnected',  'Client disconnected'),
        ('error',         'Error'),
    ]

    id         = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user       = models.ForeignKey(
                    'accounts.User',
                    on_delete=models.PROTECT,
                    related_name='sessions'
                 )
    host       = models.ForeignKey(
                    'hosts.ManagedHost',
                    on_delete=models.PROTECT,
                    related_name='sessions'
                 )
    ticket_ref = models.CharField(
                    max_length=100,
                    blank=True,
                    help_text="Optional ticket number this session is associated with"
                 )
    started_at         = models.DateTimeField(default=timezone.now)
    ended_at           = models.DateTimeField(null=True, blank=True)
    termination_reason = models.CharField(
                            max_length=20,
                            choices=TERMINATION_CHOICES,
                            blank=True
                         )
    notes = models.TextField(
                blank=True,
                help_text="Freeform notes the technician can add during or after the session"
            )

    class Meta:
        ordering = ['-started_at']

    def __str__(self):
        return f"{self.user} → {self.host} @ {self.started_at:%Y-%m-%d %H:%M}"

    @property
    def duration(self):
        """Return session duration as a timedelta, or None if still active."""
        if self.ended_at:
            return self.ended_at - self.started_at
        return timezone.now() - self.started_at

    @property
    def is_active(self):
        return self.ended_at is None

    def close(self, reason='user_closed'):
        self.ended_at = timezone.now()
        self.termination_reason = reason
        self.save(update_fields=['ended_at', 'termination_reason'])

    def generate_work_log(self):
        """
        Generate a formatted work log string suitable for pasting
        into a ticket or exporting to a ticketing system.
        """
        lines = [
            f"RAdmin Work Log",
            f"===============",
            f"Host      : {self.host.hostname} ({self.host.ip_address})",
            f"Technician: {self.user.display_name or self.user.edipi}",
            f"Started   : {self.started_at:%Y-%m-%d %H:%M:%S UTC}",
            f"Ended     : {self.ended_at:%Y-%m-%d %H:%M:%S UTC}" if self.ended_at else "Ended     : Active",
            f"Ticket    : {self.ticket_ref or 'N/A'}",
            f"",
        ]

        if self.notes:
            lines += [f"Notes:", f"{self.notes}", f""]

        lines.append("Commands Executed:")
        lines.append("-" * 60)

        for log in self.command_logs.order_by('executed_at'):
            lines += [
                f"[{log.executed_at:%H:%M:%S}] {log.command_name}",
                f"  Duration: {log.duration_ms}ms",
                f"  Output:",
            ]
            for output_line in (log.result_output or '').splitlines():
                lines.append(f"    {output_line}")
            lines.append("")

        return "\n".join(lines)


class CommandLog(models.Model):
    """
    Every command executed in a session is recorded here.
    This is the audit trail that feeds the work log, ticketing
    exports, and the insights/pattern analysis engine.
    """

    id           = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session      = models.ForeignKey(Session, on_delete=models.CASCADE, related_name='command_logs')
    user         = models.ForeignKey('accounts.User', on_delete=models.PROTECT, related_name='command_logs')
    host         = models.ForeignKey('hosts.ManagedHost', on_delete=models.PROTECT, related_name='command_logs')
    command_name = models.CharField(max_length=100)
    command_args = models.TextField(blank=True)
    result_output = models.TextField(blank=True)
    exit_code    = models.IntegerField(null=True, blank=True)
    duration_ms  = models.IntegerField(null=True, blank=True)
    executed_at  = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['executed_at']

    def __str__(self):
        return f"{self.command_name} on {self.host.hostname} by {self.user} @ {self.executed_at:%H:%M:%S}"
