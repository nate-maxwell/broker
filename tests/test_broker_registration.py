"""Unit test to ensure callbacks are properly registered and registered."""

import asyncio
from typing import Any

import pytest

import broker


# -----------------------------------------------------------------------------
# Many of the tests are attempting to verify data within the broker, but the
# broker uses a protective closure to make the subscriber table difficult to
# access.

# The work-around is to create functions that append results to a local table,
# list, or other collection and validate that the collection contains the
# expected items.
# -----------------------------------------------------------------------------


def test_record_protected() -> None:
    """Test that the subscriber dict in the broker is protected by closure."""
    broker.clear()
    try:
        _ = "foo" in broker._SUBSCRIBERS
    except Exception as e:
        assert type(e) == AttributeError


def test_subscriber_registration() -> None:
    """Test that a subscriber is successfully registered to a namespace."""
    broker.clear()
    namespace = "test.test_subscriber_registration"
    callback_invoked: list = []

    # noinspection PyUnusedLocal
    def test_callback(**kwargs: Any) -> None:
        callback_invoked.append(True)

    broker.register_subscriber(namespace, test_callback)
    broker.emit(namespace)

    # Assert - if subscriber was registered, callback should have been invoked
    assert len(callback_invoked) == 1
    assert callback_invoked[0] is True


def test_subscriber_unregistration() -> None:
    """Test that a subscriber is successfully unregistered from a namespace."""
    broker.clear()
    namespace = "test.test_subscriber_unregistration"
    callback_invoked: list[bool] = []

    # noinspection PyUnusedLocal
    def test_callback(**kwargs: Any) -> None:
        callback_invoked.append(True)

    broker.register_subscriber(namespace, test_callback)
    broker.unregister_subscriber(namespace, test_callback)
    broker.emit(namespace)

    # Assert - if subscriber was unregistered, callback should NOT have been
    # invoked
    assert len(callback_invoked) == 0


def test_subscribe_decorator_registers_function() -> None:
    """Test that @subscribe decorator successfully registers a function."""
    broker.clear()
    invoked: list[str] = []

    @broker.subscribe("test.event")
    def decorated_callback(message: str) -> None:
        invoked.append(message)

    broker.emit("test.event", message="hello")

    assert invoked == ["hello"]


def test_subscribe_decorator_with_priority() -> None:
    """Test that @subscribe decorator respects priority parameter."""
    broker.clear()
    execution_order: list[str] = []

    # noinspection PyUnusedLocal
    @broker.subscribe("test.priority", priority=1)
    def low_priority(data: str) -> None:
        execution_order.append("low")

    # noinspection PyUnusedLocal
    @broker.subscribe("test.priority", priority=10)
    def high_priority(data: str) -> None:
        execution_order.append("high")

    # noinspection PyUnusedLocal
    @broker.subscribe("test.priority", priority=5)
    def medium_priority(data: str) -> None:
        execution_order.append("medium")

    broker.emit("test.priority", data="test")

    assert execution_order == ["high", "medium", "low"]


def test_subscribe_decorator_returns_original_function() -> None:
    """Test that @subscribe decorator returns the original function unchanged."""
    broker.clear()

    @broker.subscribe("test.return")
    def my_function(value: int) -> int:
        return value * 2

    result = my_function(5)

    assert result == 10


def test_subscribe_decorator_with_async_function() -> None:
    """Test that @subscribe decorator works with async functions."""
    broker.clear()
    invoked: list[str] = []

    @broker.subscribe("test.async")
    async def async_callback(message: str) -> None:
        await asyncio.sleep(0.01)
        invoked.append(message)

    asyncio.run(broker.emit_async("test.async", message="async_test"))

    assert invoked == ["async_test"]


def test_subscribe_decorator_with_wildcard() -> None:
    """Test that @subscribe decorator works with wildcard namespaces."""
    broker.clear()
    invoked: list[str] = []

    @broker.subscribe("system.*")
    def wildcard_handler(action: str) -> None:
        invoked.append(action)

    broker.emit("system.start", action="starting")
    broker.emit("system.stop", action="stopping")

    assert invoked == ["starting", "stopping"]


def test_subscribe_decorator_multiple_on_same_namespace() -> None:
    """Test that multiple @subscribe decorators can register to same namespace."""
    broker.clear()
    results: list[str] = []

    @broker.subscribe("test.multi")
    def handler1(msg: str) -> None:
        results.append(f"handler1: {msg}")

    @broker.subscribe("test.multi")
    def handler2(msg: str) -> None:
        results.append(f"handler2: {msg}")

    broker.emit("test.multi", msg="test")

    assert len(results) == 2
    assert "handler1: test" in results
    assert "handler2: test" in results


def test_subscribe_decorator_with_kwargs() -> None:
    """Test that @subscribe decorator works with **kwargs callbacks."""
    broker.clear()
    received: dict[str, object] = {}

    @broker.subscribe("test.kwargs")
    def flexible_handler(**kwargs: object) -> None:
        received.update(kwargs)

    broker.emit("test.kwargs", foo="bar", count=42, active=True)

    assert received["foo"] == "bar"
    assert received["count"] == 42
    assert received["active"] is True


def test_subscribe_decorator_enforces_signature_matching() -> None:
    """Test that @subscribe decorator enforces signature validation."""
    broker.clear()

    # noinspection PyUnusedLocal
    @broker.subscribe("test.signature")
    def first_handler(name: str, age: int) -> None:
        pass

    with pytest.raises(broker.SignatureMismatchError, match="parameter mismatch"):
        # noinspection PyUnusedLocal
        @broker.subscribe("test.signature")
        def second_handler(name: str, email: str) -> None:
            pass
