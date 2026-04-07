"""
Shared scraper utilities: rate limiting and exponential backoff retry logic.

Provides:
- RateLimiter: enforces minimum delay between sequential requests
- retry_on_failure: async decorator for exponential backoff on scrape errors
"""

import asyncio
import time
from functools import wraps
from typing import Callable, Optional, Type, Tuple, Any
from loguru import logger as log


class RateLimiter:
    """
    Enforces a minimum delay between successive calls.

    A single shared instance should be used across all requests within a
    scraper to guarantee the minimum inter-request delay.
    """

    def __init__(self, min_delay_seconds: float = 2.0) -> None:
        """
        Initialise the rate limiter.

        Args:
            min_delay_seconds: Minimum seconds to wait between calls.
                               Must be >= 2.0 per project policy.
        """
        if min_delay_seconds < 2.0:
            raise ValueError("min_delay_seconds must be at least 2.0 (project policy)")
        self._min_delay = min_delay_seconds
        # Use -inf so the very first call never triggers a sleep regardless of
        # how small time.monotonic() is on a freshly-started process.
        self._last_call_time: float = float("-inf")

    async def wait(self) -> None:
        """
        Asynchronously wait until the minimum delay since the last call has elapsed,
        then record the current time as the new last-call timestamp.
        """
        now = time.monotonic()
        elapsed = now - self._last_call_time
        remaining = self._min_delay - elapsed
        if remaining > 0:
            log.debug(f"Rate limiter: sleeping {remaining:.2f}s")
            await asyncio.sleep(remaining)
        self._last_call_time = time.monotonic()

    @property
    def min_delay(self) -> float:
        """Return the configured minimum delay in seconds."""
        return self._min_delay


def retry_on_failure(
    max_attempts: int = 3,
    base_delay_seconds: float = 2.0,
    backoff_factor: float = 2.0,
    retriable_exceptions: Optional[Tuple[Type[BaseException], ...]] = None,
) -> Callable:
    """
    Async decorator that retries a coroutine with exponential backoff on failure.

    Delay schedule (base_delay=2, factor=2):
        attempt 1 → fails → wait 2s
        attempt 2 → fails → wait 4s
        attempt 3 → fails → re-raise

    Args:
        max_attempts:          Maximum number of attempts including the first try.
        base_delay_seconds:    Delay before the second attempt. Subsequent delays
                               are multiplied by backoff_factor.
        backoff_factor:        Multiplier applied to the delay after each failure.
        retriable_exceptions:  Exception types that trigger a retry.  Defaults to
                               (Exception,) — i.e. any non-BaseException error.

    Returns:
        Decorator that wraps an async function with retry logic.
    """
    if retriable_exceptions is None:
        retriable_exceptions = (Exception,)

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            delay = base_delay_seconds
            last_exc: Optional[BaseException] = None

            for attempt in range(1, max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except retriable_exceptions as exc:  # type: ignore[misc]
                    last_exc = exc
                    if attempt < max_attempts:
                        log.warning(
                            f"{func.__name__}: attempt {attempt}/{max_attempts} failed "
                            f"({type(exc).__name__}: {exc}). "
                            f"Retrying in {delay:.1f}s…"
                        )
                        await asyncio.sleep(delay)
                        delay *= backoff_factor
                    else:
                        log.error(
                            f"{func.__name__}: all {max_attempts} attempts failed. "
                            f"Last error — {type(exc).__name__}: {exc}"
                        )

            raise last_exc  # type: ignore[misc]

        return wrapper

    return decorator
