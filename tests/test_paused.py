"""
Unit tests for the PausedContext context manager.
"""

import pytest

import broker


@pytest.fixture(autouse=True)
def clear_broker():
    """Reset broker state before and after each test."""
    broker.clear()
    yield
    broker.clear()


def test_emit_suppressed_while_paused():
    called = []

    def handler(data: str) -> None:
        called.append(data)

    broker.register_subscriber("test.event", handler)

    with broker.PausedContext():
        broker.emit("test.event", data="hello")

    assert called == []


def test_emit_resumes_after_context_exits():
    called = []

    def handler(data: str) -> None:
        called.append(data)

    broker.register_subscriber("test.event", handler)

    with broker.PausedContext():
        broker.emit("test.event", data="suppressed")

    broker.emit("test.event", data="delivered")

    assert called == ["delivered"]


# -----Async-------------------------------------------------------------------


@pytest.mark.asyncio
async def test_emit_async_suppressed_while_paused():
    called = []

    async def handler(data: str) -> None:
        called.append(data)

    broker.register_subscriber("test.event", handler)

    with broker.PausedContext():
        await broker.emit_async("test.event", data="hello")

    assert called == []


@pytest.mark.asyncio
async def test_emit_async_resumes_after_context_exits():
    called = []

    async def handler(data: str) -> None:
        called.append(data)

    broker.register_subscriber("test.event", handler)

    with broker.PausedContext():
        await broker.emit_async("test.event", data="suppressed")

    await broker.emit_async("test.event", data="delivered")

    assert called == ["delivered"]


# -----Exception Safety--------------------------------------------------------

def test_emit_resumes_after_exception_in_context():
    called = []

    def handler(data: str) -> None:
        called.append(data)

    broker.register_subscriber("test.event", handler)

    try:
        with broker.PausedContext():
            raise RuntimeError("something went wrong")
    except RuntimeError:
        pass

    broker.emit("test.event", data="delivered")

    assert called == ["delivered"]


def test_exception_propagates_out_of_context():
    with pytest.raises(RuntimeError):
        with broker.PausedContext():
            raise RuntimeError("something went wrong")


def test_nested_context_keeps_events_suppressed_until_outer_exit():
    called = []

    def handler(data: str) -> None:
        called.append(data)

    broker.register_subscriber("test.event", handler)

    with broker.PausedContext():
        with broker.PausedContext():
            broker.emit("test.event", data="inner")
        broker.emit("test.event", data="still suppressed")

    broker.emit("test.event", data="delivered")

    assert called == ["delivered"]


# -----Isolation---------------------------------------------------------------


def test_paused_does_not_affect_staging():
    called = []

    def handler(data: str) -> None:
        called.append(data)

    broker.register_subscriber("test.event", handler)

    with broker.PausedContext():
        broker.stage("test.event", data="hello")

    broker.emit_staged()

    assert called == ["hello"]


def test_emit_resumes_across_all_namespaces_after_exit():
    called = []

    def handler_one(data: str) -> None:
        called.append(("one", data))

    def handler_two(data: str) -> None:
        called.append(("two", data))

    broker.register_subscriber("test.one", handler_one)
    broker.register_subscriber("test.two", handler_two)

    with broker.PausedContext():
        broker.emit("test.one", data="suppressed")
        broker.emit("test.two", data="suppressed")

    broker.emit("test.one", data="a")
    broker.emit("test.two", data="b")

    assert called == [("one", "a"), ("two", "b")]
