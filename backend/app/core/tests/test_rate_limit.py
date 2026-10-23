"""Limitador unico: limites por llamada, ambitos aislados y Retry-After."""

import pytest

from app.core import rate_limit
from app.core.exceptions import RateLimitedError


@pytest.fixture(autouse=True)
def _clean():
    rate_limit.reset()
    yield
    rate_limit.reset()


def test_allows_up_to_limit_then_429_with_retry_after():
    for _ in range(3):
        rate_limit.enforce("t", (("k", 3),), 60)
    with pytest.raises(RateLimitedError) as exc:
        rate_limit.enforce("t", (("k", 3),), 60)
    assert int(exc.value.headers["Retry-After"]) >= 1
    assert exc.value.details["retry_after_seconds"] >= 1


def test_limit_is_taken_per_call_not_fixed():
    rate_limit.enforce("t", (("k", 1),), 60)
    with pytest.raises(RateLimitedError):
        rate_limit.enforce("t", (("k", 1),), 60)
    rate_limit.enforce("t", (("k", 5),), 60)  # un limite mayor lo permite


def test_scopes_do_not_share_counters():
    rate_limit.enforce("a", (("k", 1),), 60)
    rate_limit.enforce("b", (("k", 1),), 60)
    with pytest.raises(RateLimitedError):
        rate_limit.enforce("a", (("k", 1),), 60)


def test_window_expiry_with_fake_clock():
    now = [0.0]
    limiter = rate_limit.SlidingWindowLimiter(clock=lambda: now[0])
    assert limiter.hit("k", 1, 10) is None
    assert limiter.hit("k", 1, 10) == 10
    now[0] = 10.0
    assert limiter.hit("k", 1, 10) is None


def test_first_failing_check_stops_the_rest():
    rate_limit.enforce("t", (("a", 1), ("b", 1)), 60)
    with pytest.raises(RateLimitedError):
        rate_limit.enforce("t", (("a", 1), ("b", 1)), 60)
