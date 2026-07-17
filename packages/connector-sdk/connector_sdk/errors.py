"""Connector error taxonomy.

Campaign task processing (apps/worker) branches retry behavior on these
types: transient/rate-limit/quota errors are retried with backoff; auth
and permanent errors are not, and immediately fail the task.
"""


class ConnectorError(Exception):
    """Base class for all connector-raised errors."""


class ConnectorAuthError(ConnectorError):
    """Credentials are missing, invalid, or revoked. Not retryable."""


class ConnectorQuotaError(ConnectorError):
    """The source's usage quota has been exhausted. Not retryable until
    the quota resets - callers should stop dispatching new requests to
    this connector for a cooldown window rather than retrying immediately."""


class ConnectorRateLimitError(ConnectorError):
    """The source is temporarily rate-limiting this connector. Retryable
    with backoff."""


class ConnectorTransientError(ConnectorError):
    """A transient failure (network blip, 5xx, timeout). Retryable."""


class ConnectorPermanentError(ConnectorError):
    """A permanent, non-retryable failure (e.g. malformed query the
    source rejects deterministically)."""
