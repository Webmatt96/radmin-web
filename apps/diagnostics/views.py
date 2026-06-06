"""
apps/diagnostics/views.py
Diagnostic engine API endpoints.
"""
import logging
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from apps.hosts.models import ManagedHost
from .models import DiagnosticFinding, DiagnosticRule, RemediationLog
from .engine import DiagnosticEngine
from .collector import CommandCollector

logger = logging.getLogger(__name__)


@csrf_exempt
@login_required
@require_http_methods(['POST'])
def run_diagnostics(request, host_id):
    """
    Trigger a diagnostic scan on a specific host.
    Collects data, runs all applicable rules, returns findings.

    POST body (JSON): optional
        rules: list of rule IDs to run (default: all applicable)
    """
    host = get_object_or_404(ManagedHost, id=host_id)

    if not host.is_online:
        return JsonResponse({
            'success': False,
            'message': f"Host {host.hostname} is offline"
        }, status=400)

    try:
        # Load applicable rules to determine what to collect
        engine = DiagnosticEngine(host=host, collected_data={}, triggered_by=request.user)
        rules  = engine._load_rules()

        if not rules:
            return JsonResponse({
                'success':  True,
                'findings': [],
                'message':  'No applicable rules found for this host'
            })

        # Build the list of commands to collect
        commands = set()
        for rule_def in rules:
            for item in rule_def.get('collect', []):
                commands.add(item['command'])

        # Collect data from the host
        collector      = CommandCollector(host, timeout=30)
        collected_data = collector.collect(list(commands))

        # Run the engine
        engine.collected_data = collected_data
        findings = engine.run()

        return JsonResponse({
            'success':  True,
            'host':     host.hostname,
            'rules_run': len(rules),
            'findings': [
                {
                    'id':            str(f.id),
                    'rule_id':       f.rule.rule_id,
                    'rule_name':     f.rule.name,
                    'severity':      f.severity,
                    'confidence':    f.confidence,
                    'probable_cause': f.probable_cause,
                    'recommendation': f.recommendation,
                    'status':        f.status,
                    'detected_at':   f.detected_at.isoformat(),
                }
                for f in findings
            ]
        })

    except Exception as e:
        logger.error(f"Diagnostic scan failed for {host.hostname}: {e}")
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


@login_required
@require_http_methods(['GET'])
def list_findings(request, host_id=None):
    """
    List diagnostic findings, optionally filtered by host.
    Query params: status, severity, limit
    """
    findings = DiagnosticFinding.objects.select_related('rule', 'host')

    if host_id:
        findings = findings.filter(host_id=host_id)

    status   = request.GET.get('status')
    severity = request.GET.get('severity')
    limit    = int(request.GET.get('limit', 50))

    if status:
        findings = findings.filter(status=status)
    if severity:
        findings = findings.filter(severity=severity)

    findings = findings[:limit]

    return JsonResponse({
        'findings': [
            {
                'id':             str(f.id),
                'rule_id':        f.rule.rule_id,
                'rule_name':      f.rule.name,
                'host':           f.host.hostname,
                'severity':       f.severity,
                'confidence':     f.confidence,
                'probable_cause': f.probable_cause,
                'recommendation': f.recommendation,
                'status':         f.status,
                'detected_at':    f.detected_at.isoformat(),
                'resolved_at':    f.resolved_at.isoformat() if f.resolved_at else None,
            }
            for f in findings
        ]
    })


@login_required
@require_http_methods(['GET'])
def list_rules(request):
    """List all loaded diagnostic rules."""
    rules = DiagnosticRule.objects.all()
    return JsonResponse({
        'rules': [
            {
                'id':          str(r.id),
                'rule_id':     r.rule_id,
                'name':        r.name,
                'version':     r.version,
                'severity':    r.severity,
                'platform':    r.platform,
                'category':    r.category,
                'autonomous':  r.autonomous,
                'status':      r.status,
            }
            for r in rules
        ]
    })


@csrf_exempt
@login_required
@require_http_methods(['POST'])
def resolve_finding(request, finding_id):
    """Mark a finding as resolved or dismissed."""
    import json
    finding = get_object_or_404(DiagnosticFinding, id=finding_id)
    try:
        body   = json.loads(request.body)
        status = body.get('status', 'dismissed')
        if status not in ('remediated', 'dismissed'):
            return JsonResponse({'success': False, 'message': 'Invalid status'}, status=400)
        finding.resolve(status)
        return JsonResponse({'success': True, 'status': finding.status})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)
