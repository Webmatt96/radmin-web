"""
radmin/urls.py
Root URL configuration.
"""
from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect

urlpatterns = [
    path('',          lambda request: redirect('hosts:dashboard'), name='home'),
    path('admin/',    admin.site.urls),
    path('accounts/', include('apps.accounts.urls')),
    path('hosts/',    include('apps.hosts.urls')),
    path('sessions/', include('apps.sessions.urls')),
    path('tickets/',  include('apps.tickets.urls')),
    path('diagnostics/', include('apps.diagnostics.urls')),
]
