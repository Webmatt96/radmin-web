"""
apps/hosts/admin.py
"""

from django.contrib import admin
from .models import ManagedHost, HostCommand


class HostCommandInline(admin.TabularInline):
    model       = HostCommand
    extra       = 0
    fields      = ['command_name', 'category', 'description', 'requires_elevation', 'is_active']
    ordering    = ['category', 'command_name']


@admin.register(ManagedHost)
class ManagedHostAdmin(admin.ModelAdmin):
    list_display   = ['hostname', 'ip_address', 'os_type', 'environment', 'is_online', 'last_seen']
    list_filter    = ['os_type', 'environment', 'is_online']
    search_fields  = ['hostname', 'ip_address', 'description']
    readonly_fields = ['registered_at', 'last_seen']
    inlines        = [HostCommandInline]

    fieldsets = (
        ('Identity',     {'fields': ('hostname', 'ip_address', 'description')}),
        ('Classification', {'fields': ('os_type', 'environment')}),
        ('Status',       {'fields': ('is_online', 'last_seen', 'registered_at', 'registered_by')}),
    )


@admin.register(HostCommand)
class HostCommandAdmin(admin.ModelAdmin):
    list_display  = ['command_name', 'host', 'category', 'requires_elevation', 'is_active']
    list_filter   = ['category', 'requires_elevation', 'is_active']
    search_fields = ['command_name', 'host__hostname']
