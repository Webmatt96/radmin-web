"""
apps/tickets/admin.py
"""

from django.contrib import admin
from .models import TicketIntegration, WorkLogExport


@admin.register(TicketIntegration)
class TicketIntegrationAdmin(admin.ModelAdmin):
    list_display   = ['name', 'system_name', 'base_url', 'auth_type', 'is_active', 'created_at']
    list_filter    = ['system_name', 'auth_type', 'is_active']
    search_fields  = ['name', 'base_url']
    readonly_fields = ['created_at', 'updated_at']

    fieldsets = (
        ('Integration', {'fields': ('name', 'system_name', 'base_url', 'is_active')}),
        ('Auth',        {'fields': ('auth_type', 'auth_config'),
                         'classes': ('collapse',),
                         'description': 'Auth config stored encrypted.'}),
        ('Metadata',    {'fields': ('created_by', 'created_at', 'updated_at')}),
    )


@admin.register(WorkLogExport)
class WorkLogExportAdmin(admin.ModelAdmin):
    list_display   = ['session', 'integration', 'external_ticket_id', 'status', 'exported_at', 'retry_count']
    list_filter    = ['status', 'integration']
    search_fields  = ['external_ticket_id', 'session__user__display_name']
    readonly_fields = ['session', 'integration', 'exported_content', 'exported_by',
                       'exported_at', 'created_at', 'retry_count']

    def has_add_permission(self, request):
        return False
