"""
radmin/settings/production.py
Production overrides.
"""
from .base import *
import configparser
from pathlib import Path

_conf = configparser.RawConfigParser()
_conf.read(Path(__file__).resolve().parent.parent.parent / 'radmin.conf')

DEBUG = False

ALLOWED_HOSTS = [
    h.strip()
    for h in _conf.get('django', 'allowed_hosts').split(',')
]

# ── Proxy configuration ────────────────────────────────────────────────────
# nginx terminates TLS and proxies to gunicorn over HTTP.
# These settings tell Django to trust the X-Forwarded-Proto header
# from nginx so it knows requests are actually HTTPS.
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
USE_X_FORWARDED_HOST    = True

# ── HTTPS enforcement ──────────────────────────────────────────────────────
# Do NOT set SECURE_SSL_REDIRECT here — nginx handles the HTTP→HTTPS
# redirect already. Setting it in Django causes infinite redirect loops
# because Django sees requests arriving from nginx as plain HTTP.
SESSION_COOKIE_SECURE          = True
CSRF_COOKIE_SECURE             = True
SECURE_HSTS_SECONDS            = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD            = True

# ── CAC auth ──────────────────────────────────────────────────────────────
CAC_DEV_BYPASS = False

# ── Logging ───────────────────────────────────────────────────────────────
LOGGING = {
    'version':                  1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style':  '{',
        },
    },
    'handlers': {
        'file': {
            'class':       'logging.handlers.RotatingFileHandler',
            'filename':    '/var/log/radmin/radmin.log',
            'maxBytes':    10 * 1024 * 1024,
            'backupCount': 5,
            'formatter':   'verbose',
        },
        'console': {
            'class':     'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['file', 'console'],
        'level':    'INFO',
    },
}
