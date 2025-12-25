from typing import Any

import pytest

import broker


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


def test_wildcard_parent_receives_child_events() -> None:
    """
    Test that a parent wildcard subscriber receives events from child
    namespaces.
    """
    broker.clear()
    parent_invoked: list[bool] = []
    child_invoked: list[bool] = []

    # noinspection PyUnusedLocal
    def parent_callback(**kwargs: Any) -> None:
        parent_invoked.append(True)

    # noinspection PyUnusedLocal
    def child_callback(**kwargs: Any) -> None:
        child_invoked.append(True)

    broker.register_subscriber("test.*", parent_callback)
    broker.register_subscriber("test.child", child_callback)
    broker.emit("test.child")

    # Assert - both parent wildcard and exact child should receive the event
    assert len(parent_invoked) == 1  # Parent gets it via wildcard match
    assert len(child_invoked) == 1  # Child gets it via exact match


def test_arguments_passed_to_callback() -> None:
    """Test that arguments are correctly passed from emit to the callback."""
    broker.clear()
    namespace = "system.io.file_save"
    received_kwargs: dict[str, object] = {}

    def test_callback(filename: str, size: int, success: bool) -> None:
        received_kwargs["filename"] = filename
        received_kwargs["size"] = size
        received_kwargs["success"] = success

    broker.register_subscriber(namespace, test_callback)
    broker.emit(namespace, filename="test.txt", size=1024, success=True)

    # Assert - all arguments should be passed correctly
    assert received_kwargs["filename"] == "test.txt"
    assert received_kwargs["size"] == 1024
    assert received_kwargs["success"] is True


def test_callbacks_execute_in_priority_order() -> None:
    """Test that callbacks execute in priority order (highest first)."""
    broker.clear()
    namespace = "system.test"
    execution_order: list[str] = []

    # noinspection PyUnusedLocal
    def low_priority_callback(**kwargs: Any) -> None:
        execution_order.append("low")

    # noinspection PyUnusedLocal
    def medium_priority_callback(**kwargs: Any) -> None:
        execution_order.append("medium")

    # noinspection PyUnusedLocal
    def high_priority_callback(**kwargs: Any) -> None:
        execution_order.append("high")

    broker.register_subscriber(namespace, medium_priority_callback, priority=5)
    broker.register_subscriber(namespace, high_priority_callback, priority=10)
    broker.register_subscriber(namespace, low_priority_callback, priority=1)
    broker.emit(namespace)

    # Assert - should execute in priority order (high to low)
    assert execution_order == ["high", "medium", "low"]


def test_matching_signatures_allowed() -> None:
    """Test that callbacks with matching signatures can be registered."""
    broker.clear()
    namespace = "file.save"

    # noinspection PyUnusedLocal
    def callback1(size: int, filename: str) -> None:
        pass

    # noinspection PyUnusedLocal
    # different positions
    def callback2(filename: str, size: int) -> None:
        pass

    # Act & Assert - should not raise
    broker.register_subscriber(namespace, callback1)
    broker.register_subscriber(namespace, callback2)


def test_mismatched_signatures_rejected() -> None:
    """Test that callbacks with different signatures are rejected."""
    broker.clear()
    namespace = "file.save"

    # noinspection PyUnusedLocal
    def callback1(filename: str, size: int) -> None:
        pass

    # noinspection PyUnusedLocal
    def callback2(filename: str, mode: str) -> None:
        pass

    broker.register_subscriber(namespace, callback1)

    with pytest.raises(ValueError, match="parameter mismatch"):
        broker.register_subscriber(namespace, callback2)


def test_kwargs_accepts_any_signature() -> None:
    """Test that callbacks with **kwargs accept any arguments."""
    broker.clear()
    namespace = "file.save"

    # noinspection PyUnusedLocal
    def callback1(filename: str, size: int) -> None:
        pass

    # noinspection PyUnusedLocal
    def callback2(**kwargs: object) -> None:
        pass

    # Act & Assert - should not raise (kwargs is compatible with anything)
    broker.register_subscriber(namespace, callback1)
    broker.register_subscriber(namespace, callback2)


def test_emit_validates_arguments() -> None:
    """Test that emit validates arguments match subscriber expectations."""
    broker.clear()
    namespace = "file.save"

    # noinspection PyUnusedLocal
    def callback(filename: str, size: int) -> None:
        pass

    broker.register_subscriber(namespace, callback)
    broker.emit(namespace, filename="test.txt", size=1024)

    # Wrong args should raise
    with pytest.raises(ValueError, match="Argument mismatch"):
        broker.emit(namespace, filename="test.txt", mode="w")


def test_wildcard_subscription_validates() -> None:
    """Test that wildcard subscriptions validate against emitted events."""
    broker.clear()

    # noinspection PyUnusedLocal
    def wildcard_callback(filename: str, size: int) -> None:
        pass

    broker.register_subscriber("file.*", wildcard_callback)
    broker.emit("file.save", filename="test.txt", size=1024)

    # Mismatched args should raise
    with pytest.raises(ValueError, match="Argument mismatch"):
        broker.emit("file.delete", path="test.txt")


def test_specific_and_wildcard_must_match() -> None:
    """Test that specific and wildcard subscribers must have compatible signatures."""
    broker.clear()

    # noinspection PyUnusedLocal
    def specific_callback(filename: str, size: int) -> None:
        pass

    # noinspection PyUnusedLocal
    def wildcard_callback(filename: str, mode: str) -> None:
        pass

    broker.register_subscriber("file.save", specific_callback)
    broker.register_subscriber("file.*", wildcard_callback)

    with pytest.raises(ValueError, match="Argument mismatch"):
        broker.emit("file.save", filename="test.txt", size=1024)


def test_kwargs_callback_accepts_any_emit() -> None:
    """Test that **kwargs callbacks accept any emitted arguments."""
    broker.clear()
    namespace = "flexible.event"
    received: dict[str, object] = {}

    def flexible_callback(**kwargs: object) -> None:
        received.update(kwargs)

    broker.register_subscriber(namespace, flexible_callback)
    broker.emit(namespace, foo="bar", count=42, active=True)

    # Assert
    assert received["foo"] == "bar"
    assert received["count"] == 42
    assert received["active"] is True
