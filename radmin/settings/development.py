"""
radmin/settings/development.py
Development overrides - never use in production.
"""

from .base import *

DEBUG = True

ALLOWED_HOSTS = ['localhost', '127.0.0.1', '0.0.0.0']

# Allow CAC auth to be bypassed in dev with a test user
CAC_DEV_BYPASS = True
CAC_DEV_EDIPI = '9999999999'

# Looser security for local dev
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

# Django debug toolbar (optional, install separately)
# INSTALLED_APPS += ['debug_toolbar']

# Log everything to console in dev
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'DEBUG',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}
