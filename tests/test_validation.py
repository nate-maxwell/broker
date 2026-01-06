"""
Unit test to ensure signatures are tracked and validated.

When a callback subscribes to an existing namespace, the first signature is
stored and following signatures are validated against the first.
"""

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

    with pytest.raises(broker.SignatureMismatchError, match="parameter mismatch"):
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
    with pytest.raises(broker.EmitArgumentError, match="Argument mismatch"):
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
    with pytest.raises(broker.EmitArgumentError, match="Argument mismatch"):
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

    with pytest.raises(broker.EmitArgumentError, match="Argument mismatch"):
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

    assert received["foo"] == "bar"
    assert received["count"] == 42
    assert received["active"] is True
