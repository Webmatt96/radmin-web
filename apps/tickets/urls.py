"""
apps/tickets/urls.py
"""
from django.urls import path
from . import views

app_name = 'tickets'

urlpatterns = [
    path('export/<uuid:session_id>/',           views.export_session,    name='export_session'),
    path('fetch/',                              views.fetch_tickets,     name='fetch_tickets'),
    path('integrations/',                       views.list_integrations, name='list_integrations'),
    path('integrations/<uuid:integration_id>/test/', views.test_integration, name='test_integration'),
]
