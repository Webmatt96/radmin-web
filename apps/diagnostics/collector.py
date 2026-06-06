"""
apps/diagnostics/collector.py
Command collector for the diagnostic engine.

Sends commands to managed hosts via the existing Redis bridge
and waits for results. Reuses the same infrastructure as the
web UI command execution — no new communication channels needed.
"""

import json
import time
import uuid
import logging
import redis as redis_lib

from django.conf import settings

logger = logging.getLogger(__name__)

# Redis connection — reuse the existing infrastructure config
REDIS_URL   = getattr(settings, 'REDIS_URL', 'redis://localhost:6379/0')
RESULT_TTL  = 60   # seconds to wait for a result
POLL_INTERVAL = 0.5


class CollectionError(Exception):
    pass


class CommandCollector:
    """
    Sends commands to a managed host via the Redis bridge and
    returns the output. Used by the diagnostic engine to collect
    data for rule evaluation.
    """

    def __init__(self, host, timeout=30):
        """
        host:    ManagedHost instance
        timeout: seconds to wait for command result
        """
        self.host     = host
        self.timeout  = timeout
        self._redis   = redis_lib.from_url(REDIS_URL, decode_responses=True)

    def collect(self, commands: list) -> dict:
        """
        Run a list of commands and return results as a dict.

        commands: list of command strings
        returns:  dict of {command: output}
        """
        results = {}
        for command in commands:
            try:
                output = self.run_command(command)
                results[command] = output
                logger.debug(f"Collected '{command}' from {self.host.hostname}: {len(output)} chars")
            except Exception as e:
                logger.error(f"Failed to collect '{command}' from {self.host.hostname}: {e}")
                results[command] = ''
        return results

    def run_command(self, command: str) -> str:
        """
        Send a single command to the host via Redis and return output.
        Raises CollectionError if the host is offline or times out.
        """
        if not self.host.is_online:
            raise CollectionError(f"Host {self.host.hostname} is offline")

        request_id = str(uuid.uuid4())
        result_key = f'radmin:result:{self.host.hostname}:{request_id}'

        # Publish command to the host's channel
        payload = json.dumps({
            'request_id': request_id,
            'command':    command,
            'args':       '',
        })
        self._redis.publish(f'radmin:cmd:{self.host.hostname}', payload)

        # Poll for result
        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            result = self._redis.get(result_key)
            if result is not None:
                self._redis.delete(result_key)
                return result
            time.sleep(POLL_INTERVAL)

        raise CollectionError(
            f"Timeout waiting for '{command}' result from {self.host.hostname}"
        )
