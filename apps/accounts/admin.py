"""
apps/accounts/admin.py
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, Role


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display  = ['name', 'description']
    search_fields = ['name']


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display   = ['display_name', 'edipi', 'email', 'role', 'is_active', 'last_login']
    list_filter    = ['is_active', 'role', 'is_staff']
    search_fields  = ['display_name', 'edipi', 'email']
    ordering       = ['display_name']
    readonly_fields = ['last_login', 'created_at']

    fieldsets = (
        ('Identity',     {'fields': ('edipi', 'distinguished_name', 'display_name', 'email')}),
        ('Permissions',  {'fields': ('role', 'is_active', 'is_staff', 'is_superuser')}),
        ('Activity',     {'fields': ('last_login', 'created_at')}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields':  ('edipi', 'distinguished_name', 'display_name', 'email', 'role'),
        }),
    )

    # CAC users have no password
    filter_horizontal = ()
