"""
apps/diagnostics/urls.py
"""
from django.urls import path
from . import views

app_name = 'diagnostics'

urlpatterns = [
    path('rules/',                              views.list_rules,      name='list_rules'),
    path('findings/',                           views.list_findings,   name='list_findings'),
    path('findings/<uuid:host_id>/',            views.list_findings,   name='host_findings'),
    path('run/<uuid:host_id>/',                 views.run_diagnostics, name='run_diagnostics'),
    path('resolve/<uuid:finding_id>/',          views.resolve_finding, name='resolve_finding'),
]
