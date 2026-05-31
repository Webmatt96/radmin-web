"""
apps/hosts/views.py
Dashboard and host detail views.
"""

import json
import logging
import time
import uuid
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.conf import settings
from .models import ManagedHost
from apps.commands.models import CommandDefinition
from apps.sessions.models import Session, CommandLog

logger = logging.getLogger(__name__)

# ── Redis ─────────────────────────────────────────────────────────────────────
try:
    import redis as redis_lib
    _redis = redis_lib.from_url(settings.REDIS_URL, decode_responses=True)
    _redis.ping()
    REDIS_AVAILABLE = True
    logger.info("Redis connected for command dispatch")
except Exception as e:
    REDIS_AVAILABLE = False
    _redis = None
    logger.warning(f"Redis not available: {e}")

COMMAND_TIMEOUT = 60  # seconds to wait for a result


# ── Dashboard ─────────────────────────────────────────────────────────────────

@login_required
def dashboard(request):
    hosts = ManagedHost.objects.all().order_by('environment', 'hostname')
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


# ── Host detail ───────────────────────────────────────────────────────────────

@login_required
def host_detail(request, host_id):
    host = get_object_or_404(ManagedHost, pk=host_id)

    host_commands = host.available_commands
    allowed = request.user.allowed_commands
    if allowed:
        host_commands = host_commands.filter(command_name__in=allowed)

    categories = {}
    for cmd in host_commands:
        cat = cmd.get_category_display()
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(cmd)

    # Auto-expire sessions older than 8 hours
    SESSION_MAX_AGE_HOURS = 8
    cutoff = timezone.now() - timezone.timedelta(hours=SESSION_MAX_AGE_HOURS)
    Session.objects.filter(
        user=request.user,
        host=host,
        ended_at=None,
        started_at__lt=cutoff
    ).update(
        ended_at=timezone.now(),
        termination_reason='timeout'
    )

    session, created = Session.objects.get_or_create(
        user=request.user,
        host=host,
        ended_at=None,
        defaults={'started_at': timezone.now()}
    )

    recent_logs = session.command_logs.order_by('-executed_at')[:20]

    # Recent unique ticket numbers used on this host for the dropdown
    recent_tickets = (
        Session.objects.filter(host=host)
        .exclude(ticket_ref='')
        .exclude(ticket_ref=None)
        .values_list('ticket_ref', flat=True)
        .distinct()
        .order_by('-started_at')[:20]
    )

    context = {
        'host':            host,
        'categories':      categories,
        'session':         session,
        'session_created': created,
        'recent_logs':     recent_logs,
        'recent_tickets':  recent_tickets,
        'redis_available': REDIS_AVAILABLE,
    }
    return render(request, 'hosts/host_detail.html', context)


# ── Command dispatch ──────────────────────────────────────────────────────────

@login_required
@require_POST
def dispatch_command(request, host_id):
    """
    Receive a command from the web UI.
    If Redis is available, publish to the socket service and wait for result.
    Otherwise log a placeholder.
    """
    host = get_object_or_404(ManagedHost, pk=host_id)
    data = json.loads(request.body)

    command    = data.get('command', '').strip()
    args       = data.get('args', '').strip()
    session_id = data.get('session_id')

    if not command:
        return JsonResponse({'error': 'No command specified'}, status=400)

    session = get_object_or_404(Session, pk=session_id, user=request.user)
    full_command = f"{command} {args}".strip() if args else command
    start = time.time()

    if REDIS_AVAILABLE:
        result = _dispatch_via_redis(host.hostname, command, args)
    else:
        result = (
            f'[Redis not available]\n'
            f'Command "{full_command}" could not be dispatched.\n'
            f'Ensure Redis is running and the socket service is connected.'
        )

    duration_ms = int((time.time() - start) * 1000)

    log = CommandLog.objects.create(
        session       = session,
        user          = request.user,
        host          = host,
        command_name  = command,
        command_args  = args,
        result_output = result,
        duration_ms   = duration_ms,
    )

    logger.info(f"Command '{full_command}' on {host.hostname} by {request.user} — {duration_ms}ms")

    return JsonResponse({
        'status':   'ok',
        'log_id':   str(log.id),
        'result':   result,
        'duration': duration_ms,
    })


def _dispatch_via_redis(hostname, command, args):
    """
    Publish command to Redis and wait for the socket service to return a result.
    Returns the result string, or an error message on timeout/failure.
    """
    request_id = str(uuid.uuid4())
    channel    = f'radmin:cmd:{hostname}'
    result_key = f'radmin:result:{hostname}:{request_id}'

    payload = json.dumps({
        'request_id': request_id,
        'command':    command,
        'args':       args,
    })

    try:
        _redis.publish(channel, payload)
        logger.debug(f"Published to {channel}: {payload}")
    except Exception as e:
        return f"Redis publish error: {e}"

    # Poll for result (socket service sets a Redis key when done)
    deadline = time.time() + COMMAND_TIMEOUT
    while time.time() < deadline:
        result = _redis.get(result_key)
        if result is not None:
            _redis.delete(result_key)
            return result
        time.sleep(0.1)  # poll every 100ms

    return f'Timeout — no response from {hostname} within {COMMAND_TIMEOUT}s.'


# ── Supporting endpoints ──────────────────────────────────────────────────────

@login_required
def host_command_log(request, host_id):
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
            'command':     log.command_name,
            'args':        log.command_args,
            'output':      log.result_output,
            'duration':    log.duration_ms,
            'executed_at': log.executed_at.strftime('%H:%M:%S'),
        }
        for log in logs
    ]
    return JsonResponse({'logs': data})


@login_required
@require_POST
def close_session(request, session_id):
    session = get_object_or_404(Session, pk=session_id, user=request.user)
    session.close(reason='user_closed')
    return JsonResponse({'status': 'closed'})


@login_required
def session_worklog(request, session_id):
    """Generate a formatted work log for a session."""
    session = get_object_or_404(Session, pk=session_id, user=request.user)
    worklog = session.generate_work_log()
    return JsonResponse({'worklog': worklog})


@login_required
@require_POST
def save_ticket_ref(request, session_id):
    """Update the ticket reference for a session."""
    session = get_object_or_404(Session, pk=session_id, user=request.user)
    data = json.loads(request.body)
    session.ticket_ref = data.get('ticket_ref', '')
    session.save(update_fields=['ticket_ref'])
    return JsonResponse({'status': 'saved'})


@login_required
def host_session_history(request, host_id):
    """
    Show all past sessions for a host.
    Allows technicians to review and retrieve work logs from previous sessions.
    """
    host = get_object_or_404(ManagedHost, pk=host_id)
    sessions = Session.objects.filter(
        host=host
    ).order_by('-started_at').select_related('user')[:50]

    context = {
        'host':     host,
        'sessions': sessions,
    }
    return render(request, 'hosts/session_history.html', context)


@login_required
def past_session_worklog(request, session_id):
    """Return work log for any session — not just the current user's."""
    session = get_object_or_404(Session, pk=session_id)
    worklog = session.generate_work_log()
    return JsonResponse({'worklog': worklog})


# ── Host status update (called by Redis status listener) ─────────────────────

def update_host_status(hostname, online, ip_address=None):
    """Called by a background thread listening to radmin:host:status."""
    try:
        host, created = ManagedHost.objects.get_or_create(
            hostname=hostname,
            defaults={
                'ip_address':   ip_address or '',
                'os_type':      'windows' if hostname.upper().startswith('WIN-') else 'linux',
                'environment':  'lab',
                'description':  'Auto-registered on first connection',
            }
        )
        host.is_online = online
        if online:
            host.last_seen = timezone.now()
        host.save(update_fields=['is_online', 'last_seen'])

        if created:
            logger.info(f"Auto-registered new host: {hostname}")
        logger.info(f"Host status updated: {hostname} → {'online' if online else 'offline'}")
    except Exception as e:
        logger.error(f"Error updating host status: {e}")
