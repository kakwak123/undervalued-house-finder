"""
Unit tests for scraper_utils: RateLimiter and retry_on_failure.

These tests do NOT require Scrapfly credentials and run fully offline.
"""

import asyncio
import time
import pytest

from scraper_utils import RateLimiter, retry_on_failure


# ---------------------------------------------------------------------------
# RateLimiter tests
# ---------------------------------------------------------------------------


class TestRateLimiter:
    def test_min_delay_enforced_on_construction(self) -> None:
        """RateLimiter must reject delays below 2 seconds."""
        with pytest.raises(ValueError, match="at least 2.0"):
            RateLimiter(min_delay_seconds=1.9)

    def test_exactly_2s_is_accepted(self) -> None:
        limiter = RateLimiter(min_delay_seconds=2.0)
        assert limiter.min_delay == 2.0

    def test_custom_delay_stored(self) -> None:
        limiter = RateLimiter(min_delay_seconds=5.0)
        assert limiter.min_delay == 5.0

    @pytest.mark.asyncio
    async def test_first_call_is_immediate(self) -> None:
        """The very first call on a fresh limiter should not sleep."""
        limiter = RateLimiter(min_delay_seconds=2.0)
        start = time.monotonic()
        await limiter.wait()
        elapsed = time.monotonic() - start
        # Should complete in well under 1 second
        assert elapsed < 1.0, f"First call took {elapsed:.3f}s, expected near 0"

    @pytest.mark.asyncio
    async def test_second_call_respects_min_delay(self) -> None:
        """A second call immediately after the first must wait ~min_delay."""
        limiter = RateLimiter(min_delay_seconds=2.0)
        await limiter.wait()  # first call — no wait
        start = time.monotonic()
        await limiter.wait()  # second call — must wait ~2s
        elapsed = time.monotonic() - start
        assert elapsed >= 1.9, f"Second call only waited {elapsed:.3f}s, expected >= 1.9s"

    @pytest.mark.asyncio
    async def test_no_extra_wait_if_enough_time_passed(self) -> None:
        """If enough time has already elapsed, wait() should return quickly."""
        limiter = RateLimiter(min_delay_seconds=2.0)
        await limiter.wait()  # first call
        await asyncio.sleep(2.1)  # manually wait more than min_delay
        start = time.monotonic()
        await limiter.wait()  # should not sleep
        elapsed = time.monotonic() - start
        assert elapsed < 0.5, f"Unexpected extra sleep: {elapsed:.3f}s"


# ---------------------------------------------------------------------------
# retry_on_failure tests
# ---------------------------------------------------------------------------


class TestRetryOnFailure:
    @pytest.mark.asyncio
    async def test_succeeds_on_first_attempt(self) -> None:
        """Function that succeeds immediately is called exactly once."""
        call_count = 0

        @retry_on_failure(max_attempts=3, base_delay_seconds=0.01)
        async def always_succeeds() -> str:
            nonlocal call_count
            call_count += 1
            return "ok"

        result = await always_succeeds()
        assert result == "ok"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_retries_on_failure_then_succeeds(self) -> None:
        """Function that fails twice then succeeds is called 3 times total."""
        call_count = 0

        @retry_on_failure(max_attempts=3, base_delay_seconds=0.01, backoff_factor=2.0)
        async def fails_twice_then_succeeds() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError(f"simulated failure #{call_count}")
            return "recovered"

        result = await fails_twice_then_succeeds()
        assert result == "recovered"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_raises_after_all_attempts_exhausted(self) -> None:
        """Function that always fails raises on the last attempt."""
        call_count = 0

        @retry_on_failure(max_attempts=3, base_delay_seconds=0.01)
        async def always_fails() -> None:
            nonlocal call_count
            call_count += 1
            raise RuntimeError("always broken")

        with pytest.raises(RuntimeError, match="always broken"):
            await always_fails()

        assert call_count == 3

    @pytest.mark.asyncio
    async def test_max_attempts_one_no_retry(self) -> None:
        """max_attempts=1 means no retries at all."""
        call_count = 0

        @retry_on_failure(max_attempts=1, base_delay_seconds=0.01)
        async def fails_once() -> None:
            nonlocal call_count
            call_count += 1
            raise IOError("single failure")

        with pytest.raises(IOError):
            await fails_once()

        assert call_count == 1

    @pytest.mark.asyncio
    async def test_only_retriable_exceptions_trigger_retry(self) -> None:
        """Non-retriable exception types are not retried."""
        call_count = 0

        @retry_on_failure(
            max_attempts=3,
            base_delay_seconds=0.01,
            retriable_exceptions=(ValueError,),
        )
        async def raises_type_error() -> None:
            nonlocal call_count
            call_count += 1
            raise TypeError("not retriable")

        with pytest.raises(TypeError):
            await raises_type_error()

        # TypeError is not in retriable_exceptions — should not be caught/retried
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_retriable_exceptions_are_retried(self) -> None:
        """Exceptions that match retriable_exceptions are retried."""
        call_count = 0

        @retry_on_failure(
            max_attempts=3,
            base_delay_seconds=0.01,
            retriable_exceptions=(ValueError,),
        )
        async def raises_value_error() -> None:
            nonlocal call_count
            call_count += 1
            raise ValueError("retriable")

        with pytest.raises(ValueError):
            await raises_value_error()

        assert call_count == 3

    @pytest.mark.asyncio
    async def test_exponential_backoff_delays_increase(self) -> None:
        """Confirm delay approximately doubles on each retry."""
        delays: list[float] = []
        call_count = 0

        @retry_on_failure(max_attempts=3, base_delay_seconds=0.1, backoff_factor=2.0)
        async def always_fails() -> None:
            nonlocal call_count
            call_count += 1
            raise RuntimeError("fail")

        # Patch asyncio.sleep to record delays without actually sleeping
        original_sleep = asyncio.sleep
        sleep_calls: list[float] = []

        async def mock_sleep(seconds: float) -> None:
            sleep_calls.append(seconds)

        asyncio.sleep = mock_sleep  # type: ignore[assignment]
        try:
            with pytest.raises(RuntimeError):
                await always_fails()
        finally:
            asyncio.sleep = original_sleep  # type: ignore[assignment]

        # Should have slept twice (between attempt 1→2 and 2→3)
        assert len(sleep_calls) == 2
        assert sleep_calls[0] == pytest.approx(0.1, abs=0.001)
        assert sleep_calls[1] == pytest.approx(0.2, abs=0.001)

    @pytest.mark.asyncio
    async def test_return_value_propagated(self) -> None:
        """Decorated function's return value passes through correctly."""

        @retry_on_failure(max_attempts=2, base_delay_seconds=0.01)
        async def returns_dict() -> dict:
            return {"key": "value", "count": 42}

        result = await returns_dict()
        assert result == {"key": "value", "count": 42}

    def test_wrapped_function_name_preserved(self) -> None:
        """functools.wraps must preserve the original function name."""

        @retry_on_failure(max_attempts=2, base_delay_seconds=0.01)
        async def my_scraper_function() -> None:
            pass

        assert my_scraper_function.__name__ == "my_scraper_function"
