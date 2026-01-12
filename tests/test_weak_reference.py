"""
Unit tests for weak reference functionality and garbage collection
notifications.

When a callback is collected by the GC or deleted by user, the broker should
not keep the object alive by maintaining a reference and should notify invested
systems that the item was culled.
"""

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


def test_weak_reference_regular_function() -> None:
    """
    Test that regular functions are held with weak references and can be
    collected.
    """
    broker.clear()
    invocations: list[str] = []

    def my_callback(data: str) -> None:
        invocations.append(data)

    broker.register_subscriber("test.event", my_callback)

    broker.emit("test.event", data="first")
    assert len(invocations) == 1
    assert invocations[0] == "first"

    del my_callback
    gc.collect()

    broker.emit("test.event", data="second")
    assert len(invocations) == 1


def test_weak_reference_instance_method() -> None:
    """
    Test that instance methods are held with weak references and cleaned up
    when object dies.
    """
    broker.clear()

    class Handler:
        def __init__(self) -> None:
            self.invocations: list[str] = []

        def on_event(self, data: str) -> None:
            self.invocations.append(data)

    handler = Handler()
    broker.register_subscriber("test.event", handler.on_event)

    broker.emit("test.event", data="first")
    assert len(handler.invocations) == 1

    del handler
    gc.collect()

    broker.emit("test.event", data="second")


def test_weak_reference_lambda() -> None:
    """Test that lambda functions are held with weak references."""
    broker.clear()
    invocations: list[str] = []

    my_lambda = lambda data: invocations.append(data)
    broker.register_subscriber("test.event", my_lambda)

    broker.emit("test.event", data="first")
    assert len(invocations) == 1

    del my_lambda
    gc.collect()

    broker.emit("test.event", data="second")
    assert len(invocations) == 1


def test_on_collected_notification_flag_off() -> None:
    """Test that no notification is sent when notify_on_collected is False."""
    broker.clear()
    broker.set_flag_states(on_subscriber_collected=False)
    collected_namespaces: list[str] = []

    @broker.subscribe(broker.BROKER_ON_SUBSCRIBER_COLLECTED)
    def on_collected(using: str) -> None:
        collected_namespaces.append(using)

    my_callback = lambda data: None
    broker.register_subscriber("test.event", my_callback)

    del my_callback
    gc.collect()

    assert len(collected_namespaces) == 0


def test_on_collected_notification_flag_on() -> None:
    """Test that notification is sent when notify_on_collected is True."""
    broker.clear()
    collected_namespaces: list[str] = []

    @broker.subscribe(broker.BROKER_ON_SUBSCRIBER_COLLECTED)
    def on_collected(using: str) -> None:
        collected_namespaces.append(using)

    broker.set_flag_states(on_subscriber_collected=True)

    my_callback = lambda data: None
    broker.register_subscriber("test.event", my_callback)

    del my_callback
    gc.collect()

    assert "test.event" in collected_namespaces


def test_on_collected_multiple_namespaces() -> None:
    """Test that collection notifications track multiple namespaces correctly."""
    broker.clear()
    collected_namespaces: list[str] = []

    @broker.subscribe(broker.BROKER_ON_SUBSCRIBER_COLLECTED)
    def on_collected(using: str) -> None:
        collected_namespaces.append(using)

    broker.set_flag_states(on_subscriber_collected=True)

    callback1 = lambda data: None
    callback2 = lambda data: None
    callback3 = lambda data: None

    broker.register_subscriber("namespace.one", callback1)
    broker.register_subscriber("namespace.two", callback2)
    broker.register_subscriber("namespace.three", callback3)

    del callback1
    gc.collect()
    assert "namespace.one" in collected_namespaces

    del callback2
    gc.collect()
    assert "namespace.two" in collected_namespaces

    del callback3
    gc.collect()
    assert "namespace.three" in collected_namespaces

    assert len(collected_namespaces) == 3


def test_on_collected_with_instance_method() -> None:
    """Test that collection notification works with instance methods."""
    broker.clear()
    collected_namespaces: list[str] = []

    @broker.subscribe(broker.BROKER_ON_SUBSCRIBER_COLLECTED)
    def on_collected(using: str) -> None:
        collected_namespaces.append(using)

    broker.set_flag_states(on_subscriber_collected=True)

    class Handler(object):
        def on_event(self, data: str) -> None:
            pass

    handler = Handler()
    broker.register_subscriber("test.method", handler.on_event)

    del handler
    gc.collect()

    assert "test.method" in collected_namespaces


def test_on_collected_does_not_trigger_for_notify_namespaces() -> None:
    """Test that broker notify namespaces don't trigger collection notifications."""
    broker.clear()
    collected_namespaces: list[str] = []

    @broker.subscribe(broker.BROKER_ON_SUBSCRIBER_COLLECTED)
    def on_collected(using: str) -> None:
        collected_namespaces.append(using)

    broker.set_flag_states(on_subscriber_collected=True)

    notify_callback = lambda using: None
    broker.register_subscriber(broker.BROKER_ON_SUBSCRIBER_ADDED, notify_callback)

    del notify_callback
    gc.collect()

    assert broker.BROKER_ON_SUBSCRIBER_ADDED not in collected_namespaces


def test_multiple_subscribers_one_collected() -> None:
    """Test that only the collected subscriber is removed, others remain."""
    broker.clear()
    invocations1: list[str] = []
    invocations2: list[str] = []

    callback1 = lambda data: invocations1.append(data)

    def callback2(data: str) -> None:
        invocations2.append(data)

    broker.register_subscriber("test.event", callback1)
    broker.register_subscriber("test.event", callback2)

    broker.emit("test.event", data="first")
    assert len(invocations1) == 1
    assert len(invocations2) == 1

    del callback1
    gc.collect()

    broker.emit("test.event", data="second")
    assert len(invocations1) == 1
    assert len(invocations2) == 2


def test_weak_reference_does_not_prevent_garbage_collection() -> None:
    """Test that subscribing a callback doesn't prevent it from being garbage collected."""
    broker.clear()

    class Observable:
        def __init__(self) -> None:
            self.alive = True

        def on_event(self, data: str) -> None:
            pass

        def __del__(self) -> None:
            self.alive = False

    obj = Observable()
    broker.register_subscriber("test.event", obj.on_event)

    assert obj.alive is True

    del obj
    gc.collect()


def test_on_collected_with_priority_subscribers() -> None:
    """Test that collection works correctly with priority-based subscribers."""
    broker.clear()
    collected_namespaces: list[str] = []

    @broker.subscribe(broker.BROKER_ON_SUBSCRIBER_COLLECTED)
    def on_collected(using: str) -> None:
        collected_namespaces.append(using)

    broker.set_flag_states(on_subscriber_collected=True)

    high_priority = lambda data: None
    low_priority = lambda data: None

    broker.register_subscriber("test.priority", high_priority, priority=10)
    broker.register_subscriber("test.priority", low_priority, priority=1)

    del high_priority
    gc.collect()

    assert collected_namespaces.count("test.priority") == 1

    del low_priority
    gc.collect()

    assert collected_namespaces.count("test.priority") == 2


@pytest.mark.asyncio
async def test_on_collected_with_async_callback() -> None:
    """Test that collection notification works with async callbacks."""
    broker.clear()
    collected_namespaces: list[str] = []

    @broker.subscribe(broker.BROKER_ON_SUBSCRIBER_COLLECTED)
    def on_collected(using: str) -> None:
        collected_namespaces.append(using)

    broker.set_flag_states(on_subscriber_collected=True)

    # noinspection PyUnusedLocal
    async def async_callback(data: str) -> None:
        pass

    my_async_callback = async_callback
    broker.register_subscriber("test.async", my_async_callback)

    del my_async_callback
    del async_callback
    gc.collect()

    assert "test.async" in collected_namespaces


def test_emit_after_all_subscribers_collected() -> None:
    """Test that emitting to a namespace with all subscribers collected doesn't error."""
    broker.clear()

    callback = lambda data: None
    broker.register_subscriber("test.event", callback)

    del callback
    gc.collect()

    broker.emit("test.event", data="test")


def test_wildcard_subscriber_collection() -> None:
    """Test that wildcard subscribers are properly collected."""
    broker.clear()
    collected_namespaces: list[str] = []

    @broker.subscribe(broker.BROKER_ON_SUBSCRIBER_COLLECTED)
    def on_collected(using: str) -> None:
        collected_namespaces.append(using)

    broker.set_flag_states(on_subscriber_collected=True)

    wildcard_callback = lambda data: None
    broker.register_subscriber("test.*", wildcard_callback)

    del wildcard_callback
    gc.collect()

    assert "test.*" in collected_namespaces
