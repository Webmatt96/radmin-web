"""
apps/tickets/integrations/servicenow.py
ServiceNow integration for RAdmin ticket export.

Supports:
  - Creating incidents via the Table API
  - Appending work notes to existing incidents
  - Fetching open incidents assigned to a group or user

ServiceNow Table API reference:
  https://developer.servicenow.com/dev.do#!/reference/api/latest/rest/c_TableAPI

Auth config JSON structure (stored in TicketIntegration.auth_config):
  Basic auth:
    {"username": "radmin_svc", "password": "secret"}
  API key (if using custom auth plugin):
    {"header_name": "X-UserToken", "api_key": "your_token", "prefix": ""}

radmin.conf [tickets] section:
    servicenow_instance = your-instance.service-now.com
    servicenow_table    = incident
    servicenow_category = Software
    servicenow_assignment_group = IT Operations
"""

import logging
import urllib.request
import urllib.error
import json

from .base import BaseTicketExporter, TicketPayload

logger = logging.getLogger(__name__)


class ServiceNowExporter(BaseTicketExporter):

    # ServiceNow Table API endpoints
    TABLE_API = '/api/now/table/{table}'
    RECORD_API = '/api/now/table/{table}/{sys_id}'

    def __init__(self, integration):
        super().__init__(integration)
        cfg             = self.auth_config
        self.table      = cfg.get('table', 'incident')
        self.category   = cfg.get('category', 'Software')
        self.assignment = cfg.get('assignment_group', '')

    def _api_url(self, path):
        return f'{self.base_url}{path}'

    def _request(self, method, url, data=None):
        """
        Make an authenticated HTTP request to the ServiceNow API.
        Returns the parsed JSON response body.
        """
        headers = {
            **self._get_headers(),
            'Content-Type':  'application/json',
            'Accept':        'application/json',
        }

        body = json.dumps(data).encode() if data else None
        req  = urllib.request.Request(url, data=body, headers=headers, method=method)

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            error_body = e.read().decode()
            raise RuntimeError(
                f"ServiceNow API error {e.code}: {error_body}"
            ) from e
        except urllib.error.URLError as e:
            raise RuntimeError(f"ServiceNow connection error: {e.reason}") from e

    def create_ticket(self, payload: TicketPayload) -> str:
        """Create a new ServiceNow incident."""
        url  = self._api_url(self.TABLE_API.format(table=self.table))
        body = {
            'short_description': payload.short_description,
            'description':       payload.description,
            'category':          self.category,
            'work_notes':        payload.work_log_text,
        }
        if self.assignment:
            body['assignment_group'] = self.assignment
        if payload.affected_ci:
            body['cmdb_ci'] = payload.affected_ci

        response  = self._request('POST', url, body)
        result    = response.get('result', {})
        sys_id    = result.get('sys_id', '')
        number    = result.get('number', sys_id)

        logger.info(f"Created ServiceNow incident: {number} (sys_id: {sys_id})")
        return number

    def update_ticket(self, ticket_id: str, payload: TicketPayload) -> bool:
        """
        Append work notes to an existing ServiceNow incident.
        ticket_id can be the incident number (INC0001234) or sys_id.
        """
        # If given an incident number, resolve to sys_id first
        sys_id = self._resolve_sys_id(ticket_id)
        if not sys_id:
            raise RuntimeError(f"Could not resolve ticket '{ticket_id}' to a sys_id")

        url  = self._api_url(self.RECORD_API.format(table=self.table, sys_id=sys_id))
        body = {
            'work_notes': (
                f"[RAdmin Session Export]\n\n{payload.work_log_text}"
            )
        }

        self._request('PATCH', url, body)
        logger.info(f"Updated ServiceNow incident: {ticket_id}")
        return True

    def fetch_tickets(self, query: str = '', limit: int = 25) -> list:
        """
        Fetch open incidents from ServiceNow.
        Returns a list of normalized ticket dicts.
        """
        # Build sysparm_query — default to active incidents
        sysparm_query = 'active=true^state!=6'   # state 6 = Resolved
        if query:
            sysparm_query += f'^short_descriptionLIKE{query}'
        if self.assignment:
            sysparm_query += f'^assignment_group.name={self.assignment}'

        url = (
            self._api_url(self.TABLE_API.format(table=self.table)) +
            f'?sysparm_query={urllib.parse.quote(sysparm_query)}'
            f'&sysparm_limit={limit}'
            f'&sysparm_fields=sys_id,number,short_description,state,assigned_to'
        )

        try:
            import urllib.parse
            response = self._request('GET', url)
            records  = response.get('result', [])
            return [
                {
                    'id':     r.get('sys_id', ''),
                    'number': r.get('number', ''),
                    'title':  r.get('short_description', ''),
                    'status': r.get('state', ''),
                    'url':    f"{self.base_url}/nav_to.do?uri=incident.do?sys_id={r.get('sys_id','')}",
                }
                for r in records
            ]
        except Exception as e:
            logger.error(f"ServiceNow fetch_tickets error: {e}")
            return []

    def test_connection(self) -> bool:
        """Verify ServiceNow connectivity by fetching a single record."""
        try:
            url = (
                self._api_url(self.TABLE_API.format(table=self.table)) +
                '?sysparm_limit=1&sysparm_fields=sys_id'
            )
            self._request('GET', url)
            logger.info(f"ServiceNow connection test passed: {self.base_url}")
            return True
        except Exception as e:
            logger.error(f"ServiceNow connection test failed: {e}")
            return False

    def _resolve_sys_id(self, ticket_id: str) -> str:
        """
        Resolve an incident number like INC0001234 to its sys_id.
        If ticket_id looks like a sys_id already (32 hex chars), return as-is.
        """
        import re
        if re.match(r'^[0-9a-f]{32}$', ticket_id, re.IGNORECASE):
            return ticket_id

        import urllib.parse
        url = (
            self._api_url(self.TABLE_API.format(table=self.table)) +
            f'?sysparm_query=number={urllib.parse.quote(ticket_id)}'
            f'&sysparm_fields=sys_id&sysparm_limit=1'
        )
        try:
            response = self._request('GET', url)
            results  = response.get('result', [])
            if results:
                return results[0].get('sys_id', '')
        except Exception as e:
            logger.error(f"Could not resolve sys_id for {ticket_id}: {e}")
        return ''
