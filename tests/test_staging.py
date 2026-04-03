"""
Unit tests for broker.stage(), broker.emit_staged(), and broker.emit_staged_async().
"""

import pytest
import broker


@pytest.fixture(autouse=True)
def clear_broker():
    """Reset broker state before and after each test."""
    broker.clear()
    broker.clear_staged()
    yield
    broker.clear()
    broker.clear_staged()


# -----stage()----------------------------------------------------------------


def test_stage_adds_to_staged_registry():
    broker.stage("test.event", data="hello")
    assert broker.get_staged_count() == 1


def test_stage_multiple_events_same_namespace():
    broker.stage("test.event", data="first")
    broker.stage("test.event", data="second")
    assert broker.get_staged_count("test.event") == 2


def test_stage_multiple_namespaces():
    broker.stage("test.one", data="a")
    broker.stage("test.two", data="b")
    assert broker.get_staged_count("test.one") == 1
    assert broker.get_staged_count("test.two") == 1


def test_stage_no_kwargs():
    def handler(**kwargs: object) -> None:
        pass

    broker.register_subscriber("test.event", handler)
    broker.stage("test.event")
    assert broker.get_staged_count("test.event") == 1


def test_stage_does_not_dispatch_immediately():
    called = []

    def handler(data: str) -> None:
        called.append(data)

    broker.register_subscriber("test.event", handler)
    broker.stage("test.event", data="hello")

    assert called == []


# -----emit_staged()-----------------------------------------------------------


def test_emit_staged_dispatches_to_subscribers():
    called = []

    def handler(data: str) -> None:
        called.append(data)

    broker.register_subscriber("test.event", handler)
    broker.stage("test.event", data="hello")
    broker.emit_staged()

    assert called == ["hello"]


def test_emit_staged_dispatches_multiple_events_same_namespace():
    called = []

    def handler(data: str) -> None:
        called.append(data)

    broker.register_subscriber("test.event", handler)
    broker.stage("test.event", data="first")
    broker.stage("test.event", data="second")
    broker.stage("test.event", data="third")
    broker.emit_staged()

    assert called == ["first", "second", "third"]


def test_emit_staged_dispatches_multiple_namespaces():
    called = []

    def handler_one(data: str) -> None:
        called.append(("one", data))

    def handler_two(data: str) -> None:
        called.append(("two", data))

    broker.register_subscriber("test.one", handler_one)
    broker.register_subscriber("test.two", handler_two)
    broker.stage("test.one", data="a")
    broker.stage("test.two", data="b")
    broker.emit_staged()

    assert ("one", "a") in called
    assert ("two", "b") in called


def test_emit_staged_flushes_by_default():
    def handler(data: str) -> None:
        pass

    broker.register_subscriber("test.event", handler)
    broker.stage("test.event", data="hello")
    broker.emit_staged()

    assert broker.get_staged_count() == 0


def test_emit_staged_flush_false_preserves_queue():
    called = []

    def handler(data: str) -> None:
        called.append(data)

    broker.register_subscriber("test.event", handler)
    broker.stage("test.event", data="hello")
    broker.emit_staged(flush=False)

    assert called == ["hello"]
    assert broker.get_staged_count("test.event") == 1


def test_emit_staged_flush_false_can_dispatch_again():
    called = []

    def handler(data: str) -> None:
        called.append(data)

    broker.register_subscriber("test.event", handler)
    broker.stage("test.event", data="hello")
    broker.emit_staged(flush=False)
    broker.emit_staged(flush=False)

    assert called == ["hello", "hello"]


def test_emit_staged_empty_queue_does_not_raise():
    broker.emit_staged()


def test_emit_staged_skips_async_subscribers():
    called = []

    async def async_handler(data: str) -> None:
        called.append(data)

    broker.register_subscriber("test.event", async_handler)
    broker.stage("test.event", data="hello")
    broker.emit_staged()

    assert called == []


def test_emit_staged_validates_signatures():
    def handler(data: str) -> None:
        pass

    broker.register_subscriber("test.event", handler)
    broker.stage("test.event", wrong_arg="oops")

    with pytest.raises(broker.EmitArgumentError):
        broker.emit_staged()


def test_emit_staged_events_staged_during_dispatch_survive():
    """Events staged inside a subscriber during emit_staged survive for the next call."""

    def handler(data: str) -> None:
        broker.stage("test.event", data="staged_during_dispatch")

    broker.register_subscriber("test.event", handler)
    broker.stage("test.event", data="initial")
    broker.emit_staged()

    assert broker.get_staged_count() == 1


def test_emit_staged_does_not_dispatch_to_async_subscribers():
    sync_called = []
    async_called = []

    def sync_handler(data: str) -> None:
        sync_called.append(data)

    async def async_handler(data: str) -> None:
        async_called.append(data)

    broker.register_subscriber("test.event", sync_handler)
    broker.register_subscriber("test.event", async_handler)
    broker.stage("test.event", data="hello")
    broker.emit_staged()

    assert sync_called == ["hello"]
    assert async_called == []


# -----emit_staged_async()-----------------------------------------------------


@pytest.mark.asyncio
async def test_emit_staged_async_dispatches_to_sync_subscribers():
    called = []

    def handler(data: str) -> None:
        called.append(data)

    broker.register_subscriber("test.event", handler)
    broker.stage("test.event", data="hello")
    await broker.emit_staged_async()

    assert called == ["hello"]


@pytest.mark.asyncio
async def test_emit_staged_async_dispatches_to_async_subscribers():
    called = []

    async def handler(data: str) -> None:
        called.append(data)

    broker.register_subscriber("test.event", handler)
    broker.stage("test.event", data="hello")
    await broker.emit_staged_async()

    assert called == ["hello"]


@pytest.mark.asyncio
async def test_emit_staged_async_dispatches_both_sync_and_async():
    called = []

    def sync_handler(data: str) -> None:
        called.append(("sync", data))

    async def async_handler(data: str) -> None:
        called.append(("async", data))

    broker.register_subscriber("test.event", sync_handler)
    broker.register_subscriber("test.event", async_handler)
    broker.stage("test.event", data="hello")
    await broker.emit_staged_async()

    assert ("sync", "hello") in called
    assert ("async", "hello") in called


@pytest.mark.asyncio
async def test_emit_staged_async_flushes_by_default():
    async def handler(data: str) -> None:
        pass

    broker.register_subscriber("test.event", handler)
    broker.stage("test.event", data="hello")
    await broker.emit_staged_async()

    assert broker.get_staged_count() == 0


@pytest.mark.asyncio
async def test_emit_staged_async_flush_false_preserves_queue():
    called = []

    async def handler(data: str) -> None:
        called.append(data)

    broker.register_subscriber("test.event", handler)
    broker.stage("test.event", data="hello")
    await broker.emit_staged_async(flush=False)

    assert called == ["hello"]
    assert broker.get_staged_count("test.event") == 1


@pytest.mark.asyncio
async def test_emit_staged_async_empty_queue_does_not_raise():
    await broker.emit_staged_async()


@pytest.mark.asyncio
async def test_emit_staged_async_validates_signatures():
    async def handler(data: str) -> None:
        pass

    broker.register_subscriber("test.event", handler)
    broker.stage("test.event", wrong_arg="oops")

    with pytest.raises(broker.EmitArgumentError):
        await broker.emit_staged_async()


@pytest.mark.asyncio
async def test_emit_staged_async_dispatches_multiple_events_in_order():
    called = []

    async def handler(data: str) -> None:
        called.append(data)

    broker.register_subscriber("test.event", handler)
    broker.stage("test.event", data="first")
    broker.stage("test.event", data="second")
    broker.stage("test.event", data="third")
    await broker.emit_staged_async()

    assert called == ["first", "second", "third"]


# -----clear_staged()----------------------------------------------------------


def test_clear_staged_empties_registry():
    broker.stage("test.event", data="hello")
    broker.clear_staged()

    assert broker.get_staged_count() == 0


def test_clear_staged_does_not_dispatch():
    called = []

    def handler(data: str) -> None:
        called.append(data)

    broker.register_subscriber("test.event", handler)
    broker.stage("test.event", data="hello")
    broker.clear_staged()

    assert called == []


def test_clear_staged_empty_does_not_raise():
    broker.clear_staged()
