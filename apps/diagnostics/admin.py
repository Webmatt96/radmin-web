"""
apps/diagnostics/admin.py
"""
from django.contrib import admin
from .models import DiagnosticRule, DiagnosticFinding, RemediationLog


@admin.register(DiagnosticRule)
class DiagnosticRuleAdmin(admin.ModelAdmin):
    list_display  = ['rule_id', 'name', 'version', 'severity', 'platform', 'category', 'autonomous', 'status']
    list_filter   = ['severity', 'platform', 'category', 'autonomous', 'status']
    search_fields = ['rule_id', 'name']
    ordering      = ['rule_id']


@admin.register(DiagnosticFinding)
class DiagnosticFindingAdmin(admin.ModelAdmin):
    list_display  = ['rule', 'host', 'severity', 'confidence', 'status', 'detected_at']
    list_filter   = ['severity', 'confidence', 'status']
    search_fields = ['host__hostname', 'rule__rule_id', 'probable_cause']
    ordering      = ['-detected_at']
    readonly_fields = ['detected_at', 'resolved_at', 'rule_version']


@admin.register(RemediationLog)
class RemediationLogAdmin(admin.ModelAdmin):
    list_display  = ['finding', 'action', 'outcome', 'trigger', 'rule_id', 'rule_version', 'executed_at']
    list_filter   = ['outcome', 'trigger']
    search_fields = ['finding__host__hostname', 'rule_id', 'action']
    ordering      = ['-executed_at']
    readonly_fields = ['executed_at', 'rule_id', 'rule_version']
