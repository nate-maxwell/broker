"""Unit tests for broker.unregister_subscriber_all."""

import pytest

import broker


@pytest.fixture(autouse=True)
def clear_broker():
    """Reset broker state before each test."""
    broker.clear()
    yield
    broker.clear()


# -----Basic Removal-----------------------------------------------------------


def test_removes_from_single_namespace():
    def handler(data: str) -> None:
        pass

    broker.register_subscriber("test.one", handler)
    broker.unregister_subscriber_all(handler)

    assert not broker.is_subscribed(handler, "test.one")


def test_removes_from_multiple_namespaces():
    def handler(data: str) -> None:
        pass

    broker.register_subscriber("test.one", handler)
    broker.register_subscriber("test.two", handler)
    broker.register_subscriber("test.three", handler)

    broker.unregister_subscriber_all(handler)

    assert not broker.is_subscribed(handler, "test.one")
    assert not broker.is_subscribed(handler, "test.two")
    assert not broker.is_subscribed(handler, "test.three")


def test_no_subscriptions_does_not_raise():
    def handler(data: str) -> None:
        pass

    broker.unregister_subscriber_all(handler)  # Should not raise


def test_already_unsubscribed_does_not_raise():
    def handler(data: str) -> None:
        pass

    broker.register_subscriber("test.one", handler)
    broker.unregister_subscriber_all(handler)
    broker.unregister_subscriber_all(handler)  # Second call should not raise


# -----Isolation---------------------------------------------------------------


def test_does_not_remove_other_callbacks():
    def handler_a(data: str) -> None:
        pass

    def handler_b(data: str) -> None:
        pass

    broker.register_subscriber("test.one", handler_a)
    broker.register_subscriber("test.one", handler_b)

    broker.unregister_subscriber_all(handler_a)

    assert not broker.is_subscribed(handler_a, "test.one")
    assert broker.is_subscribed(handler_b, "test.one")


def test_does_not_remove_from_namespaces_not_subscribed_to():
    def handler_a(data: str) -> None:
        pass

    def handler_b(data: str) -> None:
        pass

    broker.register_subscriber("test.one", handler_a)
    broker.register_subscriber("test.two", handler_b)

    broker.unregister_subscriber_all(handler_a)

    assert broker.is_subscribed(handler_b, "test.two")


# -----Namespace Cleanup-------------------------------------------------------


def test_namespace_deleted_when_last_subscriber_removed():
    def handler(data: str) -> None:
        pass

    broker.register_subscriber("test.one", handler)
    broker.unregister_subscriber_all(handler)

    assert not broker.namespace_exists("test.one")


def test_namespace_survives_when_other_subscribers_remain():
    def handler_a(data: str) -> None:
        pass

    def handler_b(data: str) -> None:
        pass

    broker.register_subscriber("test.one", handler_a)
    broker.register_subscriber("test.one", handler_b)

    broker.unregister_subscriber_all(handler_a)

    assert broker.namespace_exists("test.one")


# -----Wildcard Subscriptions--------------------------------------------------


def test_removes_from_wildcard_namespace():
    def handler(**kwargs: object) -> None:
        pass

    broker.register_subscriber("test.*", handler)
    broker.unregister_subscriber_all(handler)

    assert not broker.is_subscribed(handler, "test.*")


def test_removes_from_mix_of_exact_and_wildcard_namespaces():
    def handler(**kwargs: object) -> None:
        pass

    broker.register_subscriber("test.one", handler)
    broker.register_subscriber("test.*", handler)

    broker.unregister_subscriber_all(handler)

    assert not broker.is_subscribed(handler, "test.one")
    assert not broker.is_subscribed(handler, "test.*")


# -----Method Subscribers------------------------------------------------------


def test_removes_bound_method():
    class Listener(object):
        def on_event(self, data: str) -> None:
            pass

    listener = Listener()

    broker.register_subscriber("test.one", listener.on_event)
    broker.register_subscriber("test.two", listener.on_event)

    broker.unregister_subscriber_all(listener.on_event)

    assert not broker.is_subscribed(listener.on_event, "test.one")
    assert not broker.is_subscribed(listener.on_event, "test.two")


def test_removing_one_instance_does_not_affect_another():
    class Listener(object):
        def on_event(self, data: str) -> None:
            pass

    listener_a = Listener()
    listener_b = Listener()

    broker.register_subscriber("test.one", listener_a.on_event)
    broker.register_subscriber("test.one", listener_b.on_event)

    broker.unregister_subscriber_all(listener_a.on_event)

    assert not broker.is_subscribed(listener_a.on_event, "test.one")
    assert broker.is_subscribed(listener_b.on_event, "test.one")


# -----Callback No Longer Called After Removal---------------------------------


def test_callback_not_invoked_after_removal():
    called = []

    def handler(data: str) -> None:
        called.append(data)

    broker.register_subscriber("test.one", handler)
    broker.register_subscriber("test.two", handler)

    broker.unregister_subscriber_all(handler)

    broker.emit("test.one", data="a")
    broker.emit("test.two", data="b")

    assert called == []


def test_other_callback_still_invoked_after_removal():
    called = []

    def handler_a(data: str) -> None:
        called.append("a")

    def handler_b(data: str) -> None:
        called.append("b")

    broker.register_subscriber("test.one", handler_a)
    broker.register_subscriber("test.one", handler_b)

    broker.unregister_subscriber_all(handler_a)

    broker.emit("test.one", data="x")

    assert called == ["b"]


# -----get_subscriptions Consistency-------------------------------------------


def test_get_subscriptions_empty_after_removal():
    def handler(data: str) -> None:
        pass

    broker.register_subscriber("test.one", handler)
    broker.register_subscriber("test.two", handler)

    broker.unregister_subscriber_all(handler)

    assert broker.get_subscriptions(handler) == []
