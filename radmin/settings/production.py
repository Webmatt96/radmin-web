"""
radmin/settings/production.py
Production overrides.
"""

from .base import *
import configparser
from pathlib import Path

_conf = configparser.ConfigParser()
_conf.read(Path(__file__).resolve().parent.parent.parent / 'radmin.conf')

DEBUG = False

ALLOWED_HOSTS = [
    h.strip()
    for h in _conf.get('django', 'allowed_hosts').split(',')
]

# Force HTTPS
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

CAC_DEV_BYPASS = False

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': '/var/log/radmin/radmin.log',
            'maxBytes': 10 * 1024 * 1024,
            'backupCount': 5,
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['file'],
        'level': 'INFO',
    },
}
