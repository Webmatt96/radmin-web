"""
apps/hosts/urls.py
"""

from django.urls import path
from . import views

app_name = 'hosts'

urlpatterns = [
    path('',                                        views.dashboard,         name='dashboard'),
    path('<uuid:host_id>/',                         views.host_detail,       name='host_detail'),
    path('<uuid:host_id>/logs/',                    views.host_command_log,  name='host_command_log'),
    path('<uuid:host_id>/command/',                 views.dispatch_command,  name='dispatch_command'),
    path('session/<uuid:session_id>/close/',        views.close_session,     name='close_session'),
    path('session/<uuid:session_id>/ticket/',       views.save_ticket_ref,   name='save_ticket_ref'),
]
