"""
apps/credentials/admin.py
"""

from django.contrib import admin
from .models import CredentialPackage, HostCredential


class HostCredentialInline(admin.TabularInline):
    model         = HostCredential
    extra         = 0
    readonly_fields = ['host', 'status', 'deployed_at', 'deployed_by', 'retry_count', 'error_message']
    fields        = ['host', 'status', 'deployed_at', 'retry_count', 'error_message']
    can_delete    = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(CredentialPackage)
class CredentialPackageAdmin(admin.ModelAdmin):
    list_display   = ['name', 'version', 'status', 'valid_from', 'valid_until', 'is_expired', 'created_by']
    list_filter    = ['status']
    search_fields  = ['name']
    readonly_fields = ['created_at', 'is_expired']
    inlines        = [HostCredentialInline]

    fieldsets = (
        ('Package',   {'fields': ('name', 'version', 'status', 'notes')}),
        ('Validity',  {'fields': ('valid_from', 'valid_until', 'is_expired')}),
        ('Secrets',   {'fields': ('cert_data', 'shared_secret'),
                       'classes': ('collapse',),
                       'description': 'Stored encrypted. Handle with care.'}),
        ('Metadata',  {'fields': ('created_by', 'created_at')}),
    )

    def is_expired(self, obj):
        return obj.is_expired
    is_expired.boolean = True


@admin.register(HostCredential)
class HostCredentialAdmin(admin.ModelAdmin):
    list_display  = ['host', 'package', 'status', 'deployed_at', 'retry_count']
    list_filter   = ['status']
    search_fields = ['host__hostname', 'package__name']
    readonly_fields = ['created_at', 'updated_at']
