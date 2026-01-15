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

- **The Broker** - The central event system
- **Namespaces** - Dot-notation event channels (e.g., `system.io.file_opened`)
- **Subscribers** - Callbacks that receive events
- **Transformers** - Middleware that modifies or filters events before delivery
- **Emitters** - Code that produces events via `emit()` or `emit_async()`

## Subscribing to Events

### Basic Subscription

```python
import broker

# Decorator style
@broker.subscribe("system.io.file")
def print_filename(filename: str) -> None:
    print(f'File accessed: {filename}')

# Or programmatic registration
broker.register_subscriber("system.io.file", print_filename)
```

### Wildcard Subscriptions

Subscribe to multiple namespaces using `*`:

```python
# Listen to all events under 'file'
@broker.subscribe("file.*")
def on_any_file_event(**kwargs) -> None:  # Must accept **kwargs
    print(f'File event: {kwargs}')

broker.emit('file.saved', filename='data.json', size=2048)
broker.emit('file.deleted', filename='temp.txt', size=512)
```

### Priorities

Control execution order with priority values (higher = earlier):

```python
@broker.subscribe('system.alert', priority=10)
def critical_handler(message: str) -> None:
    print('CRITICAL:', message)

@broker.subscribe('system.alert', priority=1)
def log_handler(message: str) -> None:
    print('Logged:', message)

broker.emit('system.alert', message='Disk full')
# Output:
# CRITICAL: Disk full
# Logged: Disk full
```

### Unsubscribing

```python
broker.unregister_subscriber('file.saved', on_file_saved)
```

## Emitting Events

### Synchronous Events

```python
# Emits to all synchronous subscribers only
broker.emit('process.data', value=42, status='ready')
```

### Asynchronous Events

```python
import asyncio

async def async_handler(data: str) -> None:
    await asyncio.sleep(0.1)
    print(f'Async: {data}')

def sync_handler(data: str) -> None:
    print(f'Sync: {data}')

broker.register_subscriber('process.data', async_handler)
broker.register_subscriber('process.data', sync_handler)

# emit() calls sync handlers only
broker.emit('process.data', data='test')  # Only sync_handler runs

# emit_async() calls both sync and async handlers
await broker.emit_async('process.data', data='test')  # Both run
```

## Signature Validation

The broker validates that all subscribers and emitters use consistent argument signatures:

```python
@broker.subscribe('user.login')
def first_subscriber(username: str, user_id: int) -> None:
    pass

# This will raise an exception - signature mismatch
@broker.subscribe('user.login')
def wrong_signature(username: str, email: str) -> None:  # ❌ Different args
    pass

# This will also raise an exception
broker.emit('user.login', username='alice', email='[email protected]')  # ❌ Wrong args
```

The first subscriber sets the expected signature for that namespace.

## Transformers

Transformers intercept and modify event data before it reaches subscribers. They execute in priority order and are scoped to specific namespaces.

### Basic Transformer

```python
import datetime

def add_timestamp(namespace: str, kwargs: dict) -> dict:
    """Add timestamp to all events."""
    now = datetime.datetime.now().time().isoformat()[:-4]
    kwargs['timestamp'] = now
    return kwargs

broker.register_transformer('system.*', add_timestamp, priority=10)

@broker.subscribe('system.startup')
def on_startup(timestamp: str) -> None:
    print(f'Started at {timestamp}')

broker.emit('system.startup')  # timestamp added automatically
```

### Blocking Events

Return `None` to prevent event delivery:

```python
def validate_user(namespace: str, kwargs: dict) -> dict | None:
    """Block events with invalid user_id."""
    if 'user_id' not in kwargs or kwargs['user_id'] < 0:
        return None  # Event blocked - subscribers never called
    return kwargs

broker.register_transformer('user.*', validate_user)
broker.emit('user.login', user_id=-1)  # Blocked silently
```

### Transformer Priority

Higher priority transformers execute first:

```python
def normalize(namespace: str, kwargs: dict) -> dict:
    kwargs['value'] = kwargs['value'].lower()
    return kwargs

def validate(namespace: str, kwargs: dict) -> dict | None:
    if not kwargs['value'].isalnum():
        return None
    return kwargs

# Normalize before validating
broker.register_transformer('input', normalize, priority=10)
broker.register_transformer('input', validate, priority=5)
```

### Common Use Cases

**Data Enrichment**
```python
def enrich_user_data(namespace: str, kwargs: dict) -> dict:
    if 'user_id' in kwargs:
        kwargs['user_name'] = get_user_name(kwargs['user_id'])
        kwargs['permissions'] = get_permissions(kwargs['user_id'])
    return kwargs

broker.register_transformer('user.*', enrich_user_data)
```

**Path Normalization**
```python
from pathlib import Path

def normalize_paths(namespace: str, kwargs: dict) -> dict:
    if 'filepath' in kwargs:
        kwargs['filepath'] = str(Path(kwargs['filepath']).absolute())
    return kwargs

broker.register_transformer('file.*', normalize_paths)
```

**Event Logging**
```python
def log_events(namespace: str, kwargs: dict) -> dict:
    print(f"[{namespace}] {kwargs}")
    return kwargs  # Pass through unchanged

broker.register_transformer('*', log_events, priority=100)  # Log everything
```

**Validation and Filtering**
```python
def validate_required_fields(namespace: str, kwargs: dict) -> dict | None:
    required = ['id', 'action', 'timestamp']
    if not all(field in kwargs for field in required):
        return None  # Block incomplete events
    return kwargs
```

## Exception Handling

### Subscriber Exception Handlers

Configure how the broker handles errors in subscriber callbacks:

```python
from broker import handlers

# Stop and Log (default) - logs error and stops delivery
broker.set_subscriber_exception_handler(
    handlers.stop_and_log_subscriber_exception
)

# Log and Continue - logs but continues to next subscriber
broker.set_subscriber_exception_handler(
    handlers.log_and_continue_subscriber_exception
)

# Silent - ignores all exceptions and continues
broker.set_subscriber_exception_handler(
    handlers.silent_subscriber_exception
)

# Collecting - captures exceptions for batch review
handlers.exceptions_caught.clear()
broker.set_subscriber_exception_handler(
    handlers.collect_subscriber_exception
)
broker.emit('event', data='test')
for error in handlers.exceptions_caught:
    print(f"Error in {error['namespace']}: {error['exception']}")

# Custom handler
def custom_handler(callback: Callable, namespace: str, exception: Exception) -> bool:
    """Return True to stop delivery, False to continue."""
    if isinstance(exception, ValueError):
        return True  # Stop on ValueError
    return False  # Continue on other exceptions

broker.set_subscriber_exception_handler(custom_handler)

# Disable (re-raise all exceptions)
broker.set_subscriber_exception_handler(None)
```

### Transformer Exception Handlers

Similar handlers for transformer errors:

```python
from broker import handlers

# Stop and log transformer errors (blocks event)
broker.set_transformer_exception_handler(
    handlers.stop_and_log_transformer_exception
)

# Log and continue with next transformer
broker.set_transformer_exception_handler(
    handlers.log_and_continue_transformer_exception
)

# Silent mode
broker.set_transformer_exception_handler(
    handlers.silent_transformer_exception
)

# Collecting mode
handlers.transformer_exceptions_caught.clear()
broker.set_transformer_exception_handler(
    handlers.collecting_transformer_exception
)

# Custom handler
def custom_transformer_handler(transformer, namespace, exception):
    print(f"Transformer error: {exception}")
    return False  # Continue with next transformer

broker.set_transformer_exception_handler(custom_transformer_handler)

# Disable (re-raise exceptions)
broker.set_transformer_exception_handler(None)
```

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

### Available Notifications

**Subscriber Events**
- `BROKER_ON_SUBSCRIBER_ADDED` - New subscriber registered
- `BROKER_ON_SUBSCRIBER_REMOVED` - Subscriber unregistered
- `BROKER_ON_SUBSCRIBER_COLLECTED` - Subscriber garbage collected

**Transformer Events**
- `BROKER_ON_TRANSFORMER_ADDED` - New transformer registered
- `BROKER_ON_TRANSFORMER_REMOVED` - Transformer unregistered
- `BROKER_ON_TRANSFORMER_COLLECTED` - Transformer garbage collected

**Emission Events**
- `BROKER_ON_EMIT` - Event emitted via `emit()`
- `BROKER_ON_EMIT_ASYNC` - Event emitted via `emit_async()`
- `BROKER_ON_EMIT_ALL` - Any emission (sync or async)

**Namespace Events**
- `BROKER_ON_NAMESPACE_CREATED` - New namespace created
- `BROKER_ON_NAMESPACE_DELETED` - Namespace removed

## Advanced Features

### Flexible Callbacks

Use `**kwargs` for flexible argument handling:

```python
def flexible_handler(**kwargs: object) -> None:
    print('Received:', kwargs)

broker.register_subscriber('flexible.event', flexible_handler)
broker.emit('flexible.event', foo='bar', count=42, active=True)
```

### Reimport Protection

The broker is a singleton with reimport safeguards. Reimporting raises `ImportError` to prevent data loss:

```python
import broker
import importlib
importlib.reload(broker)  # Raises ImportError
```

This protects the global namespace/subscriber table from being accidentally cleared.

## Complete Example

```python
import asyncio
import broker
from broker import handlers

# Configure exception handling
broker.set_subscriber_exception_handler(handlers.log_and_continue_subscriber_exception)

# Add data enrichment transformer
def add_metadata(namespace: str, kwargs: dict) -> dict:
    kwargs['source'] = 'app'
    kwargs['version'] = '1.0'
    return kwargs

broker.register_transformer('*', add_metadata, priority=10)

# Add validation transformer
def validate_file_size(namespace: str, kwargs: dict) -> dict | None:
    if 'size' in kwargs and kwargs['size'] > 10_000_000:
        print(f"File too large: {kwargs.get('filename')}")
        return None  # Block large files
    return kwargs

broker.register_transformer('file.*', validate_file_size, priority=5)

# Register handlers with priorities
@broker.subscribe('file.saved', priority=10)
def backup_file(filename: str, size: int, **kwargs) -> None:
    print(f'Backing up: {filename}')

@broker.subscribe('file.saved', priority=5)
def log_file(filename: str, size: int, **kwargs) -> None:
    print(f'Logged: {filename} ({size} bytes, v{kwargs["version"]})')

@broker.subscribe('file.*')
async def async_notify(**kwargs) -> None:
    await asyncio.sleep(0.1)
    print(f'Notification sent for: {kwargs.get("filename")}')

# Emit events
broker.emit('file.saved', filename='small.txt', size=1024)
# Output:
# Backing up: small.txt
# Logged: small.txt (1024 bytes, v1.0)

await broker.emit_async('file.saved', filename='document.txt', size=2048)
# Output:
# Backing up: document.txt
# Logged: document.txt (2048 bytes, v1.0)
# Notification sent for: document.txt

# This gets blocked by the validator
broker.emit('file.saved', filename='huge.bin', size=50_000_000)
# Output:
# File too large: huge.bin
```

## API Reference

### Core Functions

- `subscribe(namespace: str, priority: int = 0)` - Decorator for registering subscribers
- `register_subscriber(namespace: str, callback: Callable, priority: int = 0)` - Register a subscriber programmatically
- `unregister_subscriber(namespace: str, callback: Callable)` - Remove a subscriber
- `register_transformer(namespace: str, transformer: Callable, priority: int = 0)` - Add event transformer
- `emit(namespace: str, **kwargs)` - Emit event to synchronous subscribers
- `emit_async(namespace: str, **kwargs)` - Emit event to all subscribers (async)
- `set_subscriber_exception_handler(handler: Callable | None)` - Configure subscriber error handling
- `set_transformer_exception_handler(handler: Callable | None)` - Configure transformer error handling
- `set_flag_states(**flags)` - Enable broker event notifications
