"""
apps/hosts/views.py
Dashboard and host detail views.
"""

import json
import logging
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.utils import timezone
from .models import ManagedHost
from apps.commands.models import CommandDefinition
from apps.sessions.models import Session, CommandLog

logger = logging.getLogger(__name__)


@login_required
def dashboard(request):
    """
    Main dashboard — shows all managed hosts with online/offline status.
    """
    hosts = ManagedHost.objects.all().order_by('environment', 'hostname')

    # Counts for the summary bar
    total   = hosts.count()
    online  = hosts.filter(is_online=True).count()
    offline = total - online

    context = {
        'hosts':   hosts,
        'total':   total,
        'online':  online,
        'offline': offline,
    }
    return render(request, 'hosts/dashboard.html', context)


@login_required
def host_detail(request, host_id):
    """
    Host detail page — command selector and output panel.
    Opens a work session when the page loads.
    """
    host = get_object_or_404(ManagedHost, pk=host_id)

    # Get commands available for this host filtered by user's role
    host_commands = host.available_commands
    allowed = request.user.allowed_commands

    if allowed:
        # Role has a command whitelist — filter to only allowed commands
        host_commands = host_commands.filter(command_name__in=allowed)

    # Group commands by category for the UI
    categories = {}
    for cmd in host_commands:
        cat = cmd.get_category_display()
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(cmd)

    # Open or resume a session for this user/host
    session, created = Session.objects.get_or_create(
        user=request.user,
        host=host,
        ended_at=None,
        defaults={'started_at': timezone.now()}
    )

    # Recent command logs for this session
    recent_logs = session.command_logs.order_by('-executed_at')[:20]

    context = {
        'host':        host,
        'categories':  categories,
        'session':     session,
        'recent_logs': recent_logs,
    }
    return render(request, 'hosts/host_detail.html', context)


@login_required
def host_command_log(request, host_id):
    """
    Returns recent command logs for a host as JSON.
    Used by the frontend to refresh the output panel.
    """
    host = get_object_or_404(ManagedHost, pk=host_id)
    session = Session.objects.filter(
        user=request.user,
        host=host,
        ended_at=None
    ).first()

    if not session:
        return JsonResponse({'logs': []})

    logs = session.command_logs.order_by('-executed_at')[:50]
    data = [
        {
            'command':    log.command_name,
            'args':       log.command_args,
            'output':     log.result_output,
            'duration':   log.duration_ms,
            'executed_at': log.executed_at.strftime('%H:%M:%S'),
        }
        for log in logs
    ]
    return JsonResponse({'logs': data})


@login_required
@require_POST
def close_session(request, session_id):
    """
    Close an active work session.
    """
    session = get_object_or_404(Session, pk=session_id, user=request.user)
    session.close(reason='user_closed')
    return JsonResponse({'status': 'closed'})


@login_required
@require_POST
def save_ticket_ref(request, session_id):
    """Update the ticket reference for a session."""
    import json
    session = get_object_or_404(Session, pk=session_id, user=request.user)
    data = json.loads(request.body)
    session.ticket_ref = data.get('ticket_ref', '')
    session.save(update_fields=['ticket_ref'])
    return JsonResponse({'status': 'saved'})


@login_required
@require_POST
def dispatch_command(request, host_id):
    """
    Receive a command from the web UI, log it, and forward
    it to the socket service via Redis.
    This is the bridge between Django and the socket service.
    """
    import json
    import time
    host = get_object_or_404(ManagedHost, pk=host_id)
    data = json.loads(request.body)

    command    = data.get('command', '').strip()
    args       = data.get('args', '').strip()
    session_id = data.get('session_id')

    if not command:
        return JsonResponse({'error': 'No command specified'}, status=400)

    session = get_object_or_404(Session, pk=session_id, user=request.user)

    # Build the full command string
    full_command = f"{command} {args}".strip() if args else command

    # TODO: Forward to socket service via Redis in next session
    # For now, record a placeholder log entry so the UI works
    start = time.time()

    log = CommandLog.objects.create(
        session      = session,
        user         = request.user,
        host         = host,
        command_name = command,
        command_args = args,
        result_output = f'[Command queued: {full_command}]\n'
                        f'Socket service bridge not yet connected.\n'
                        f'This will execute on {host.hostname} once Redis bridge is wired up.',
        duration_ms  = int((time.time() - start) * 1000),
    )

    logger.info(f"Command queued: {full_command} on {host.hostname} by {request.user}")

    return JsonResponse({
        'status':  'queued',
        'log_id':  str(log.id),
        'message': f'Command {full_command} queued for {host.hostname}',
    })
