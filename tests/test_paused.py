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


# -----Pausing-----------------------------------------------------------------


def test_emit_suppressed_while_paused():
    called = []

    def handler(data: str) -> None:
        called.append(data)

    broker.register_subscriber("test.event", handler)

    with broker.paused():
        broker.emit("test.event", data="hello")

    assert called == []


def test_emit_resumes_after_context_exits():
    called = []

    def handler(data: str) -> None:
        called.append(data)

    broker.register_subscriber("test.event", handler)

    with broker.paused():
        broker.emit("test.event", data="suppressed")

    broker.emit("test.event", data="delivered")

    assert called == ["delivered"]


def test_paused_counter_zero_by_default():
    assert broker._paused == 0


def test_paused_counter_increments_on_enter():
    with broker.paused():
        assert broker._paused == 1


def test_paused_counter_decrements_on_exit():
    with broker.paused():
        pass

    assert broker._paused == 0


# -----Async-------------------------------------------------------------------


@pytest.mark.asyncio
async def test_emit_async_suppressed_while_paused():
    called = []

    async def handler(data: str) -> None:
        called.append(data)

    broker.register_subscriber("test.event", handler)

    with broker.paused():
        await broker.emit_async("test.event", data="hello")

    assert called == []


@pytest.mark.asyncio
async def test_emit_async_resumes_after_context_exits():
    called = []

    async def handler(data: str) -> None:
        called.append(data)

    broker.register_subscriber("test.event", handler)

    with broker.paused():
        await broker.emit_async("test.event", data="suppressed")

    await broker.emit_async("test.event", data="delivered")

    assert called == ["delivered"]


# -----Exception Safety--------------------------------------------------------


def test_paused_counter_restored_after_exception():
    try:
        with broker.paused():
            raise RuntimeError("something went wrong")
    except RuntimeError:
        pass

    assert broker._paused == 0


def test_emit_resumes_after_exception_in_context():
    called = []

    def handler(data: str) -> None:
        called.append(data)

    broker.register_subscriber("test.event", handler)

    try:
        with broker.paused():
            raise RuntimeError("something went wrong")
    except RuntimeError:
        pass

    broker.emit("test.event", data="delivered")

    assert called == ["delivered"]


def test_exception_propagates_out_of_context():
    with pytest.raises(RuntimeError):
        with broker.paused():
            raise RuntimeError("something went wrong")


# -----Nesting-----------------------------------------------------------------


def test_nested_contexts_increment_counter():
    with broker.paused():
        with broker.paused():
            assert broker._paused == 2


def test_nested_inner_exit_decrements_counter():
    with broker.paused():
        with broker.paused():
            pass
        assert broker._paused == 1


def test_nested_outer_exit_decrements_counter_to_zero():
    with broker.paused():
        with broker.paused():
            pass

    assert broker._paused == 0


def test_nested_emit_suppressed_while_inner_active():
    called = []

    def handler(data: str) -> None:
        called.append(data)

    broker.register_subscriber("test.event", handler)

    with broker.paused():
        with broker.paused():
            broker.emit("test.event", data="hello")

    assert called == []


def test_nested_emit_suppressed_after_inner_exits():
    called = []

    def handler(data: str) -> None:
        nonlocal called
        called.append(data)

    broker.register_subscriber("test.event", handler)

    with broker.paused():
        with broker.paused():
            pass
        broker.emit("test.event", data="still suppressed")

    # noinspection PyUnboundLocalVariable
    assert called == []


def test_nested_emit_resumes_after_all_contexts_exit():
    called = []

    def handler(data: str) -> None:
        nonlocal called
        called.append(data)

    broker.register_subscriber("test.event", handler)

    with broker.paused():
        with broker.paused():
            pass

    broker.emit("test.event", data="delivered")

    # noinspection PyUnboundLocalVariable
    assert called == ["delivered"]


def test_nested_exception_in_inner_restores_outer_depth():
    try:
        with broker.paused():
            try:
                with broker.paused():
                    raise RuntimeError("inner error")
            except RuntimeError:
                pass
            assert broker._paused == 1
    except RuntimeError:
        pass


def test_deeply_nested_counter():
    with broker.paused():
        with broker.paused():
            with broker.paused():
                assert broker._paused == 3
        assert broker._paused == 1

    assert broker._paused == 0


# -----Isolation---------------------------------------------------------------


def test_paused_does_not_affect_staging():
    called = []

    def handler(data: str) -> None:
        called.append(data)

    broker.register_subscriber("test.event", handler)

    with broker.paused():
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

    with broker.paused():
        broker.emit("test.one", data="suppressed")
        broker.emit("test.two", data="suppressed")

    broker.emit("test.one", data="a")
    broker.emit("test.two", data="b")

    assert called == [("one", "a"), ("two", "b")]
