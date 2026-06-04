"""
apps/tickets/integrations/jira.py
Jira Service Management integration for RAdmin ticket export.

Supports:
  - Creating issues via the Jira REST API v3
  - Appending comments to existing issues
  - Fetching open issues via JQL

Jira REST API reference:
  https://developer.atlassian.com/cloud/jira/platform/rest/v3/

Auth config JSON structure (stored in TicketIntegration.auth_config):
  API token (Jira Cloud):
    {"username": "user@example.com", "api_token": "your_token"}
  Personal Access Token (Jira Data Center):
    {"header_name": "Authorization", "api_key": "your_pat", "prefix": "Bearer"}

radmin.conf [tickets] section:
    jira_project_key  = OPS
    jira_issue_type   = Task
    jira_priority     = Medium
"""

import logging
import urllib.request
import urllib.error
import urllib.parse
import json
import base64

from .base import BaseTicketExporter, TicketPayload

logger = logging.getLogger(__name__)


class JiraExporter(BaseTicketExporter):

    # Jira REST API v3 endpoints
    ISSUE_API   = '/rest/api/3/issue'
    COMMENT_API = '/rest/api/3/issue/{issue_id}/comment'
    SEARCH_API  = '/rest/api/3/search'

    def __init__(self, integration):
        super().__init__(integration)
        cfg              = self.auth_config
        self.project_key = cfg.get('project_key', 'OPS')
        self.issue_type  = cfg.get('issue_type', 'Task')
        self.priority    = cfg.get('priority', 'Medium')

    def _get_headers(self):
        """
        Jira Cloud uses Basic auth with email + API token.
        Jira Data Center uses Bearer PAT.
        """
        cfg = self.auth_config

        if 'api_token' in cfg:
            # Jira Cloud: email:api_token base64 encoded
            credentials = base64.b64encode(
                f"{cfg['username']}:{cfg['api_token']}".encode()
            ).decode()
            return {
                'Authorization': f'Basic {credentials}',
                'Content-Type':  'application/json',
                'Accept':        'application/json',
            }

        # Fall back to parent implementation for PAT / other auth
        return {
            **super()._get_headers(),
            'Content-Type': 'application/json',
            'Accept':       'application/json',
        }

    def _api_url(self, path):
        return f'{self.base_url}{path}'

    def _request(self, method, url, data=None):
        """Make an authenticated request to the Jira REST API."""
        headers = self._get_headers()
        body    = json.dumps(data).encode() if data else None
        req     = urllib.request.Request(url, data=body, headers=headers, method=method)

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                response_body = resp.read().decode()
                return json.loads(response_body) if response_body else {}
        except urllib.error.HTTPError as e:
            error_body = e.read().decode()
            raise RuntimeError(
                f"Jira API error {e.code}: {error_body}"
            ) from e
        except urllib.error.URLError as e:
            raise RuntimeError(f"Jira connection error: {e.reason}") from e

    def _text_to_adf(self, text):
        """
        Convert plain text to Atlassian Document Format (ADF).
        Jira API v3 requires ADF for description and comment fields.
        """
        paragraphs = []
        for line in text.split('\n'):
            if line.strip():
                paragraphs.append({
                    'type': 'paragraph',
                    'content': [{'type': 'text', 'text': line}]
                })
            else:
                paragraphs.append({'type': 'paragraph', 'content': []})

        return {
            'type':    'doc',
            'version': 1,
            'content': paragraphs or [{'type': 'paragraph', 'content': []}]
        }

    def create_ticket(self, payload: TicketPayload) -> str:
        """Create a new Jira issue."""
        url  = self._api_url(self.ISSUE_API)
        body = {
            'fields': {
                'project':     {'key': self.project_key},
                'summary':     payload.short_description,
                'description': self._text_to_adf(payload.description),
                'issuetype':   {'name': self.issue_type},
                'priority':    {'name': self.priority},
                'labels':      ['radmin', 'remote-administration'],
            }
        }

        response = self._request('POST', url, body)
        issue_key = response.get('key', '')
        issue_id  = response.get('id', '')

        logger.info(f"Created Jira issue: {issue_key} (id: {issue_id})")
        return issue_key

    def update_ticket(self, ticket_id: str, payload: TicketPayload) -> bool:
        """Append a comment to an existing Jira issue."""
        url  = self._api_url(self.COMMENT_API.format(issue_id=ticket_id))
        body = {
            'body': self._text_to_adf(
                f"[RAdmin Session Export]\n\n{payload.work_log_text}"
            )
        }

        self._request('POST', url, body)
        logger.info(f"Added comment to Jira issue: {ticket_id}")
        return True

    def fetch_tickets(self, query: str = '', limit: int = 25) -> list:
        """
        Fetch open Jira issues using JQL.
        Returns a list of normalized ticket dicts.
        """
        jql_parts = [
            f'project = {self.project_key}',
            'statusCategory != Done',
            'statusCategory != "In Progress"',
        ]
        if query:
            jql_parts.append(f'summary ~ "{query}"')

        jql = ' AND '.join(jql_parts) + ' ORDER BY created DESC'

        url  = self._api_url(self.SEARCH_API)
        body = {
            'jql':        jql,
            'maxResults': limit,
            'fields':     ['summary', 'status', 'assignee', 'priority'],
        }

        try:
            response = self._request('POST', url, body)
            issues   = response.get('issues', [])
            return [
                {
                    'id':     issue.get('id', ''),
                    'number': issue.get('key', ''),
                    'title':  issue.get('fields', {}).get('summary', ''),
                    'status': issue.get('fields', {}).get('status', {}).get('name', ''),
                    'url':    f"{self.base_url}/browse/{issue.get('key', '')}",
                }
                for issue in issues
            ]
        except Exception as e:
            logger.error(f"Jira fetch_tickets error: {e}")
            return []

    def test_connection(self) -> bool:
        """Verify Jira connectivity by fetching project info."""
        try:
            url = self._api_url(f'/rest/api/3/project/{self.project_key}')
            self._request('GET', url)
            logger.info(f"Jira connection test passed: {self.base_url}")
            return True
        except Exception as e:
            logger.error(f"Jira connection test failed: {e}")
            return False
