"""
apps/accounts/backends.py
CAC authentication backend.

Extracts the identifier and Distinguished Name from the client certificate
and looks up the corresponding pre-provisioned User record.

Supported certificate CN formats:
  DoD CAC:          LASTNAME.FIRSTNAME.MI.1234567890  (10-digit EDIPI)
  Ascendant Group:  LASTNAME.FIRSTNAME.MI.TAG-000001  (division-prefixed AGID)

Pre-provisioned accounts only — this backend does NOT create users on first
login. An administrator must provision the account before the certificate
will be accepted.
"""

import logging
import re
from django.contrib.auth.backends import BaseBackend
from django.contrib.auth import get_user_model

logger = logging.getLogger(__name__)

User = get_user_model()

# DoD EDIPI: exactly 10 digits
EDIPI_PATTERN = re.compile(r'^\d{10}$')

# Ascendant AGID: uppercase letters, hyphen, digits (e.g. TAG-000001)
AGID_PATTERN = re.compile(r'^[A-Z]{2,6}-\d{4,8}$')


class CACAuthBackend(BaseBackend):

    def authenticate(self, request, cert_data=None, **kwargs):
        if cert_data is None:
            return None

        try:
            identifier, dn, display_name = self._parse_certificate(cert_data)
        except Exception as e:
            logger.error(f"Failed to parse certificate: {e}")
            return None

        if not identifier:
            logger.warning("Could not extract EDIPI or AGID from certificate")
            return None

        # Pre-provisioned accounts only — look up, do not create
        try:
            user = User.objects.get(edipi=identifier)
        except User.DoesNotExist:
            logger.warning(
                f"Certificate presented for unknown identifier: {identifier} "
                f"— account not provisioned"
            )
            return None

        if not user.is_active:
            logger.warning(f"Inactive user attempted certificate login: {identifier}")
            return None

        # Update DN and display name if cert was reissued
        updated = False
        if user.distinguished_name != dn:
            user.distinguished_name = dn
            updated = True
        if display_name and user.display_name != display_name:
            user.display_name = display_name
            updated = True
        if updated:
            user.save()
            logger.info(f"Updated user record from certificate: {identifier}")

        logger.info(f"Certificate login successful: {identifier} - {display_name}")
        return user

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None

    def _parse_certificate(self, cert_data):
        """
        Parse PEM certificate data passed by nginx and extract the
        identifier (EDIPI or AGID), full DN, and display name.

        Handles both URL-encoded and raw PEM formats since nginx
        can pass the cert in either form.
        """
        from urllib.parse import unquote
        from cryptography import x509
        from cryptography.hazmat.backends import default_backend

        # URL-decode if nginx passed it encoded
        cert_pem = unquote(cert_data)

        # Ensure proper PEM formatting
        if '-----BEGIN CERTIFICATE-----' not in cert_pem:
            cert_pem = (
                '-----BEGIN CERTIFICATE-----\n' +
                cert_pem.replace(' ', '\n') +
                '\n-----END CERTIFICATE-----\n'
            )

        cert = x509.load_pem_x509_certificate(
            cert_pem.encode(), default_backend()
        )

        # Extract full Distinguished Name
        dn = cert.subject.rfc4514_string()

        # Extract CN
        cn_attrs = cert.subject.get_attributes_for_oid(x509.NameOID.COMMON_NAME)
        if not cn_attrs:
            raise ValueError("No CN found in certificate subject")

        cn = cn_attrs[0].value  # e.g. "MATTHEWS.JASON.B.TAG-000001"
        parts = cn.split('.')

        # Extract identifier from last CN segment
        identifier = None
        if parts:
            last = parts[-1]
            if EDIPI_PATTERN.match(last):
                identifier = last          # DoD EDIPI
                logger.debug(f"Parsed DoD EDIPI: {identifier}")
            elif AGID_PATTERN.match(last.upper()):
                identifier = last.upper()  # Ascendant AGID
                logger.debug(f"Parsed Ascendant AGID: {identifier}")
            else:
                logger.warning(f"CN last segment '{last}' matches neither EDIPI nor AGID pattern")

        # Build display name from CN: LASTNAME.FIRSTNAME... -> "Firstname Lastname"
        if len(parts) >= 2:
            display_name = f"{parts[1].capitalize()} {parts[0].capitalize()}"
        else:
            display_name = cn

        return identifier, dn, display_name
