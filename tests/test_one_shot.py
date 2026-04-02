"""Unit tests for is_one_shot subscriber behavior."""

import pytest

import broker


@pytest.fixture(autouse=True)
def clear_broker():
    """Reset broker state before and after each test."""
    broker.clear()
    yield
    broker.clear()


# -----Registration------------------------------------------------------------


def test_is_one_shot_flag_stored_on_subscriber():
    def handler(data: str) -> None:
        pass

    broker.register_subscriber("test.event", handler, once=True)

    subscribers = broker.get_subscribers("test.event")
    assert len(subscribers) == 1
    assert subscribers[0].is_one_shot is True


def test_is_one_shot_false_by_default():
    def handler(data: str) -> None:
        pass

    broker.register_subscriber("test.event", handler)

    subscribers = broker.get_subscribers("test.event")
    assert len(subscribers) == 1
    assert subscribers[0].is_one_shot is False


def test_subscribe_decorator_once_param():
    @broker.subscribe("test.event", once=True)
    def handler(data: str) -> None:
        pass

    subscribers = broker.get_subscribers("test.event")
    assert len(subscribers) == 1
    assert subscribers[0].is_one_shot is True


# -----Fires Once--------------------------------------------------------------


def test_callback_called_on_first_emit():
    called = []

    def handler(data: str) -> None:
        called.append(data)

    broker.register_subscriber("test.event", handler, once=True)
    broker.emit("test.event", data="first")

    assert called == ["first"]


def test_callback_not_called_on_second_emit():
    called = []

    def handler(data: str) -> None:
        called.append(data)

    broker.register_subscriber("test.event", handler, once=True)
    broker.emit("test.event", data="first")
    broker.emit("test.event", data="second")

    assert called == ["first"]


def test_callback_called_exactly_once_across_many_emits():
    called = []

    def handler(data: str) -> None:
        called.append(data)

    broker.register_subscriber("test.event", handler, once=True)
    for i in range(10):
        broker.emit("test.event", data=str(i))

    assert len(called) == 1


# -----Unregistered After Firing-----------------------------------------------


def test_unregistered_from_namespace_after_emit():
    def handler(data: str) -> None:
        pass

    broker.register_subscriber("test.event", handler, once=True)
    broker.emit("test.event", data="x")

    assert not broker.is_subscribed(handler, "test.event")


def test_namespace_deleted_when_one_shot_was_only_subscriber():
    def handler(data: str) -> None:
        pass

    broker.register_subscriber("test.event", handler, once=True)
    broker.emit("test.event", data="x")

    assert not broker.namespace_exists("test.event")


def test_namespace_survives_when_other_subscribers_remain():
    def one_shot(data: str) -> None:
        pass

    def permanent(data: str) -> None:
        pass

    broker.register_subscriber("test.event", one_shot, once=True)
    broker.register_subscriber("test.event", permanent)
    broker.emit("test.event", data="x")

    assert not broker.is_subscribed(one_shot, "test.event")
    assert broker.is_subscribed(permanent, "test.event")
    assert broker.namespace_exists("test.event")


# -----Isolation---------------------------------------------------------------


def test_permanent_subscriber_unaffected_by_one_shot():
    permanent_calls = []
    one_shot_calls = []

    def one_shot(data: str) -> None:
        one_shot_calls.append(data)

    def permanent(data: str) -> None:
        permanent_calls.append(data)

    broker.register_subscriber("test.event", one_shot, once=True)
    broker.register_subscriber("test.event", permanent)

    broker.emit("test.event", data="first")
    broker.emit("test.event", data="second")
    broker.emit("test.event", data="third")

    assert one_shot_calls == ["first"]
    assert permanent_calls == ["first", "second", "third"]


def test_multiple_one_shot_subscribers_each_fire_once():
    calls = []

    def handler_a(data: str) -> None:
        calls.append("a")

    def handler_b(data: str) -> None:
        calls.append("b")

    broker.register_subscriber("test.event", handler_a, once=True)
    broker.register_subscriber("test.event", handler_b, once=True)

    broker.emit("test.event", data="first")
    broker.emit("test.event", data="second")

    assert sorted(calls) == ["a", "b"]


def test_one_shot_on_one_namespace_does_not_affect_another():
    calls = []

    def handler(data: str) -> None:
        calls.append(data)

    broker.register_subscriber("test.one", handler, once=True)
    broker.register_subscriber("test.two", handler)

    broker.emit("test.one", data="from_one")
    broker.emit("test.two", data="from_two")

    # one_shot on test.one should not have affected the test.two registration
    assert calls == ["from_one", "from_two"]


# -----Wildcard Namespaces-----------------------------------------------------


def test_one_shot_fires_on_wildcard_match():
    called = []

    def handler(**kwargs: object) -> None:
        called.append(kwargs)

    broker.register_subscriber("test.*", handler, once=True)
    broker.emit("test.foo", **{})

    assert len(called) == 1


def test_one_shot_wildcard_unregistered_after_first_match():
    called = []

    def handler(**kwargs: object) -> None:
        called.append(True)

    broker.register_subscriber("test.*", handler, once=True)
    broker.emit("test.foo")
    broker.emit("test.bar")

    assert len(called) == 1
    assert not broker.is_subscribed(handler, "test.*")


# -----Bound Methods-----------------------------------------------------------


def test_one_shot_bound_method_fires_once():
    class Listener(object):
        def __init__(self) -> None:
            self.calls: list[str] = []

        def on_event(self, data: str) -> None:
            self.calls.append(data)

    listener = Listener()
    broker.register_subscriber("test.event", listener.on_event, once=True)

    broker.emit("test.event", data="first")
    broker.emit("test.event", data="second")

    assert listener.calls == ["first"]
    assert not broker.is_subscribed(listener.on_event, "test.event")


# -----Async-------------------------------------------------------------------


@pytest.mark.asyncio
async def test_one_shot_async_subscriber_fires_once():
    called = []

    async def handler(data: str) -> None:
        called.append(data)

    broker.register_subscriber("test.event", handler, once=True)

    await broker.emit_async("test.event", data="first")
    await broker.emit_async("test.event", data="second")

    assert called == ["first"]
    assert not broker.is_subscribed(handler, "test.event")


# -----Re-registration---------------------------------------------------------


def test_can_reregister_after_one_shot_fires():
    calls = []

    def handler(data: str) -> None:
        calls.append(data)

    broker.register_subscriber("test.event", handler, once=True)
    broker.emit("test.event", data="first")

    # Re-register — should work cleanly
    broker.register_subscriber("test.event", handler, once=True)
    broker.emit("test.event", data="second")

    assert calls == ["first", "second"]
