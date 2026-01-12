"""Unit tests for broker middleware/transformer system."""

# -----------------------------------------------------------------------------
# Many of the tests are attempting to verify data within the broker, but the
# broker uses a protective closure to make the subscriber table difficult to
# access.

# The work-around is to create functions that append results to a local table,
# list, or other collection and validate that the collection contains the
# expected items.
# -----------------------------------------------------------------------------


import gc

import pytest

import broker


def test_transformer_modifies_kwargs() -> None:
    """Test that transformers can modify event kwargs."""
    broker.clear()

    received_kwargs = []

    def add_field(namespace: str, kwargs: dict) -> dict:
        kwargs["added_field"] = "added_value"
        return kwargs

    def handler(**kwargs) -> None:
        received_kwargs.append(kwargs)

    broker.register_transformer("test.event", add_field)
    broker.register_subscriber("test.event", handler)

    broker.emit("test.event", original="data")

    assert len(received_kwargs) == 1
    assert received_kwargs[0]["original"] == "data"
    assert received_kwargs[0]["added_field"] == "added_value"


def test_transform_decorator_basic() -> None:
    """Test basic transformer registration using decorator."""
    broker.clear()

    @broker.transform("test.event")
    def add_field(namespace: str, kwargs: dict) -> dict:
        kwargs["added"] = True
        return kwargs

    # Verify transformer was registered
    transformers = broker.get_transformers("test.event")
    assert len(transformers) == 1
    assert transformers[0].callback == add_field
    assert transformers[0].priority == 0
    assert transformers[0].namespace == "test.event"


def test_transformer_can_block_event() -> None:
    """Test that returning None blocks event propagation."""
    broker.clear()

    calls = []

    def block_event(namespace: str, kwargs: dict) -> None:
        return None  # Block

    def handler(data: str) -> None:
        calls.append(data)

    broker.register_transformer("test.event", block_event)
    broker.register_subscriber("test.event", handler)

    broker.emit("test.event", data="blocked")

    # Handler should not be called
    assert len(calls) == 0


def test_transformer_priority_order() -> None:
    """Test that transformers execute in priority order."""
    broker.clear()

    execution_order = []

    def transformer_low(namespace: str, kwargs: dict) -> dict:
        execution_order.append("low")
        return kwargs

    def transformer_high(namespace: str, kwargs: dict) -> dict:
        execution_order.append("high")
        return kwargs

    def transformer_medium(namespace: str, kwargs: dict) -> dict:
        execution_order.append("medium")
        return kwargs

    def handler(data: str) -> None:
        pass

    broker.register_transformer("test.event", transformer_low, priority=1)
    broker.register_transformer("test.event", transformer_high, priority=10)
    broker.register_transformer("test.event", transformer_medium, priority=5)
    broker.register_subscriber("test.event", handler)

    broker.emit("test.event", data="test")

    assert execution_order == ["high", "medium", "low"]


def test_transformer_with_wildcard() -> None:
    """Test that transformers work with wildcard namespaces."""
    broker.clear()

    received = []

    def add_timestamp(namespace: str, kwargs: dict) -> dict:
        kwargs["timestamp"] = "now"
        return kwargs

    def handler(**kwargs) -> None:
        received.append(kwargs)

    broker.register_transformer("system.*", add_timestamp)
    broker.register_subscriber("system.io.file", handler)

    broker.emit("system.io.file", data="test")

    assert len(received) == 1
    assert received[0]["timestamp"] == "now"


def test_multiple_transformers_chain() -> None:
    """Test that multiple transformers chain together."""
    broker.clear()

    received = []

    def add_field1(namespace: str, kwargs: dict) -> dict:
        kwargs["field1"] = "value1"
        return kwargs

    def add_field2(namespace: str, kwargs: dict) -> dict:
        kwargs["field2"] = "value2"
        return kwargs

    def handler(**kwargs) -> None:
        received.append(kwargs)

    broker.register_transformer("test.event", add_field1, priority=10)
    broker.register_transformer("test.event", add_field2, priority=5)
    broker.register_subscriber("test.event", handler)

    broker.emit("test.event", original="data")

    assert len(received) == 1
    assert received[0]["original"] == "data"
    assert received[0]["field1"] == "value1"
    assert received[0]["field2"] == "value2"


def test_unregister_transformer() -> None:
    """Test removing a transformer."""
    broker.clear()

    received = []

    def transformer(namespace: str, kwargs: dict) -> dict:
        kwargs["transformed"] = True
        return kwargs

    def handler(**kwargs) -> None:
        received.append(kwargs)

    broker.register_transformer("test.event", transformer)
    broker.register_subscriber("test.event", handler)

    broker.emit("test.event", data="test")
    assert received[0].get("transformed") is True

    # Unregister transformer
    broker.unregister_transformer("test.event", transformer)
    received.clear()

    broker.emit("test.event", data="test")
    assert "transformed" not in received[0]


def test_transformer_doesnt_modify_original_kwargs() -> None:
    """Test that transformers work on a copy, not the original."""
    broker.clear()

    def transformer(namespace: str, kwargs: dict) -> dict:
        kwargs["added"] = "value"
        return kwargs

    def handler(**kwargs) -> None:
        pass

    broker.register_transformer("test.event", transformer)
    broker.register_subscriber("test.event", handler)

    original_kwargs = {"original": "data"}
    broker.emit("test.event", **original_kwargs)

    # Original dict should not be modified
    assert "added" not in original_kwargs


@pytest.mark.asyncio
async def test_transformer_with_async_emit() -> None:
    """Test that transformers work with emit_async."""
    broker.clear()

    received = []

    def transformer(namespace: str, kwargs: dict) -> dict:
        kwargs["transformed"] = True
        return kwargs

    async def async_handler(**kwargs) -> None:
        received.append(kwargs)

    broker.register_transformer("test.event", transformer)
    broker.register_subscriber("test.event", async_handler)

    await broker.emit_async("test.event", data="test")

    assert len(received) == 1
    assert received[0]["transformed"] is True


def test_transformer_error_raises() -> None:
    """Test that transformer errors are raised."""
    broker.clear()
    broker.set_transformer_exception_handler(None)

    def failing_transformer(namespace: str, kwargs: dict) -> dict:
        raise ValueError("Transformer failed")

    def handler(data: str) -> None:
        pass

    broker.register_transformer("test.event", failing_transformer)
    broker.register_subscriber("test.event", handler)

    with pytest.raises(RuntimeError, match="Transformer .* failed"):
        broker.emit("test.event", data="test")


def test_get_transformers() -> None:
    """Test getting transformers for a namespace."""
    broker.clear()

    def transformer1(namespace: str, kwargs: dict) -> dict:
        return kwargs

    def transformer2(namespace: str, kwargs: dict) -> dict:
        return kwargs

    broker.register_transformer("test.event", transformer1)
    broker.register_transformer("test.event", transformer2)

    transformers = broker.get_transformers("test.event")

    assert len(transformers) == 2
    assert any(t.callback == transformer1 for t in transformers)
    assert any(t.callback == transformer2 for t in transformers)


def test_transformer_receives_namespace() -> None:
    """Test that transformer receives the actual event namespace."""
    broker.clear()

    received_namespace = []

    def transformer(namespace: str, kwargs: dict) -> dict:
        received_namespace.append(namespace)
        return kwargs

    def handler(data: str) -> None:
        pass

    broker.register_transformer("system.*", transformer)
    broker.register_subscriber("system.io.file", handler)

    broker.emit("system.io.file", data="test")

    assert received_namespace[0] == "system.io.file"


def test_get_transformer_count() -> None:
    """Test counting transformers for a namespace."""
    broker.clear()

    def transformer1(namespace: str, kwargs: dict) -> dict:
        return kwargs

    def transformer2(namespace: str, kwargs: dict) -> dict:
        return kwargs

    broker.register_transformer("test.event", transformer1)
    broker.register_transformer("test.event", transformer2)

    assert broker.get_transformer_count("test.event") == 2
    assert broker.get_transformer_count("nonexistent") == 0


def test_get_live_transformer_count() -> None:
    """Test counting only live (non-garbage-collected) transformers."""
    broker.clear()

    transformer1 = lambda namespace, kwargs: kwargs

    def transformer2(namespace: str, kwargs: dict) -> dict:
        return kwargs

    broker.register_transformer("test.event", transformer1)
    broker.register_transformer("test.event", transformer2)

    assert broker.get_live_transformer_count("test.event") == 2

    del transformer1
    gc.collect()

    assert broker.get_live_transformer_count("test.event") == 1


def test_is_transformed() -> None:
    """Test checking if a callback is registered as a transformer."""
    broker.clear()

    def transformer1(namespace: str, kwargs: dict) -> dict:
        return kwargs

    def transformer2(namespace: str, kwargs: dict) -> dict:
        return kwargs

    broker.register_transformer("test.event", transformer1)

    assert broker.is_transformed(transformer1, "test.event") is True
    assert broker.is_transformed(transformer2, "test.event") is False
    assert broker.is_transformed(transformer1, "other.event") is False


def test_get_transformations() -> None:
    """Test getting all namespaces a transformer is registered for."""
    broker.clear()

    def transformer(namespace: str, kwargs: dict) -> dict:
        return kwargs

    broker.register_transformer("test.one", transformer)
    broker.register_transformer("test.two", transformer)
    broker.register_transformer("test.three", transformer)

    transformations = broker.get_transformations(transformer)

    assert transformations == ["test.one", "test.three", "test.two"]


def test_get_live_transformers() -> None:
    """Test getting only live transformers."""
    broker.clear()

    transformer1 = lambda namespace, kwargs: kwargs

    def transformer2(namespace: str, kwargs: dict) -> dict:
        return kwargs

    broker.register_transformer("test.event", transformer1, priority=10)
    broker.register_transformer("test.event", transformer2, priority=5)

    live_transformers = broker.get_live_transformers("test.event")
    assert len(live_transformers) == 2

    del transformer1
    gc.collect()

    live_transformers = broker.get_live_transformers("test.event")
    assert len(live_transformers) == 1
    assert live_transformers[0].callback == transformer2
    assert live_transformers[0].priority == 5


def test_transformer_weak_reference() -> None:
    """Test that transformers use weak references."""
    broker.clear()

    def create_transformer():
        def transformer(namespace: str, kwargs: dict) -> dict:
            kwargs["modified"] = True
            return kwargs

        return transformer

    transformer = create_transformer()
    broker.register_transformer("test.event", transformer)

    assert broker.get_transformer_count("test.event") == 1
    assert broker.get_live_transformer_count("test.event") == 1

    # Delete transformer and collect garbage
    del transformer
    gc.collect()

    # Broker automatically cleans up dead references
    assert broker.get_transformer_count("test.event") == 0
    assert broker.get_live_transformer_count("test.event") == 0


def test_transformer_garbage_collection_doesnt_break_emit() -> None:
    """Test that emit continues to work after transformers are garbage collected."""
    broker.clear()

    received = []

    transformer = lambda namespace, kwargs: {**kwargs, "added": True}

    def handler(**kwargs) -> None:
        received.append(kwargs)

    broker.register_transformer("test.event", transformer)
    broker.register_subscriber("test.event", handler)

    broker.emit("test.event", data="test")
    assert received[0].get("added") is True

    received.clear()
    del transformer
    gc.collect()

    # Should still emit, just without transformation
    broker.emit("test.event", data="test")
    assert len(received) == 1
    assert "added" not in received[0]


def test_transformer_silent_exception_handler() -> None:
    """Test silent exception handler continues processing."""
    broker.clear()

    received = []

    def failing_transformer(namespace: str, kwargs: dict) -> dict:
        raise ValueError("Transformer failed")

    def working_transformer(namespace: str, kwargs: dict) -> dict:
        kwargs["worked"] = True
        return kwargs

    def handler(**kwargs) -> None:
        received.append(kwargs)

    broker.set_transformer_exception_handler(
        broker.handlers.silent_transformer_exception
    )

    broker.register_transformer("test.event", failing_transformer, priority=10)
    broker.register_transformer("test.event", working_transformer, priority=5)
    broker.register_subscriber("test.event", handler)

    # Should continue despite error
    broker.emit("test.event", data="test")

    assert len(received) == 1
    assert received[0]["worked"] is True


def test_transformer_log_and_continue_handler() -> None:
    """Test log and continue exception handler."""
    broker.clear()

    received = []

    def failing_transformer(namespace: str, kwargs: dict) -> dict:
        raise ValueError("Transformer failed")

    def handler(**kwargs) -> None:
        received.append(kwargs)

    broker.set_transformer_exception_handler(
        broker.handlers.log_and_continue_transformer_exception
    )

    broker.register_transformer("test.event", failing_transformer)
    broker.register_subscriber("test.event", handler)

    # Should log but continue
    broker.emit("test.event", data="test")

    assert len(received) == 1


def test_transformer_collecting_exception_handler() -> None:
    """Test collecting exception handler gathers errors."""
    broker.clear()

    def failing_transformer(namespace: str, kwargs: dict) -> dict:
        raise ValueError("Transformer failed")

    def handler(data: str) -> None:
        pass

    broker.handlers.transformer_exceptions_caught.clear()
    broker.set_transformer_exception_handler(
        broker.handlers.collecting_transformer_exception
    )

    broker.register_transformer("test.event", failing_transformer)
    broker.register_subscriber("test.event", handler)

    broker.emit("test.event", data="test")

    assert len(broker.handlers.transformer_exceptions_caught) == 1
    caught = broker.handlers.transformer_exceptions_caught[0]
    assert "ValueError" in caught["exception"]
    assert caught["namespace"] == "test.event"


def test_transformer_custom_exception_handler() -> None:
    """Test custom exception handler."""
    broker.clear()

    handled_exceptions = []

    def custom_handler(transformer, namespace: str, exception: Exception) -> bool:
        handled_exceptions.append((namespace, str(exception)))
        return False  # Continue

    def failing_transformer(namespace: str, kwargs: dict) -> dict:
        raise ValueError("Custom error")

    def handler(data: str) -> None:
        pass

    broker.set_transformer_exception_handler(custom_handler)
    broker.register_transformer("test.event", failing_transformer)
    broker.register_subscriber("test.event", handler)

    broker.emit("test.event", data="test")

    assert len(handled_exceptions) == 1
    assert handled_exceptions[0][0] == "test.event"
    assert "Custom error" in handled_exceptions[0][1]


def test_transformer_only_namespace() -> None:
    """Test namespace with only transformers (no subscribers)."""
    broker.clear()

    def transformer(namespace: str, kwargs: dict) -> dict:
        return kwargs

    broker.register_transformer("test.event", transformer)

    # Namespace should exist
    assert broker.namespace_exists("test.event")

    # Should have transformer info
    info = broker.get_namespace_info("test.event")
    assert info["transformer_count"] == 1
    assert info["subscriber_count"] == 0


def test_unregister_last_transformer_removes_namespace() -> None:
    """Test that removing the last transformer removes the namespace."""
    broker.clear()

    def transformer(namespace: str, kwargs: dict) -> dict:
        return kwargs

    broker.register_transformer("test.event", transformer)
    assert broker.namespace_exists("test.event")

    broker.unregister_transformer("test.event", transformer)
    assert not broker.namespace_exists("test.event")


def test_namespace_with_both_subscribers_and_transformers() -> None:
    """Test namespace with both subscribers and transformers."""
    broker.clear()

    def transformer(namespace: str, kwargs: dict) -> dict:
        return kwargs

    def handler(data: str) -> None:
        pass

    broker.register_transformer("test.event", transformer)
    broker.register_subscriber("test.event", handler)

    info = broker.get_namespace_info("test.event")
    assert info["transformer_count"] == 1
    assert info["subscriber_count"] == 1

    # Remove transformer, namespace should still exist
    broker.unregister_transformer("test.event", transformer)
    assert broker.namespace_exists("test.event")

    # Remove subscriber, namespace should be gone
    broker.unregister_subscriber("test.event", handler)
    assert not broker.namespace_exists("test.event")


def test_statistics_with_dead_transformer_references() -> None:
    """Test statistics correctly count transformers."""
    broker.clear()

    transformer1 = lambda namespace, kwargs: kwargs
    transformer2 = lambda namespace, kwargs: kwargs

    broker.register_transformer("test.event", transformer1)
    broker.register_transformer("test.event", transformer2)

    stats = broker.get_statistics()
    assert stats["total_transformers"] == 2
    assert stats["total_live_transformers"] == 2
    assert stats["dead_transformer_references"] == 0

    # Keep transformer2 alive, delete transformer1
    del transformer1
    gc.collect()

    stats = broker.get_statistics()
    # Broker automatically cleans up dead references
    assert stats["total_transformers"] == 1
    assert stats["total_live_transformers"] == 1
    assert stats["dead_transformer_references"] == 0


def test_transformer_add_notification() -> None:
    """Test notification when transformer is added."""
    broker.clear()
    notifications = []

    def notify_handler(using: str) -> None:
        notifications.append(("added", using))

    broker.register_subscriber(broker.BROKER_ON_TRANSFORMER_ADDED, notify_handler)
    broker.set_flag_states(on_transform=True)

    def transformer(namespace: str, kwargs: dict) -> dict:
        return kwargs

    broker.register_transformer("test.event", transformer)

    assert len(notifications) == 1
    assert notifications[0] == ("added", "test.event")


def test_transformer_remove_notification() -> None:
    """Test notification when transformer is removed."""
    broker.clear()
    notifications = []

    def notify_handler(using: str) -> None:
        notifications.append(("removed", using))

    def transformer(namespace: str, kwargs: dict) -> dict:
        return kwargs

    broker.register_subscriber(broker.BROKER_ON_TRANSFORMER_REMOVED, notify_handler)
    broker.set_flag_states(on_untransform=True)

    broker.register_transformer("test.event", transformer)
    broker.unregister_transformer("test.event", transformer)

    assert len(notifications) == 1
    assert notifications[0] == ("removed", "test.event")


def test_transformer_collected_notification() -> None:
    """Test notification when transformer is garbage collected."""
    broker.clear()

    notifications = []

    def notify_handler(using: str) -> None:
        notifications.append(("collected", using))

    broker.register_subscriber(broker.BROKER_ON_TRANSFORMER_COLLECTED, notify_handler)
    broker.set_flag_states(on_transformer_collected=True)

    transformer = lambda namespace, kwargs: kwargs
    broker.register_transformer("test.event", transformer)

    del transformer
    gc.collect()

    assert len(notifications) == 1
    assert notifications[0] == ("collected", "test.event")
