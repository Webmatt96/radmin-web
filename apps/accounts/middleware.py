"""
apps/accounts/middleware.py
CAC authentication middleware.

In production: Nginx terminates TLS, extracts the client certificate,
and passes it to Django via HTTP headers. This middleware reads those
headers and authenticates the user.

In development: A bypass mode allows testing without a physical CAC.
Set CAC_DEV_BYPASS = True in development settings.
"""

import logging
from django.conf import settings
from django.contrib.auth import login
from django.shortcuts import redirect
from django.urls import reverse

logger = logging.getLogger(__name__)

# Paths that don't require authentication
PUBLIC_PATHS = [
    '/accounts/login/',
    '/accounts/cac-required/',
    '/admin/',
    '/static/',
]


class CACAuthMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Skip auth for public paths
        if any(request.path.startswith(p) for p in PUBLIC_PATHS):
            return self.get_response(request)

        # If already authenticated, continue
        if request.user.is_authenticated:
            return self.get_response(request)

        # Development bypass
        if getattr(settings, 'CAC_DEV_BYPASS', False):
            self._dev_login(request)
            return self.get_response(request)

        # Production: check for CAC certificate from Nginx
        cert_verified = request.META.get(settings.CAC_VERIFY_HEADER, '')
        cert_data     = request.META.get(settings.CAC_CERT_HEADER, '')

        if cert_verified != 'SUCCESS' or not cert_data:
            logger.warning(f"No valid CAC cert for {request.path} from {request.META.get('REMOTE_ADDR')}")
            return redirect(reverse('accounts:cac_required'))

        # Attempt to authenticate with the certificate
        from django.contrib.auth import authenticate
        user = authenticate(request, cert_data=cert_data)

        if user is None:
            logger.warning("CAC cert presented but user not found or inactive")
            return redirect(reverse('accounts:cac_required'))

        login(request, user, backend='apps.accounts.backends.CACAuthBackend')
        logger.info(f"CAC login: {user} from {request.META.get('REMOTE_ADDR')}")

        return self.get_response(request)

    def _dev_login(self, request):
        """
        Bypass CAC in development by auto-logging in a test user.
        Creates the user if it doesn't exist.
        """
        from django.contrib.auth import get_user_model
        User = get_user_model()

        edipi = getattr(settings, 'CAC_DEV_EDIPI', '9999999999')

        try:
            user = User.objects.get(edipi=edipi)
        except User.DoesNotExist:
            user = User.objects.create_superuser(
                edipi=edipi,
                distinguished_name='CN=DEV USER,OU=TEST,O=U.S. Government,C=US',
                display_name='Dev User',
                email='dev@localhost',
                is_staff=True,
                is_superuser=True,
            )
            logger.info(f"Created dev bypass user: {edipi}")

        if not request.user.is_authenticated:
            login(request, user, backend='apps.accounts.backends.CACAuthBackend')
            logger.debug(f"Dev bypass login: {user}")
