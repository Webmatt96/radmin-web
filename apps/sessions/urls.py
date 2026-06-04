"""
apps/sessions/urls.py
"""
from django.urls import path
from . import views

app_name = 'sessions'

urlpatterns = [
    path('',                              views.session_list,     name='session_list'),
    path('<uuid:session_id>/work-log/',   views.session_work_log, name='work_log'),
]
