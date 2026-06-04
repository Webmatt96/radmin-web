"""
apps/sessions/views.py
Session detail and work log views.
"""
import logging
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_http_methods

from .models import Session

logger = logging.getLogger(__name__)


@login_required
@require_http_methods(['GET'])
def session_work_log(request, session_id):
    """
    Return the generated work log for a session.
    Supports both JSON and plain text formats.
    """
    session = get_object_or_404(Session, id=session_id)
    fmt     = request.GET.get('format', 'json')

    work_log = session.generate_work_log()

    if fmt == 'text':
        return HttpResponse(work_log, content_type='text/plain')

    return JsonResponse({
        'session_id':  str(session.id),
        'host':        session.host.hostname,
        'operator':    session.user.display_name or session.user.edipi,
        'started_at':  session.started_at.isoformat(),
        'ended_at':    session.ended_at.isoformat() if session.ended_at else None,
        'ticket_ref':  session.ticket_ref,
        'work_log':    work_log,
    })


@login_required
@require_http_methods(['GET'])
def session_list(request):
    """
    Return recent sessions, optionally filtered by host.
    """
    host_id  = request.GET.get('host_id')
    limit    = int(request.GET.get('limit', 25))

    sessions = Session.objects.select_related('user', 'host').order_by('-started_at')
    if host_id:
        sessions = sessions.filter(host_id=host_id)

    sessions = sessions[:limit]

    return JsonResponse({
        'sessions': [
            {
                'id':         str(s.id),
                'host':       s.host.hostname,
                'operator':   s.user.display_name or s.user.edipi,
                'started_at': s.started_at.isoformat(),
                'ended_at':   s.ended_at.isoformat() if s.ended_at else None,
                'ticket_ref': s.ticket_ref,
                'is_active':  s.is_active,
                'duration':   str(s.duration) if s.duration else None,
            }
            for s in sessions
        ]
    })
