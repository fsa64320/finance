"""FR-028 : 5 échecs, puis 15 secondes qui doublent à chaque échec jusqu'à 15 minutes."""

from finance.auth.ratelimit import AttemptLimiter

from tests.conftest import FakeClock


def limiter(clock: FakeClock) -> AttemptLimiter:
    return AttemptLimiter(clock=clock)


def fail(instance: AttemptLimiter, times: int) -> None:
    for _ in range(times):
        instance.record_failure()


def test_four_failures_do_not_slow_down(clock: FakeClock) -> None:
    attempts = limiter(clock)
    fail(attempts, 4)
    assert attempts.retry_after() == 0


def test_fifth_failure_waits_fifteen_seconds(clock: FakeClock) -> None:
    attempts = limiter(clock)
    fail(attempts, 5)
    assert attempts.retry_after() == 15
    clock.advance(14.2)
    assert attempts.retry_after() == 1
    clock.advance(1)
    assert attempts.retry_after() == 0


def test_delay_doubles_with_each_failure(clock: FakeClock) -> None:
    attempts = limiter(clock)
    fail(attempts, 5)
    delays = [attempts.retry_after()]
    for _ in range(5):
        clock.advance(attempts.retry_after())
        attempts.record_failure()
        delays.append(attempts.retry_after())
    assert delays == [15, 30, 60, 120, 240, 480]


def test_delay_is_capped_at_fifteen_minutes(clock: FakeClock) -> None:
    attempts = limiter(clock)
    fail(attempts, 40)
    assert attempts.retry_after() == 900
    clock.advance(900)
    assert attempts.retry_after() == 0
    attempts.record_failure()
    assert attempts.retry_after() == 900


def test_success_resets_the_counter(clock: FakeClock) -> None:
    attempts = limiter(clock)
    fail(attempts, 7)
    clock.advance(10_000)
    attempts.record_success()
    assert attempts.failures == 0
    fail(attempts, 4)
    assert attempts.retry_after() == 0


def test_failures_before_the_threshold_never_expire_silently(clock: FakeClock) -> None:
    attempts = limiter(clock)
    fail(attempts, 4)
    clock.advance(3 * 3600)
    attempts.record_failure()
    assert attempts.retry_after() == 15
