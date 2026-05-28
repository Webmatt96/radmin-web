"""
apps/insights/admin.py
"""

from django.contrib import admin
from .models import Insight, UserPerformanceSnapshot


@admin.register(Insight)
class InsightAdmin(admin.ModelAdmin):
    list_display   = ['title', 'host', 'category', 'severity', 'occurrence_count',
                      'first_seen', 'last_seen', 'is_resolved']
    list_filter    = ['category', 'severity', 'is_resolved']
    search_fields  = ['title', 'description', 'host__hostname']
    readonly_fields = ['first_seen', 'last_seen', 'occurrence_count']

    fieldsets = (
        ('Insight',        {'fields': ('host', 'category', 'severity', 'title', 'description', 'recommendation')}),
        ('Occurrence',     {'fields': ('occurrence_count', 'first_seen', 'last_seen', 'supporting_log_ids')}),
        ('Resolution',     {'fields': ('is_resolved', 'resolved_at', 'resolved_by')}),
    )


@admin.register(UserPerformanceSnapshot)
class UserPerformanceSnapshotAdmin(admin.ModelAdmin):
    list_display   = ['user', 'period_start', 'period_end', 'session_count',
                      'command_count', 'unique_hosts_touched', 'work_logs_exported']
    list_filter    = ['user']
    search_fields  = ['user__display_name', 'user__edipi']
    readonly_fields = ['generated_at', 'command_breakdown', 'host_breakdown']

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
