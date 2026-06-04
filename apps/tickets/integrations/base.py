"""
apps/tickets/integrations/base.py
Abstract base class for ticketing system integrations.

All integrations must implement:
  - create_ticket(payload) -> external_ticket_id
  - update_ticket(ticket_id, payload) -> bool
  - fetch_tickets(query) -> list[dict]
  - test_connection() -> bool
"""

import json
import logging
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class TicketPayload:
    """
    Normalized ticket payload built from an RAdmin session.
    Passed to all exporters regardless of target system.
    """

    def __init__(self, session, work_log_text, operator=None):
        self.session       = session
        self.work_log_text = work_log_text
        self.operator      = operator or session.user

    @property
    def short_description(self):
        host     = self.session.host.hostname
        operator = self.operator.display_name or self.operator.edipi
        started  = self.session.started_at.strftime('%Y-%m-%d %H:%M UTC')
        return f"RAdmin session — {host} — {operator} — {started}"

    @property
    def description(self):
        return self.work_log_text

    @property
    def category(self):
        return "Remote Administration"

    @property
    def affected_ci(self):
        """Configuration item — the managed host."""
        return self.session.host.hostname

    @property
    def ticket_ref(self):
        return self.session.ticket_ref or ''

    def to_dict(self):
        return {
            'short_description': self.short_description,
            'description':       self.description,
            'category':          self.category,
            'affected_ci':       self.affected_ci,
            'ticket_ref':        self.ticket_ref,
            'host':              self.session.host.hostname,
            'host_ip':           str(self.session.host.ip_address),
            'operator':          self.operator.display_name or self.operator.edipi,
            'started_at':        self.session.started_at.isoformat(),
            'ended_at':          self.session.ended_at.isoformat() if self.session.ended_at else None,
        }


class BaseTicketExporter(ABC):
    """
    Abstract base for all ticketing system integrations.
    Subclasses implement the system-specific API calls.
    """

    def __init__(self, integration):
        """
        integration: TicketIntegration model instance
        """
        self.integration = integration
        self.base_url    = integration.base_url.rstrip('/')
        self.auth_config = self._load_auth_config()
        self.logger      = logging.getLogger(
            f"{__name__}.{integration.system_name}"
        )

    def _load_auth_config(self):
        """
        Load auth config from the integration record.
        Currently stores as JSON — encrypted storage is a future milestone.
        """
        try:
            return json.loads(self.integration.auth_config)
        except (json.JSONDecodeError, TypeError):
            return {}

    def _get_headers(self):
        """Build auth headers based on the integration's auth_type."""
        import base64

        auth_type = self.integration.auth_type
        cfg       = self.auth_config

        if auth_type == 'apikey':
            header_name = cfg.get('header_name', 'Authorization')
            api_key     = cfg.get('api_key', '')
            prefix      = cfg.get('prefix', 'Bearer')
            return {header_name: f'{prefix} {api_key}'}

        elif auth_type == 'basic':
            username = cfg.get('username', '')
            password = cfg.get('password', '')
            encoded  = base64.b64encode(
                f'{username}:{password}'.encode()
            ).decode()
            return {'Authorization': f'Basic {encoded}'}

        elif auth_type == 'oauth':
            token = cfg.get('access_token', '')
            return {'Authorization': f'Bearer {token}'}

        return {}

    @abstractmethod
    def create_ticket(self, payload: TicketPayload) -> str:
        """
        Create a new ticket from a session payload.
        Returns the external ticket ID/number on success.
        Raises an exception on failure.
        """

    @abstractmethod
    def update_ticket(self, ticket_id: str, payload: TicketPayload) -> bool:
        """
        Append session work log to an existing ticket.
        Returns True on success.
        Raises an exception on failure.
        """

    @abstractmethod
    def fetch_tickets(self, query: str = '', limit: int = 25) -> list:
        """
        Fetch open tickets from the external system.
        Returns a list of dicts: [{id, number, title, status, url}, ...]
        """

    @abstractmethod
    def test_connection(self) -> bool:
        """
        Verify the integration credentials and connectivity.
        Returns True if the connection is healthy.
        """

    def export_session(self, session, work_log_export_record):
        """
        High-level export method called by the view layer.
        Handles both create and update based on whether the session
        has an existing ticket_ref.
        """
        work_log_text = session.generate_work_log()
        payload       = TicketPayload(session, work_log_text)

        try:
            if session.ticket_ref:
                # Append to existing ticket
                self.logger.info(
                    f"Updating ticket {session.ticket_ref} "
                    f"for session {session.id}"
                )
                self.update_ticket(session.ticket_ref, payload)
                work_log_export_record.mark_sent(session.ticket_ref)
            else:
                # Create new ticket
                self.logger.info(f"Creating ticket for session {session.id}")
                ticket_id = self.create_ticket(payload)
                work_log_export_record.mark_sent(ticket_id)
                # Back-fill the ticket ref on the session
                session.ticket_ref = ticket_id
                session.save(update_fields=['ticket_ref'])

            return True

        except Exception as e:
            self.logger.error(f"Export failed: {e}")
            work_log_export_record.mark_failed(str(e))
            raise


def get_exporter(integration):
    """
    Factory — returns the correct exporter for a TicketIntegration instance.
    """
    from .servicenow import ServiceNowExporter
    from .jira       import JiraExporter

    exporters = {
        'servicenow': ServiceNowExporter,
        'jira':       JiraExporter,
    }

    cls = exporters.get(integration.system_name)
    if not cls:
        raise ValueError(
            f"No exporter available for system: {integration.system_name}"
        )
    return cls(integration)
