"""
Unit tests for broker exception handling capabilities.

Tests verify that the broker's exception handling system properly manages errors
that occur during subscriber callback execution. This includes testing different
exception handler policies (stop, continue, silent, collecting), ensuring handlers
work with both sync and async subscribers, and validating that exception handling
respects priority ordering and namespace isolation.
"""

import pytest

import broker
from broker import handlers
from broker import subscriber


def test_default_exception_handler_stops_delivery() -> None:
    """Test that default exception handler stops delivery to remaining subscribers."""
    broker.clear()
    calls: list[str] = []

    def failing_handler(data: str) -> None:
        calls.append("failing")
        raise ValueError("Test exception")

    def should_not_run(data: str) -> None:
        calls.append("should_not_run")

    broker.register_subscriber("test.event", failing_handler, priority=10)
    broker.register_subscriber("test.event", should_not_run, priority=5)

    # Default handler stops on exception
    broker.emit("test.event", data="test")

    assert "failing" in calls
    assert "should_not_run" not in calls


def test_set_subscription_exception_handler_to_none_raises() -> None:
    """Test that setting exception handler to None re-raises handlers."""
    broker.clear()
    broker.set_subscriber_exception_handler(None)

    def failing_handler(data: str) -> None:
        raise ValueError("Test exception")

    broker.register_subscriber("test.event", failing_handler)

    with pytest.raises(ValueError, match="Test exception"):
        broker.emit("test.event", data="test")


def test_silent_exception_handler_continues() -> None:
    """Test that silent handler continues to next subscriber."""
    broker.clear()
    broker.set_subscriber_exception_handler(handlers.silent_exception_handler)
    calls: list[str] = []

    def failing_handler(data: str) -> None:
        calls.append("failing")
        raise ValueError("Test exception")

    def succeeding_handler(data: str) -> None:
        calls.append("succeeding")

    broker.register_subscriber("test.event", failing_handler, priority=10)
    broker.register_subscriber("test.event", succeeding_handler, priority=5)

    broker.emit("test.event", data="test")

    assert "failing" in calls
    assert "succeeding" in calls


def test_collecting_exception_handler() -> None:
    """Test that collecting handler captures exception information."""
    broker.clear()
    handlers.exceptions_caught.clear()
    broker.set_subscriber_exception_handler(handlers.collecting_exception_handler)

    def failing_handler1(data: str) -> None:
        raise ValueError("First error")

    def failing_handler2(data: str) -> None:
        raise TypeError("Second error")

    broker.register_subscriber("test.event", failing_handler1, priority=10)
    broker.register_subscriber("test.event", failing_handler2, priority=5)

    broker.emit("test.event", data="test")

    assert len(handlers.exceptions_caught) == 2
    assert "ValueError: First error" in handlers.exceptions_caught[0]["exception"]
    assert "TypeError: Second error" in handlers.exceptions_caught[1]["exception"]
    assert handlers.exceptions_caught[0]["namespace"] == "test.event"
    assert handlers.exceptions_caught[1]["namespace"] == "test.event"


def test_custom_handler_stops_on_specific_exception() -> None:
    """Test custom handler that stops only on specific exception types."""
    broker.clear()
    calls: list[str] = []

    def custom_handler(_, __, exception):
        if isinstance(exception, ValueError):
            return True
        return False

    broker.set_subscriber_exception_handler(custom_handler)

    def fails_with_value_error(data: str) -> None:
        calls.append("value_error")
        raise ValueError("Stop here")

    def fails_with_type_error(data: str) -> None:
        calls.append("type_error")
        raise TypeError("Continue after this")

    def should_run_after_type_error(data: str) -> None:
        calls.append("after_type_error")

    def should_not_run_after_value_error(data: str) -> None:
        calls.append("after_value_error")

    # Test ValueError stops delivery
    broker.register_subscriber("test.stops", fails_with_value_error, priority=10)
    broker.register_subscriber(
        "test.stops", should_not_run_after_value_error, priority=5
    )

    broker.emit("test.stops", data="test")

    assert "value_error" in calls
    assert "after_value_error" not in calls

    # Test TypeError continues delivery
    broker.register_subscriber("test.continues", fails_with_type_error, priority=10)
    broker.register_subscriber(
        "test.continues", should_run_after_type_error, priority=5
    )

    broker.emit("test.continues", data="test")

    assert "type_error" in calls
    assert "after_type_error" in calls


@pytest.mark.asyncio
async def test_exception_handler_with_emit_async() -> None:
    """Test that exception handler works with emit_async()."""
    broker.clear()
    broker.set_subscriber_exception_handler(handlers.silent_exception_handler)
    calls: list[str] = []

    async def failing_async_handler(data: str) -> None:
        calls.append("failing_async")
        raise ValueError("Async error")

    def failing_sync_handler(data: str) -> None:
        calls.append("failing_sync")
        raise TypeError("Sync error")

    async def succeeding_async_handler(data: str) -> None:
        calls.append("succeeding_async")

    broker.register_subscriber("test.async", failing_async_handler, priority=10)
    broker.register_subscriber("test.async", failing_sync_handler, priority=5)
    broker.register_subscriber("test.async", succeeding_async_handler, priority=1)

    await broker.emit_async("test.async", data="test")

    assert "failing_async" in calls
    assert "failing_sync" in calls
    assert "succeeding_async" in calls


@pytest.mark.asyncio
async def test_exception_handler_stops_async_delivery() -> None:
    """Test that exception handler can stop async delivery."""
    broker.clear()
    calls: list[str] = []

    def stop_handler(callback, namespace, exception):
        return True

    broker.set_subscriber_exception_handler(stop_handler)

    async def failing_handler(data: str) -> None:
        calls.append("failing")
        raise ValueError("Stop")

    async def should_not_run(data: str) -> None:
        calls.append("should_not_run")

    broker.register_subscriber("test.event", failing_handler, priority=10)
    broker.register_subscriber("test.event", should_not_run, priority=5)

    await broker.emit_async("test.event", data="test")

    assert "failing" in calls
    assert "should_not_run" not in calls


def test_exception_handler_receives_correct_arguments() -> None:
    """Test that exception handler receives callback, namespace, and exception."""
    broker.clear()
    handler_args: list[tuple] = []

    def capture_handler(
        callback: subscriber.CALLBACK, namespace: str, exception: Exception
    ) -> bool:
        handler_args.append((callback.__name__, namespace, type(exception).__name__))
        return False

    broker.set_subscriber_exception_handler(capture_handler)

    def my_failing_callback(data: str) -> None:
        raise ValueError("Test")

    broker.register_subscriber("test.namespace", my_failing_callback)
    broker.emit("test.namespace", data="test")

    assert len(handler_args) == 1
    assert handler_args[0][0] == "my_failing_callback"
    assert handler_args[0][1] == "test.namespace"
    assert handler_args[0][2] == "ValueError"


def test_exception_handler_with_instance_method() -> None:
    """Test that exception handler works with instance methods."""
    broker.clear()
    handlers.exceptions_caught.clear()
    broker.set_subscriber_exception_handler(handlers.collecting_exception_handler)

    class Handler:
        def on_event(self, data: str) -> None:
            raise RuntimeError("Instance method error")

    handler = Handler()
    broker.register_subscriber("test.event", handler.on_event)
    broker.emit("test.event", data="test")

    assert len(handlers.exceptions_caught) == 1
    assert "Handler.on_event" in handlers.exceptions_caught[0]["callback"]
    assert (
        "RuntimeError: Instance method error"
        in handlers.exceptions_caught[0]["exception"]
    )


def test_exception_handler_with_lambda() -> None:
    """Test that exception handler works with lambda functions."""
    broker.clear()
    handlers.exceptions_caught.clear()
    broker.set_subscriber_exception_handler(handlers.collecting_exception_handler)

    # noinspection PyPep8
    lambda_handler = lambda data: (_ for _ in ()).throw(ValueError("Lambda error"))
    broker.register_subscriber("test.event", lambda_handler)
    broker.emit("test.event", data="test")

    assert len(handlers.exceptions_caught) == 1


def test_exception_only_affects_one_namespace() -> None:
    """Test that exception in one namespace doesn't affect another."""
    broker.clear()
    broker.set_subscriber_exception_handler(handlers.silent_exception_handler)
    calls: list[str] = []

    def failing_handler(data: str) -> None:
        calls.append("failing")
        raise ValueError("Error")

    def namespace1_handler(data: str) -> None:
        calls.append("namespace1")

    def namespace2_handler(data: str) -> None:
        calls.append("namespace2")

    broker.register_subscriber("ns1", failing_handler, priority=10)
    broker.register_subscriber("ns1", namespace1_handler, priority=5)
    broker.register_subscriber("ns2", namespace2_handler)

    broker.emit("ns1", data="test")
    broker.emit("ns2", data="test")

    assert "failing" in calls
    assert "namespace1" in calls
    assert "namespace2" in calls


def test_exception_with_wildcard_subscribers() -> None:
    """Test exception handling with wildcard namespace subscriptions."""
    broker.clear()
    broker.set_subscriber_exception_handler(handlers.silent_exception_handler)
    calls: list[str] = []

    def failing_wildcard(data: str) -> None:
        calls.append("wildcard")
        raise ValueError("Wildcard error")

    def specific_handler(data: str) -> None:
        calls.append("specific")

    broker.register_subscriber("system.*", failing_wildcard, priority=10)
    broker.register_subscriber("system.io.file", specific_handler, priority=5)

    broker.emit("system.io.file", data="test")

    assert "wildcard" in calls
    assert "specific" in calls


def test_multiple_exceptions_in_same_emit() -> None:
    """Test handling multiple exceptions from different subscribers."""
    broker.clear()
    handlers.exceptions_caught.clear()
    broker.set_subscriber_exception_handler(handlers.collecting_exception_handler)

    def handler1(data: str) -> None:
        raise ValueError("Error 1")

    def handler2(data: str) -> None:
        raise TypeError("Error 2")

    def handler3(data: str) -> None:
        raise RuntimeError("Error 3")

    broker.register_subscriber("test.event", handler1, priority=10)
    broker.register_subscriber("test.event", handler2, priority=5)
    broker.register_subscriber("test.event", handler3, priority=1)

    broker.emit("test.event", data="test")

    assert len(handlers.exceptions_caught) == 3
    error_messages = [e["exception"] for e in handlers.exceptions_caught]
    assert "ValueError: Error 1" in error_messages[0]
    assert "TypeError: Error 2" in error_messages[1]
    assert "RuntimeError: Error 3" in error_messages[2]


def test_successful_handlers_before_and_after_exception() -> None:
    """Test that successful handlers run even when another handler fails."""
    broker.clear()
    broker.set_subscriber_exception_handler(handlers.silent_exception_handler)
    calls: list[str] = []

    def handler1(data: str) -> None:
        calls.append("handler1")

    def failing_handler(data: str) -> None:
        calls.append("failing")
        raise ValueError("Error")

    def handler3(data: str) -> None:
        calls.append("handler3")

    broker.register_subscriber("test.event", handler1, priority=10)
    broker.register_subscriber("test.event", failing_handler, priority=5)
    broker.register_subscriber("test.event", handler3, priority=1)

    broker.emit("test.event", data="test")

    assert calls == ["handler1", "failing", "handler3"]


@pytest.mark.asyncio
async def test_mixed_sync_async_with_exceptions() -> None:
    """Test exception handling with mixed sync and async subscribers."""
    broker.clear()
    broker.set_subscriber_exception_handler(handlers.silent_exception_handler)
    calls: list[str] = []

    def sync_handler(data: str) -> None:
        calls.append("sync")
        raise ValueError("Sync error")

    async def async_handler(data: str) -> None:
        calls.append("async")
        raise TypeError("Async error")

    def final_sync(data: str) -> None:
        calls.append("final_sync")

    broker.register_subscriber("test.event", sync_handler, priority=10)
    broker.register_subscriber("test.event", async_handler, priority=5)
    broker.register_subscriber("test.event", final_sync, priority=1)

    await broker.emit_async("test.event", data="test")

    assert "sync" in calls
    assert "async" in calls
    assert "final_sync" in calls


def test_exception_handler_with_priority_ordering() -> None:
    """Test that exceptions are handled in priority order."""
    broker.clear()
    execution_order: list[int] = []

    def tracking_handler(callback, namespace, exception):
        # Extract priority from exception message
        priority = int(str(exception).split()[-1])
        execution_order.append(priority)
        return False

    broker.set_subscriber_exception_handler(tracking_handler)

    def priority_10(data: str) -> None:
        raise ValueError("priority 10")

    def priority_5(data: str) -> None:
        raise ValueError("priority 5")

    def priority_1(data: str) -> None:
        raise ValueError("priority 1")

    broker.register_subscriber("test.event", priority_5, priority=5)
    broker.register_subscriber("test.event", priority_10, priority=10)
    broker.register_subscriber("test.event", priority_1, priority=1)

    broker.emit("test.event", data="test")

    assert execution_order == [10, 5, 1]
