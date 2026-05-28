"""
apps/commands/migrations/0002_initial_data.py
Populates the CommandDefinition table with all commands
from the socket service layer.
"""

from django.db import migrations


COMMANDS = [
    # System Info
    {
        'command_name':       'help',
        'display_name':       'Help',
        'description':        'List all available commands on this host.',
        'category':           'system',
        'platform':           'all',
        'takes_argument':     False,
        'requires_elevation': False,
    },
    {
        'command_name':       'sys_info',
        'display_name':       'System Information',
        'description':        'OS, hostname, architecture, uptime, and Python version.',
        'category':           'system',
        'platform':           'all',
        'takes_argument':     False,
        'requires_elevation': False,
    },
    {
        'command_name':       'cpu_usage',
        'display_name':       'CPU Usage',
        'description':        'Current CPU utilization across all cores.',
        'category':           'system',
        'platform':           'all',
        'takes_argument':     False,
        'requires_elevation': False,
    },
    {
        'command_name':       'memory_usage',
        'display_name':       'Memory Usage',
        'description':        'Total, used, and free RAM.',
        'category':           'system',
        'platform':           'all',
        'takes_argument':     False,
        'requires_elevation': False,
    },
    {
        'command_name':       'disk_usage',
        'display_name':       'Disk Usage',
        'description':        'Filesystem usage for all mounted drives.',
        'category':           'storage',
        'platform':           'all',
        'takes_argument':     False,
        'requires_elevation': False,
    },
    {
        'command_name':       'reboot',
        'display_name':       'Reboot',
        'description':        'Reboot the machine immediately.',
        'category':           'system',
        'platform':           'all',
        'takes_argument':     False,
        'requires_elevation': True,
    },

    # Service Management
    {
        'command_name':       'service_list',
        'display_name':       'List Running Services',
        'description':        'Show all currently running services.',
        'category':           'services',
        'platform':           'all',
        'takes_argument':     False,
        'requires_elevation': False,
    },
    {
        'command_name':       'service_status',
        'display_name':       'Service Status',
        'description':        'Get the status of a specific service.',
        'category':           'services',
        'platform':           'all',
        'takes_argument':     True,
        'argument_hint':      'service name',
        'requires_elevation': False,
    },
    {
        'command_name':       'service_start',
        'display_name':       'Start Service',
        'description':        'Start a specific service.',
        'category':           'services',
        'platform':           'all',
        'takes_argument':     True,
        'argument_hint':      'service name',
        'requires_elevation': True,
    },
    {
        'command_name':       'service_stop',
        'display_name':       'Stop Service',
        'description':        'Stop a specific service.',
        'category':           'services',
        'platform':           'all',
        'takes_argument':     True,
        'argument_hint':      'service name',
        'requires_elevation': True,
    },

    # Logs
    {
        'command_name':       'tail_syslog',
        'display_name':       'System Log',
        'description':        'Last N lines of the system log. Defaults to 50.',
        'category':           'logs',
        'platform':           'all',
        'takes_argument':     True,
        'argument_hint':      'number of lines (default 50)',
        'requires_elevation': False,
    },
    {
        'command_name':       'tail_applog',
        'display_name':       'Application Log',
        'description':        'Last N lines of the application/auth log. Defaults to 50.',
        'category':           'logs',
        'platform':           'all',
        'takes_argument':     True,
        'argument_hint':      'number of lines (default 50)',
        'requires_elevation': False,
    },
    {
        'command_name':       'application_log',
        'display_name':       'Windows Application Event Log',
        'description':        'Last 10 entries from the Windows Application Event Log.',
        'category':           'logs',
        'platform':           'windows',
        'takes_argument':     False,
        'requires_elevation': False,
    },
    {
        'command_name':       'installroot_log',
        'display_name':       'DoD PKE InstallRoot Log',
        'description':        'Last 10 entries from the DoD PKE InstallRoot event log.',
        'category':           'logs',
        'platform':           'windows',
        'takes_argument':     False,
        'requires_elevation': False,
    },

    # Network
    {
        'command_name':       'net_connections',
        'display_name':       'Active Network Connections',
        'description':        'All established TCP connections.',
        'category':           'network',
        'platform':           'all',
        'takes_argument':     False,
        'requires_elevation': False,
    },
    {
        'command_name':       'net_interfaces',
        'display_name':       'Network Interfaces',
        'description':        'Network adapter status and IP addresses.',
        'category':           'network',
        'platform':           'all',
        'takes_argument':     False,
        'requires_elevation': False,
    },

    # Cluster (Windows only)
    {
        'command_name':       'failover_cluster_validation',
        'display_name':       'Failover Cluster Validation',
        'description':        'Run Test-Cluster to validate the failover cluster configuration.',
        'category':           'cluster',
        'platform':           'windows',
        'takes_argument':     False,
        'requires_elevation': True,
    },
]


def load_commands(apps, schema_editor):
    CommandDefinition = apps.get_model('commands', 'CommandDefinition')
    for cmd in COMMANDS:
        CommandDefinition.objects.get_or_create(
            command_name=cmd['command_name'],
            defaults=cmd
        )


def unload_commands(apps, schema_editor):
    CommandDefinition = apps.get_model('commands', 'CommandDefinition')
    names = [c['command_name'] for c in COMMANDS]
    CommandDefinition.objects.filter(command_name__in=names).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('commands', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(load_commands, unload_commands),
    ]
