"""
apps/tickets/management/commands/setup_jira.py
Management command to configure the Jira ticket integration.

Usage:
    python3 manage.py setup_jira

Fill in your values when prompted. Credentials are stored in the
database and never written to disk or version control.
"""

import json
from django.core.management.base import BaseCommand
from apps.tickets.models import TicketIntegration
from apps.accounts.models import User


class Command(BaseCommand):
    help = 'Configure Jira Service Management integration'

    def handle(self, *args, **options):
        self.stdout.write('\n=== Jira Integration Setup ===\n')

        # Collect configuration
        instance  = input('Jira instance URL (e.g. https://yourorg.atlassian.net): ').strip().rstrip('/')
        username  = input('Atlassian account email: ').strip()
        api_token = input('API token (from id.atlassian.com/manage-profile/security/api-tokens): ').strip()
        project   = input('Project key (e.g. SCRUM or AO): ').strip().upper()
        issue_type = input('Issue type [Task]: ').strip() or 'Task'
        priority   = input('Default priority [Medium]: ').strip() or 'Medium'
        name       = input('Integration name [Jira - Ascendant Operations]: ').strip() or 'Jira - Ascendant Operations'

        # Get the first superuser as the creator
        try:
            creator = User.objects.filter(is_superuser=True).first()
        except Exception:
            self.stderr.write('[ERROR] No superuser found. Run provision_user first.')
            return

        auth_config = json.dumps({
            'username':    username,
            'api_token':   api_token,
            'project_key': project,
            'issue_type':  issue_type,
            'priority':    priority,
        })

        integration, created = TicketIntegration.objects.update_or_create(
            system_name = 'jira',
            base_url    = instance,
            defaults    = {
                'name':        name,
                'auth_type':   'apikey',
                'auth_config': auth_config,
                'is_active':   True,
                'created_by':  creator,
            }
        )

        action = 'Created' if created else 'Updated'
        self.stdout.write(f'\n{action} integration: {integration.name}')
        self.stdout.write(f'ID: {integration.id}')
        self.stdout.write('\nTest the connection with:')
        self.stdout.write(f'  curl -sk --cert ... https://192.168.122.1/tickets/integrations/{integration.id}/test/')
