"""
radmin/settings/base.py
Shared settings inherited by all environments.
"""

import os
import configparser
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# ── Load radmin.conf ──────────────────────────────────────────────────────────
_conf = configparser.ConfigParser()
_conf_path = BASE_DIR / 'radmin.conf'
if not _conf_path.exists():
    raise FileNotFoundError(
        f"radmin.conf not found at {_conf_path}. "
        "Copy radmin.conf.example to radmin.conf and fill in your values."
    )
_conf.read(_conf_path)

# ── Core ──────────────────────────────────────────────────────────────────────
SECRET_KEY = _conf.get('django', 'secret_key')
ROOT_URLCONF = 'radmin.urls'
WSGI_APPLICATION = 'radmin.wsgi.application'
ASGI_APPLICATION = 'radmin.asgi.application'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

AUTH_USER_MODEL = 'accounts.User'

# ── Apps ──────────────────────────────────────────────────────────────────────
DJANGO_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

THIRD_PARTY_APPS = [
    'rest_framework',
    'channels',
]

LOCAL_APPS = [
    'apps.accounts',
    'apps.hosts',
    'apps.sessions',
    'apps.commands',
    'apps.tickets',
    'apps.credentials',
    'apps.insights',
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

# ── Middleware ────────────────────────────────────────────────────────────────
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'apps.accounts.middleware.CACAuthMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# ── Templates ─────────────────────────────────────────────────────────────────
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'frontend' / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

# ── Database ──────────────────────────────────────────────────────────────────
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME':     _conf.get('infrastructure', 'postgres_db'),
        'USER':     _conf.get('infrastructure', 'postgres_user'),
        'PASSWORD': _conf.get('infrastructure', 'postgres_password'),
        'HOST':     _conf.get('infrastructure', 'postgres_host'),
        'PORT':     _conf.get('infrastructure', 'postgres_port'),
    }
}

# ── Cache / Channel layer (Redis) ─────────────────────────────────────────────
REDIS_URL = _conf.get('infrastructure', 'redis_url')

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': REDIS_URL,
    }
}

CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            'hosts': [REDIS_URL],
        },
    },
}

# ── Celery ────────────────────────────────────────────────────────────────────
CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'UTC'

# ── Authentication ────────────────────────────────────────────────────────────
AUTHENTICATION_BACKENDS = [
    'apps.accounts.backends.CACAuthBackend',
    'django.contrib.auth.backends.ModelBackend',
]

LOGIN_URL = '/accounts/login/'
LOGIN_REDIRECT_URL = '/hosts/'
LOGOUT_REDIRECT_URL = '/accounts/login/'

# ── REST Framework ────────────────────────────────────────────────────────────
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
}

# ── Static files ──────────────────────────────────────────────────────────────
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'frontend' / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

# ── Internationalization ──────────────────────────────────────────────────────
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# ── Security ──────────────────────────────────────────────────────────────────
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_HTTPONLY = True
X_FRAME_OPTIONS = 'DENY'
SECURE_CONTENT_TYPE_NOSNIFF = True

# ── CAC / PKI settings ────────────────────────────────────────────────────────
CAC_CERT_HEADER = 'HTTP_X_SSL_CLIENT_CERT'
CAC_VERIFY_HEADER = 'HTTP_X_SSL_CLIENT_VERIFY'
DOD_PKI_CA_BUNDLE = _conf.get('pki', 'ca_bundle_path', fallback=None)
