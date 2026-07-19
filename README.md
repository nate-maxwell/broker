# Broker

A lightweight message broker system for Python with support for sync/async events, transformers, and flexible event routing.

## Quick Start

```python
import broker

# Subscribe to events
@broker.subscribe("file.saved")
def on_file_saved(filename: str, size: int) -> None:
    print(f'Saved: {filename} ({size} bytes)')

# Emit events
broker.emit('file.saved', filename='document.txt', size=1024)
```

## Core Concepts

The broker comprises 5 components:

- **The Registry** - The central event tracking system
- **Namespaces** - Dot-notation event channels (e.g., `system.io.file_opened`)
- **Subscribers** - Callbacks that receive events
- **Transformers** - Middleware that modifies or filters events before delivery
- **Emitters** - Code that produces events via `emit()` or `emit_async()`

## Subscribing to Events

```python
import broker

# Decorator style
@broker.subscribe("system.io.file")
def print_filename(filename: str) -> None:
    print(f'File accessed: {filename}')

# Or programmatic registration
broker.register_subscriber("system.io.file", print_filename)
```

More info can be found [here](./docs/Subscribers.md).

## Emitting Events

```python
import broker

# Subscribe to events
@broker.subscribe("file.saved")
def on_file_saved(filename: str, size: int) -> None:
    print(f'Saved: {filename} ({size} bytes)')

# Emit events
broker.emit('file.saved', filename='document.txt', size=1024)

# Asynchronously emit events
await broker.emit_async('file.saved', filename='document.txt', size=1024)
```

More info can be found [here](./docs/Emitting.md).

## Signature Validation

The first subscriber establishes the required arguments for a namespace. Child
namespaces inherit those arguments and may add more:

```python
@broker.subscribe('user')
def on_user(username: str) -> None:
    print(username)

@broker.subscribe('user.login')
def on_login(username: str, user_id: int) -> None:
    print(user_id)

broker.emit('user.login', username='alice', user_id=42)
# Output: Alice
# Output: 42
```

Child events bubble to subscribers of parent namespaces as well. Each subscriber
receives only it's named arguments unless it explicitly accepts `**kwargs`.
Transformers run before required arguments are validated.

## Transformers

Transformers intercept and modify event data before it reaches subscribers.
They execute in priority order and obey namespaces just like subscribers.

### Basic Transformer

```python
import datetime

@broker.transform("system", priority=10)
def add_timestamp(namespace: str, kwargs: dict) -> dict:
    """Add timestamp to all events."""
    now = datetime.datetime.now().time().isoformat()[:-4]
    kwargs['timestamp'] = now
    return kwargs

@broker.subscribe('system.startup')
def on_startup(timestamp: str) -> None:
    print(f'Started at {timestamp}')

broker.emit('system.startup')  # timestamp added automatically
```

More info can be found [here](./docs/Transformers.md).

## Exception Handling

Configure how the broker handles errors in subscribers and transformers.

More info can be found [here](./docs/Handlers.md).

## Advanced Features

### Flexible Callbacks

Use `**kwargs` for flexible argument handling:

```python
def flexible_handler(**kwargs: object) -> None:
    print('Received:', kwargs)

broker.register_subscriber('flexible.event', flexible_handler)
broker.emit('flexible.event', foo='bar', count=42, active=True)
```

### Weak References

The broker will not maintain references to items, preventing them from being
culled by the garbage collector.
Deletion of items referenced by the broker can be subscribed to.

## Broker Event Notifications

Subscribe to internal broker events to monitor subscription changes, emissions, and namespace lifecycle:

```python
# Enable specific notifications
broker.set_flag_states(on_subscribe=True, on_emit=True)

@broker.subscribe(broker.BROKER_ON_SUBSCRIBER_ADDED)
def on_subscriber_added(using: str) -> None:
    print(f'New subscriber to: {using}')

@broker.subscribe(broker.BROKER_ON_EMIT)
def on_emit(namespace: str, kwargs: dict) -> None:
    print(f'Event emitted: {namespace}')
```

More info can be found [here](./docs/EventNotifies.md).

## Reimport Protection

The broker's internal registry is protected against reimporting. If
`broker.private.registry` has already been imported, a second import or reload
raises `ImportError` to prevent the subscriber table from being cleared:

```python
import importlib
import broker.private.registry as registry

importlib.reload(registry)  # Raises ImportError
```

To bypass the guard in controlled environments, set:

```python
import os

os.environ["BROKER_REIMPORT_GUARD"] = "false"
```

This protects the global namespace/subscriber table from being accidentally cleared.

## API References
Can be found [here](./docs/APIReferences.md).
