"""
apps/sessions/admin.py
"""

from django.contrib import admin
from .models import Session, CommandLog


class CommandLogInline(admin.TabularInline):
    model         = CommandLog
    extra         = 0
    readonly_fields = ['command_name', 'command_args', 'result_output', 'duration_ms', 'executed_at']
    fields        = ['executed_at', 'command_name', 'command_args', 'duration_ms']
    ordering      = ['executed_at']
    can_delete    = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    list_display   = ['user', 'host', 'ticket_ref', 'started_at', 'ended_at', 'is_active']
    list_filter    = ['host', 'termination_reason']
    search_fields  = ['user__display_name', 'host__hostname', 'ticket_ref']
    readonly_fields = ['started_at', 'ended_at', 'termination_reason']
    inlines        = [CommandLogInline]

    fieldsets = (
        ('Session',  {'fields': ('user', 'host', 'ticket_ref', 'notes')}),
        ('Timing',   {'fields': ('started_at', 'ended_at', 'termination_reason')}),
    )

    def is_active(self, obj):
        return obj.ended_at is None
    is_active.boolean = True
    is_active.short_description = 'Active'


@admin.register(CommandLog)
class CommandLogAdmin(admin.ModelAdmin):
    list_display   = ['command_name', 'host', 'user', 'executed_at', 'duration_ms']
    list_filter    = ['host', 'command_name']
    search_fields  = ['command_name', 'host__hostname', 'user__display_name']
    readonly_fields = ['session', 'user', 'host', 'command_name', 'command_args',
                       'result_output', 'exit_code', 'duration_ms', 'executed_at']

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
