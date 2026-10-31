"""When an external call may be repeated: only failures the provider did not process.

Connection failures and 429/5xx answers are retried up to MAX_RETRIES times. A read
timeout on a paid model call is not retried, since the provider may already have processed
and billed the request.
"""

import httpx

MAX_RETRIES = 2
DELAYS = (1.0, 3.0)
MAX_RETRY_AFTER = 20.0
RETRY_STATUS = {429, 500, 502, 503, 504}
# The request never reached the provider.
NOT_SENT = (httpx.ConnectError, httpx.ConnectTimeout)


def retry_delay(attempt: int, response: httpx.Response | None = None) -> float:
    """Seconds to wait before retry number attempt (0-based), honouring Retry-After."""
    if response is not None:
        value = response.headers.get("retry-after", "")
        try:
            return min(max(float(value), 0.0), MAX_RETRY_AFTER)
        except ValueError:
            pass
    return DELAYS[min(attempt, len(DELAYS) - 1)]


def should_retry_status(status_code: int, attempt: int) -> bool:
    return attempt < MAX_RETRIES and status_code in RETRY_STATUS


def should_retry_error(error: Exception, attempt: int, paid: bool) -> bool:
    if attempt >= MAX_RETRIES:
        return False
    if isinstance(error, NOT_SENT):
        return True
    # A cheap call may also be repeated after a timeout or a dropped connection.
    return not paid and isinstance(error, (httpx.TimeoutException, httpx.TransportError))
