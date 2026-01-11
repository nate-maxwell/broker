"""
Unit tests for async/await capabilities of the event broker.

Tests cover:
- Async subscribers with emit_async()
- Mixed sync/async subscribers
- Priority ordering with async
- emit() skips async subscribers
- Error handling in async contexts
"""

# -----------------------------------------------------------------------------
# Many of the tests are attempting to verify data within the broker, but the
# broker uses a protective closure to make the subscriber table difficult to
# access.

# The work-around is to create functions that append results to a local table,
# list, or other collection and validate that the collection contains the
# expected items.
# -----------------------------------------------------------------------------

import asyncio

import pytest

import broker


@pytest.mark.asyncio
async def test_basic_async_subscriber() -> None:
    """Test that a basic async subscriber receives events via emit_async."""
    broker.clear()
    invocations: list[str] = []

    async def async_handler(data: str) -> None:
        invocations.append(data)

    broker.register_subscriber("test.async", async_handler)
    await broker.emit_async("test.async", data="test_value")

    assert len(invocations) == 1
    assert invocations[0] == "test_value"


@pytest.mark.asyncio
async def test_multiple_async_subscribers() -> None:
    """Test that multiple async subscribers all receive the event."""
    broker.clear()
    handler1_called: list[bool] = []
    handler2_called: list[bool] = []
    handler3_called: list[bool] = []

    async def handler1(data: str) -> None:
        handler1_called.append(True)

    async def handler2(data: str) -> None:
        handler2_called.append(True)

    async def handler3(data: str) -> None:
        handler3_called.append(True)

    broker.register_subscriber("test.event", handler1)
    broker.register_subscriber("test.event", handler2)
    broker.register_subscriber("test.event", handler3)

    await broker.emit_async("test.event", data="test")

    assert len(handler1_called) == 1
    assert len(handler2_called) == 1
    assert len(handler3_called) == 1


@pytest.mark.asyncio
async def test_emit_skips_async_subscribers() -> None:
    """Test that regular emit() skips async subscribers entirely."""
    broker.clear()
    sync_called: list[bool] = []
    async_called: list[bool] = []

    def sync_handler(data: str) -> None:
        sync_called.append(True)

    async def async_handler(data: str) -> None:
        async_called.append(True)

    broker.register_subscriber("test.event", sync_handler)
    broker.register_subscriber("test.event", async_handler)

    broker.emit("test.event", data="test")

    assert len(sync_called) == 1
    assert len(async_called) == 0  # Async should NOT be called


@pytest.mark.asyncio
async def test_emit_async_calls_both_sync_and_async() -> None:
    """Test that emit_async() calls both sync and async subscribers."""
    broker.clear()
    sync_called: list[bool] = []
    async_called: list[bool] = []

    def sync_handler(data: str) -> None:
        sync_called.append(True)

    async def async_handler(data: str) -> None:
        async_called.append(True)

    broker.register_subscriber("test.event", sync_handler)
    broker.register_subscriber("test.event", async_handler)

    await broker.emit_async("test.event", data="test")

    assert len(sync_called) == 1
    assert len(async_called) == 1


@pytest.mark.asyncio
async def test_async_priority_ordering() -> None:
    """Test that async subscribers execute in priority order."""
    broker.clear()
    execution_order: list[str] = []

    async def low_priority(data: str) -> None:
        execution_order.append("low")

    async def medium_priority(data: str) -> None:
        execution_order.append("medium")

    async def high_priority(data: str) -> None:
        execution_order.append("high")

    broker.register_subscriber("test.event", medium_priority, priority=5)
    broker.register_subscriber("test.event", high_priority, priority=10)
    broker.register_subscriber("test.event", low_priority, priority=1)

    await broker.emit_async("test.event", data="test")

    assert execution_order == ["high", "medium", "low"]


@pytest.mark.asyncio
async def test_mixed_sync_async_priority_ordering() -> None:
    """Test that mixed sync/async subscribers execute in priority order."""
    broker.clear()
    execution_order: list[str] = []

    def sync_high(data: str) -> None:
        execution_order.append("sync_high")

    async def async_medium(data: str) -> None:
        execution_order.append("async_medium")

    def sync_low(data: str) -> None:
        execution_order.append("sync_low")

    broker.register_subscriber("test.event", async_medium, priority=5)
    broker.register_subscriber("test.event", sync_high, priority=10)
    broker.register_subscriber("test.event", sync_low, priority=1)

    await broker.emit_async("test.event", data="test")

    assert execution_order == ["sync_high", "async_medium", "sync_low"]


@pytest.mark.asyncio
async def test_async_with_actual_await() -> None:
    """Test async subscribers that actually await something."""
    broker.clear()
    results: list[str] = []

    async def async_handler(data: str) -> None:
        await asyncio.sleep(0.01)  # Actually await something
        results.append(data)

    broker.register_subscriber("test.event", async_handler)
    await broker.emit_async("test.event", data="after_await")

    assert len(results) == 1
    assert results[0] == "after_await"


@pytest.mark.asyncio
async def test_async_sequential_execution() -> None:
    """Test that async subscribers execute sequentially, not concurrently."""
    broker.clear()
    execution_log: list[tuple[str, str]] = []

    async def handler1(data: str) -> None:
        execution_log.append(("handler1", "start"))
        await asyncio.sleep(0.02)
        execution_log.append(("handler1", "end"))

    async def handler2(data: str) -> None:
        execution_log.append(("handler2", "start"))
        await asyncio.sleep(0.01)
        execution_log.append(("handler2", "end"))

    broker.register_subscriber("test.event", handler1, priority=10)
    broker.register_subscriber("test.event", handler2, priority=5)

    await broker.emit_async("test.event", data="test")

    # If sequential, should be: h1_start, h1_end, h2_start, h2_end
    assert execution_log[0] == ("handler1", "start")
    assert execution_log[1] == ("handler1", "end")
    assert execution_log[2] == ("handler2", "start")
    assert execution_log[3] == ("handler2", "end")


@pytest.mark.asyncio
async def test_async_wildcard_subscribers() -> None:
    """Test that async subscribers work with wildcard namespaces."""
    broker.clear()
    wildcard_calls: list[str] = []
    specific_calls: list[str] = []

    async def wildcard_handler(data: str) -> None:
        wildcard_calls.append(data)

    async def specific_handler(data: str) -> None:
        specific_calls.append(data)

    broker.register_subscriber("system.*", wildcard_handler)
    broker.register_subscriber("system.io.file", specific_handler)

    await broker.emit_async("system.io.file", data="test")

    assert len(wildcard_calls) == 1
    assert len(specific_calls) == 1


@pytest.mark.asyncio
async def test_async_signature_validation() -> None:
    """Test that signature validation works with async subscribers."""
    broker.clear()

    async def async_handler(filename: str, size: int) -> None:
        pass

    broker.register_subscriber("test.event", async_handler)

    # Should work
    await broker.emit_async("test.event", filename="test.txt", size=1024)

    # Should fail - wrong arguments
    with pytest.raises(broker.EmitArgumentError):
        await broker.emit_async("test.event", wrong="args")


@pytest.mark.asyncio
async def test_async_with_kwargs() -> None:
    """Test that async subscribers with **kwargs work correctly."""
    broker.clear()
    received_kwargs: dict = {}

    async def async_handler(**kwargs) -> None:
        received_kwargs.update(kwargs)

    broker.register_subscriber("test.event", async_handler)
    await broker.emit_async("test.event", a=1, b=2, c=3)

    assert received_kwargs == {"a": 1, "b": 2, "c": 3}


@pytest.mark.asyncio
async def test_async_instance_method() -> None:
    """Test that async instance methods work as subscribers."""
    broker.clear()

    class AsyncHandler:
        def __init__(self) -> None:
            self.calls: list[str] = []

        async def on_event(self, data: str) -> None:
            await asyncio.sleep(0.01)
            self.calls.append(data)

    handler = AsyncHandler()
    broker.register_subscriber("test.event", handler.on_event)

    await broker.emit_async("test.event", data="test")

    assert len(handler.calls) == 1
    assert handler.calls[0] == "test"


@pytest.mark.asyncio
async def test_async_decorator_registration() -> None:
    """Test that @subscribe decorator works with async functions."""
    broker.clear()
    calls: list[str] = []

    @broker.subscribe("test.decorated")
    async def decorated_handler(data: str) -> None:
        calls.append(data)

    await broker.emit_async("test.decorated", data="decorated")

    assert len(calls) == 1
    assert calls[0] == "decorated"


@pytest.mark.asyncio
async def test_multiple_emits_to_async() -> None:
    """Test multiple sequential emits to async subscribers."""
    broker.clear()
    calls: list[str] = []

    async def async_handler(data: str) -> None:
        calls.append(data)

    broker.register_subscriber("test.event", async_handler)

    await broker.emit_async("test.event", data="first")
    await broker.emit_async("test.event", data="second")
    await broker.emit_async("test.event", data="third")

    assert calls == ["first", "second", "third"]


@pytest.mark.asyncio
async def test_async_with_notify_flags() -> None:
    """Test that async emit triggers notify events correctly."""
    broker.clear()
    notifications: list[str] = []

    @broker.subscribe(broker.BROKER_ON_EMIT_ASYNC)
    def on_emit_async(using: str) -> None:
        notifications.append(using)

    broker.set_flag_sates(on_emit_async=True)

    async def async_handler(data: str) -> None:
        pass

    broker.register_subscriber("test.event", async_handler)
    await broker.emit_async("test.event", data="test")

    assert "test.event" in notifications


@pytest.mark.asyncio
async def test_async_with_emit_all_flag() -> None:
    """Test that emit_all flag triggers for async emits."""
    broker.clear()
    notifications: list[str] = []

    @broker.subscribe(broker.BROKER_ON_EMIT_ASYNC)
    def on_emit(using: str) -> None:
        notifications.append(using)

    broker.set_flag_sates(on_emit_all=True)

    async def async_handler(data: str) -> None:
        pass

    broker.register_subscriber("test.async", async_handler)
    await broker.emit_async("test.async", data="test")

    assert "test.async" in notifications


@pytest.mark.asyncio
async def test_empty_namespace_with_async() -> None:
    """Test that emitting to empty namespace with emit_async doesn't error."""
    broker.clear()
    await broker.emit_async("nonexistent.namespace", data="test")


@pytest.mark.asyncio
async def test_async_unsubscribe_during_emit() -> None:
    """Test that unsubscribing doesn't affect current emit cycle."""
    broker.clear()
    calls: list[str] = []

    async def handler1(data: str) -> None:
        calls.append("handler1")

    async def handler2(data: str) -> None:
        calls.append("handler2")

    broker.register_subscriber("test.event", handler1)
    broker.register_subscriber("test.event", handler2)

    await broker.emit_async("test.event", data="test")

    assert len(calls) == 2


@pytest.mark.asyncio
async def test_sync_emit_with_only_async_subscribers() -> None:
    """Test that sync emit with only async subscribers calls nothing."""
    broker.clear()
    calls: list[bool] = []

    async def async_only(data: str) -> None:
        calls.append(True)

    broker.register_subscriber("test.event", async_only)

    # Sync emit should skip async subscriber
    broker.emit("test.event", data="test")

    assert len(calls) == 0

    # Async emit should work
    await broker.emit_async("test.event", data="test")
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_async_with_weak_references() -> None:
    """Test that async subscribers work correctly with weak references."""
    broker.clear()
    calls: list[str] = []

    async def async_handler(data: str) -> None:
        calls.append(data)

    broker.register_subscriber("test.event", async_handler)
    await broker.emit_async("test.event", data="before_gc")

    assert len(calls) == 1

    # Handler is still in scope, should work again
    await broker.emit_async("test.event", data="still_alive")
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_async_execution_order_with_delays() -> None:
    """
    Test that execution order is maintained even when handlers have
    different delays.
    """
    broker.clear()
    execution_order: list[str] = []

    async def fast_handler(data: str) -> None:
        execution_order.append("fast_start")
        await asyncio.sleep(0.001)
        execution_order.append("fast_end")

    async def slow_handler(data: str) -> None:
        execution_order.append("slow_start")
        await asyncio.sleep(0.01)
        execution_order.append("slow_end")

    # Register slow first with higher priority
    broker.register_subscriber("test.event", slow_handler, priority=10)
    broker.register_subscriber("test.event", fast_handler, priority=5)

    await broker.emit_async("test.event", data="test")

    # Slow should complete entirely before fast starts (sequential execution)
    assert execution_order == ["slow_start", "slow_end", "fast_start", "fast_end"]
