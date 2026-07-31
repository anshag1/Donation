import time

from app.core.identity_rate_limit import IdentityRateLimiter


def test_allows_up_to_the_limit_then_blocks():
    limiter = IdentityRateLimiter()
    identity = "9876500000"

    for _ in range(5):
        assert limiter.allow(identity, max_requests=5, window_seconds=3600) is True

    assert limiter.allow(identity, max_requests=5, window_seconds=3600) is False


def test_limits_are_independent_per_identity():
    limiter = IdentityRateLimiter()

    for _ in range(3):
        assert limiter.allow("mobile-a", max_requests=3, window_seconds=3600) is True
    assert limiter.allow("mobile-a", max_requests=3, window_seconds=3600) is False

    # A different identity has its own, unaffected budget.
    assert limiter.allow("mobile-b", max_requests=3, window_seconds=3600) is True


def test_reset_clears_all_identities():
    limiter = IdentityRateLimiter()
    limiter.allow("mobile-a", max_requests=1, window_seconds=3600)
    assert limiter.allow("mobile-a", max_requests=1, window_seconds=3600) is False

    limiter.reset()

    assert limiter.allow("mobile-a", max_requests=1, window_seconds=3600) is True


def test_old_hits_fall_outside_the_window():
    limiter = IdentityRateLimiter()
    identity = "9876500000"
    assert limiter.allow(identity, max_requests=1, window_seconds=0.01) is True
    assert limiter.allow(identity, max_requests=1, window_seconds=0.01) is False
    time.sleep(0.02)
    # The earlier hit has now aged out of the window, freeing up budget.
    assert limiter.allow(identity, max_requests=1, window_seconds=0.01) is True
