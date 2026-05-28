"""
apps/commands/admin.py
"""

from django.contrib import admin
from .models import CommandDefinition


@admin.register(CommandDefinition)
class CommandDefinitionAdmin(admin.ModelAdmin):
    list_display   = ['display_name', 'command_name', 'category', 'platform',
                      'takes_argument', 'requires_elevation', 'is_active']
    list_filter    = ['category', 'platform', 'requires_elevation', 'is_active']
    search_fields  = ['command_name', 'display_name', 'description']
    readonly_fields = ['created_at', 'updated_at']

    fieldsets = (
        ('Identity',    {'fields': ('command_name', 'display_name', 'description')}),
        ('Classification', {'fields': ('category', 'platform')}),
        ('Behavior',    {'fields': ('takes_argument', 'argument_hint', 'requires_elevation', 'is_active')}),
        ('Timestamps',  {'fields': ('created_at', 'updated_at')}),
    )
