"""
apps/hosts/management/commands/populate_host_commands.py

Automatically assigns commands from CommandDefinition to each ManagedHost
based on the host's OS type.

Usage:
    python3 manage.py populate_host_commands
    python3 manage.py populate_host_commands --host radmin-server
    python3 manage.py populate_host_commands --dry-run
"""

from django.core.management.base import BaseCommand
from apps.hosts.models import ManagedHost, HostCommand
from apps.commands.models import CommandDefinition


class Command(BaseCommand):
    help = 'Auto-populate host commands from the CommandDefinition library'

    def add_arguments(self, parser):
        parser.add_argument(
            '--host',
            type=str,
            help='Only populate commands for this hostname',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be added without making changes',
        )
        parser.add_argument(
            '--overwrite',
            action='store_true',
            help='Remove existing host commands before repopulating',
        )

    def handle(self, *args, **options):
        dry_run  = options['dry_run']
        overwrite = options['overwrite']
        hostname = options.get('host')

        # Get hosts to process
        hosts = ManagedHost.objects.all()
        if hostname:
            hosts = hosts.filter(hostname=hostname)
            if not hosts.exists():
                self.stderr.write(f"Host '{hostname}' not found.")
                return

        total_added   = 0
        total_skipped = 0

        for host in hosts:
            self.stdout.write(f"\nProcessing: {host.hostname} ({host.get_os_type_display()})")

            # Get commands appropriate for this host's OS
            platform_filter = ['all']
            if host.os_type == 'windows':
                platform_filter.append('windows')
            elif host.os_type == 'linux':
                platform_filter.append('linux')
            elif host.os_type == 'macos':
                platform_filter.append('linux')  # macOS uses Linux commands

            definitions = CommandDefinition.objects.filter(
                platform__in=platform_filter,
                is_active=True
            ).order_by('category', 'command_name')

            if overwrite and not dry_run:
                deleted = HostCommand.objects.filter(host=host).delete()
                self.stdout.write(f"  Removed {deleted[0]} existing commands")

            added   = 0
            skipped = 0

            for defn in definitions:
                # Check if already exists
                exists = HostCommand.objects.filter(
                    host=host,
                    command_name=defn.command_name
                ).exists()

                if exists and not overwrite:
                    skipped += 1
                    continue

                if dry_run:
                    self.stdout.write(
                        f"  [DRY RUN] Would add: {defn.command_name} ({defn.get_category_display()})"
                    )
                    added += 1
                else:
                    HostCommand.objects.get_or_create(
                        host=host,
                        command_name=defn.command_name,
                        defaults={
                            'description':        defn.description,
                            'category':           defn.category,
                            'requires_elevation': defn.requires_elevation,
                            'is_active':          True,
                        }
                    )
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"  + {defn.command_name} ({defn.get_category_display()})"
                        )
                    )
                    added += 1

            total_added   += added
            total_skipped += skipped

            self.stdout.write(
                f"  Done: {added} added, {skipped} skipped"
            )

        self.stdout.write(f"\nTotal: {total_added} added, {total_skipped} skipped")

        if dry_run:
            self.stdout.write(
                self.style.WARNING("\nDry run — no changes made. Remove --dry-run to apply.")
            )
