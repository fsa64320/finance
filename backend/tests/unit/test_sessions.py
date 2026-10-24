"""FR-028 : 30 minutes d'inactivité, 12 heures au plus."""

from finance.auth.sessions import IDLE_TIMEOUT, MAX_AGE, SessionStore

from tests.conftest import FakeClock

MINUTE = 60.0
HOUR = 3600.0


def test_limits_are_the_ones_of_the_specification() -> None:
    assert (IDLE_TIMEOUT, MAX_AGE) == (30 * MINUTE, 12 * HOUR)


def test_tokens_are_unpredictable_and_distinct(clock: FakeClock) -> None:
    store = SessionStore(clock=clock)
    tokens = {store.create() for _ in range(50)}
    assert len(tokens) == 50
    assert all(len(token) >= 40 for token in tokens)


def test_unknown_or_missing_token_is_invalid(clock: FakeClock) -> None:
    store = SessionStore(clock=clock)
    assert not store.validate(None)
    assert not store.validate("")
    assert not store.validate("inconnu")


def test_session_expires_after_thirty_idle_minutes(clock: FakeClock) -> None:
    store = SessionStore(clock=clock)
    token = store.create()
    clock.advance(30 * MINUTE - 1)
    assert store.validate(token)
    clock.advance(30 * MINUTE + 1)
    assert not store.validate(token)


def test_activity_extends_the_idle_window(clock: FakeClock) -> None:
    store = SessionStore(clock=clock)
    token = store.create()
    for _ in range(5):
        clock.advance(25 * MINUTE)
        assert store.validate(token)


def test_session_never_outlives_twelve_hours(clock: FakeClock) -> None:
    store = SessionStore(clock=clock)
    token = store.create()
    for _ in range(100):
        clock.advance(20 * MINUTE)
        if not store.validate(token):
            break
    assert clock.now - 1000.0 <= 12 * HOUR + 20 * MINUTE
    clock.advance(1)
    assert not store.validate(token)


def test_revoke_and_clear(clock: FakeClock) -> None:
    store = SessionStore(clock=clock)
    first, second = store.create(), store.create()
    store.revoke(first)
    assert not store.validate(first)
    assert store.validate(second)
    store.clear()
    assert not store.validate(second)
    assert not store.has_active()


def test_has_active_ignores_expired_sessions(clock: FakeClock) -> None:
    store = SessionStore(clock=clock)
    store.create()
    assert store.has_active()
    clock.advance(31 * MINUTE)
    assert not store.has_active()


def test_raw_tokens_are_not_kept_in_memory(clock: FakeClock) -> None:
    store = SessionStore(clock=clock)
    token = store.create()
    assert token not in repr(vars(store))
