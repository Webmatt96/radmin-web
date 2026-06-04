"""
apps/tickets/views.py
Ticket export and integration management views.
"""
import json
import logging

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .models import TicketIntegration, WorkLogExport
from .integrations.base import get_exporter
from apps.sessions.models import Session as RAdminSession

logger = logging.getLogger(__name__)


@csrf_exempt
@login_required
@require_http_methods(['POST'])
def export_session(request, session_id):
    """
    Export a session work log to a ticketing system.

    POST body (JSON):
        integration_id  - UUID of the TicketIntegration to use
        ticket_id       - Optional existing ticket ID to append to
                          (overrides session.ticket_ref)

    Returns JSON: {success, ticket_id, message}
    """
    session = get_object_or_404(RAdminSession, id=session_id)

    try:
        body           = json.loads(request.body)
        integration_id = body.get('integration_id')
        ticket_id      = body.get('ticket_id', '').strip()
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({'success': False, 'message': 'Invalid request body'}, status=400)

    if not integration_id:
        return JsonResponse({'success': False, 'message': 'integration_id is required'}, status=400)

    integration = get_object_or_404(
        TicketIntegration, id=integration_id, is_active=True
    )

    # Override ticket_ref if caller specified one
    if ticket_id:
        session.ticket_ref = ticket_id

    # Create export record
    export_record = WorkLogExport.objects.create(
        session          = session,
        integration      = integration,
        exported_content = session.generate_work_log(),
        exported_by      = request.user,
        status           = 'pending',
    )

    try:
        exporter = get_exporter(integration)
        exporter.export_session(session, export_record)

        return JsonResponse({
            'success':   True,
            'ticket_id': export_record.external_ticket_id,
            'message':   f"Exported to {integration.name}: {export_record.external_ticket_id}",
        })

    except Exception as e:
        logger.error(f"Export failed for session {session_id}: {e}")
        return JsonResponse({
            'success': False,
            'message': str(e),
        }, status=500)


@login_required
@require_http_methods(['GET'])
def fetch_tickets(request):
    """
    Fetch open tickets from an active integration.

    Query params:
        integration_id  - UUID of the TicketIntegration
        q               - Optional search query

    Returns JSON: {tickets: [{id, number, title, status, url}]}
    """
    integration_id = request.GET.get('integration_id')
    query          = request.GET.get('q', '')

    if not integration_id:
        # Return tickets from all active integrations
        integrations = TicketIntegration.objects.filter(is_active=True)
    else:
        integrations = TicketIntegration.objects.filter(
            id=integration_id, is_active=True
        )

    all_tickets = []
    for integration in integrations:
        try:
            exporter = get_exporter(integration)
            tickets  = exporter.fetch_tickets(query=query)
            for t in tickets:
                t['integration'] = integration.name
                t['system']      = integration.system_name
            all_tickets.extend(tickets)
        except Exception as e:
            logger.error(f"fetch_tickets failed for {integration.name}: {e}")

    return JsonResponse({'tickets': all_tickets})


@login_required
@require_http_methods(['GET'])
def list_integrations(request):
    """
    Return all active ticket integrations.
    Used to populate the export modal's integration selector.
    """
    integrations = TicketIntegration.objects.filter(is_active=True).values(
        'id', 'name', 'system_name', 'base_url'
    )
    return JsonResponse({'integrations': list(integrations)})


@csrf_exempt
@login_required
@require_http_methods(['POST'])
def test_integration(request, integration_id):
    """
    Test connectivity for a ticket integration.
    Returns JSON: {success, message}
    """
    integration = get_object_or_404(TicketIntegration, id=integration_id)

    try:
        exporter = get_exporter(integration)
        ok       = exporter.test_connection()
        return JsonResponse({
            'success': ok,
            'message': 'Connection successful' if ok else 'Connection failed',
        })
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)
