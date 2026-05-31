"""
apps/hosts/apps.py
Starts the Redis host status listener when Django starts.
"""

from django.apps import AppConfig


class HostsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.hosts'

    def ready(self):
        """Start the Redis host status listener in a background thread."""
        import threading
        from django.conf import settings

        def status_listener():
            try:
                import redis as redis_lib
                import json
                r = redis_lib.from_url(settings.REDIS_URL, decode_responses=True)
                pubsub = r.pubsub()
                pubsub.subscribe('radmin:host:status')

                for message in pubsub.listen():
                    if message['type'] != 'message':
                        continue
                    try:
                        data = json.loads(message['data'])
                        hostname   = data.get('hostname')
                        online     = data.get('online', False)
                        ip_address = data.get('ip_address', '')
                        if hostname:
                            from apps.hosts.views import update_host_status
                            update_host_status(hostname, online, ip_address)
                    except Exception as e:
                        import logging
                        logging.getLogger(__name__).error(f"Status listener error: {e}")
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning(f"Redis status listener not started: {e}")

        t = threading.Thread(target=status_listener, daemon=True)
        t.start()
