"""
apps/accounts/backends.py
CAC authentication backend.

Extracts the EDIPI and Distinguished Name from the client certificate
and looks up or creates the corresponding User record.

Certificate DN format for DoD CAC:
CN=LASTNAME.FIRSTNAME.MI.EDIPI,OU=USA,OU=PKI,OU=DoD,O=U.S. Government,C=US
"""

import logging
import re
from django.contrib.auth.backends import BaseBackend
from django.contrib.auth import get_user_model

logger = logging.getLogger(__name__)

User = get_user_model()


class CACAuthBackend(BaseBackend):

    def authenticate(self, request, cert_data=None, **kwargs):
        if cert_data is None:
            return None

        try:
            edipi, dn, display_name = self._parse_certificate(cert_data)
        except Exception as e:
            logger.error(f"Failed to parse CAC certificate: {e}")
            return None

        if not edipi:
            logger.warning("Could not extract EDIPI from certificate")
            return None

        try:
            user, created = User.objects.get_or_create(
                edipi=edipi,
                defaults={
                    'distinguished_name': dn,
                    'display_name':       display_name,
                    'is_active':          True,
                }
            )

            if created:
                user.set_unusable_password()
                user.save()
                logger.info(f"Created new user from CAC: {edipi} - {display_name}")
            else:
                # Update DN and display name in case cert was reissued
                updated = False
                if user.distinguished_name != dn:
                    user.distinguished_name = dn
                    updated = True
                if user.display_name != display_name:
                    user.display_name = display_name
                    updated = True
                if updated:
                    user.save()

            if not user.is_active:
                logger.warning(f"Inactive user attempted CAC login: {edipi}")
                return None

            return user

        except Exception as e:
            logger.error(f"Database error during CAC authentication: {e}")
            return None

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None

    def _parse_certificate(self, cert_data):
        """
        Parse the PEM certificate data passed by Nginx and extract
        the EDIPI, full DN, and display name.

        The CN field of a DoD CAC certificate follows the format:
        LASTNAME.FIRSTNAME.MI.EDIPI

        This method handles both URL-encoded and raw PEM formats
        since Nginx can pass the cert in either form.
        """
        from urllib.parse import unquote
        from cryptography import x509
        from cryptography.hazmat.backends import default_backend
        import base64

        # URL-decode if Nginx passed it encoded
        cert_pem = unquote(cert_data)

        # Ensure proper PEM formatting
        if '-----BEGIN CERTIFICATE-----' not in cert_pem:
            # Raw base64 — wrap it
            cert_pem = (
                '-----BEGIN CERTIFICATE-----\n' +
                cert_pem.replace(' ', '\n') +
                '\n-----END CERTIFICATE-----\n'
            )

        cert = x509.load_pem_x509_certificate(
            cert_pem.encode(), default_backend()
        )

        # Extract the full Distinguished Name
        dn = cert.subject.rfc4514_string()

        # Extract CN
        cn_attr = cert.subject.get_attributes_for_oid(
            x509.NameOID.COMMON_NAME
        )
        if not cn_attr:
            raise ValueError("No CN found in certificate subject")

        cn = cn_attr[0].value  # e.g. "DOE.JOHN.A.1234567890"

        # Parse EDIPI (last segment of CN, 10 digits)
        parts = cn.split('.')
        edipi = parts[-1] if parts[-1].isdigit() and len(parts[-1]) == 10 else None

        # Build display name from CN parts
        if len(parts) >= 2:
            display_name = f"{parts[1]} {parts[0]}".title()
        else:
            display_name = cn

        return edipi, dn, display_name
