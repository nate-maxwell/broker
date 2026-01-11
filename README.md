# Broker

A simple message broker system for python.
Supports sync and async events.

## Subscribing and Namespaces

Subscriptions can be done either by decorating functions or static methods, or
by using `broker.register_subscriber("namespace", callback)`.

End-points can subscribe to namespaces using dot notation like
`system.io.file_opened` or wildcard namespace subscriptions for specific levels
downwards like `system.io.*`.

```python
import broker

@broker.subscribe("system.io.file")
def print_filename(filename: str) -> None:
    print(f'User is attempting to access file: {filename}')

# --or--

broker.register_subscriber("system.io.file", print_filename)
```
 
## Priorities

Subscriptions can add a priority integer that will dictate the subscriber
execution order:
```python
broker.subscribe('file.io.*', my_func, priority=10)
```

Higher priorities are executed first.

## Expressive Arguments

Events can be emitted with any keyword arguments:
```python
broker.emit('file.io.open_file', path=Path('D:/dir/file.txt'))
```

## Signature Validation

If a subscriber to a namespace with keyword arguments different from previous
subscribers, or an event is emitted using different keywords than subscribers
are expecting, an explicit exception is raised. First subscribers set the
expectation and following subscribers + emitters are validated.

## Exception Handling

The broker provides configurable exception handling for errors that occur during
subscriber callback execution. By default, exceptions are logged and stop
delivery to remaining subscribers.

### Exception Handler Types

**Stop on Exception (Default)**

```python
from broker import handlers

# Default behavior - logs error and stops delivery
broker.set_subscriber_exception_handler(exceptions.stop_on_exception_handler)
```

**Silent Handler** - Ignores exceptions and continues delivery:

```python
broker.set_subscriber_exception_handler(exceptions.silent_exception_handler)
```

**Collecting Handler** - Captures all exceptions for batch processing:

```python
exceptions.exceptions_caught.clear()
broker.set_subscriber_exception_handler(exceptions.collecting_exception_handler)

broker.emit('event', data='test')

# Review collected exceptions
for error in exceptions.exceptions_caught:
    print(f"Error in {error['namespace']}: {error['exception']}")
```

**Custom Handler** - Create your own exception policy:

```python
def custom_handler(callback: Callable, namespace: str, exception: Exception) -> bool:
    # Log the error
    print(f"Error in {namespace}: {exception}")

    # Return True to stop delivery and raise, False to ignore and continue
    if isinstance(exception, ValueError):
        return True  # Stop on ValueError
    return False  # Continue on other exceptions


broker.set_subscriber_exception_handler(custom_handler)
```

**Disable Handler** - Re-raise all exceptions:

```python
broker.set_subscriber_exception_handler(None)  # Exceptions propagate normally
```

Exception handlers work with both `emit()` and `emit_async()`, and apply to all
subscriber types including sync callbacks, async callbacks, instance methods,
and lambdas.

## Transformers

Transformers intercept and modify event data before it reaches subscribers. They
execute in priority order and can modify arguments, add metadata, validate data,
or block events entirely. Transformers are scoped to namespaces and not globally
applied.

### Registering Transformers

```python
import datetime

def add_timestamp(namespace: str, kwargs: dict) -> dict:
    """Add timestamp to all events."""
    now = datetime.datetime.now().time().isoformat()[:-4]
    kwargs['timestamp'] = now
    return kwargs

broker.register_transformer('system.*', add_timestamp, priority=10)
broker.emit('system.io.file', filename='data.txt')  # Gets timestamp automatically
```

### Blocking Events

Transformers can block event propagation by returning `None`:

```python
def validate_user(namespace: str, kwargs: dict) -> dict | None:
    """Block events with invalid user_id."""
    if 'user_id' not in kwargs or kwargs['user_id'] < 0:
        return None  # Block the event
    return kwargs

broker.register_transformer('user.*', validate_user)
broker.emit('user.login', user_id=-1)  # Blocked - no subscribers called
```

### Priority Execution

Higher priority transformers execute first:

```python
def step1(namespace: str, kwargs: dict) -> dict:
    kwargs['step'] = 1
    return kwargs

def step2(namespace: str, kwargs: dict) -> dict:
    kwargs['step'] = 2
    return kwargs

broker.register_transformer('pipeline', step1, priority=10)  # Runs first
broker.register_transformer('pipeline', step2, priority=5)   # Runs second
```

### Transformer Exception Handling

Transformers support exception handlers similar to subscriber handlers:

```python
from broker import handlers

# Stop on transformer errors (logs and blocks event)
broker.set_transformer_exception_handler(
    handlers.stop_and_log_transformer_exception
)

# Silent mode - ignore transformer errors and continue
broker.set_transformer_exception_handler(
    handlers.silent_transformer_exception
)

# Collect transformer errors for review
handlers.transformer_exceptions_caught.clear()
broker.set_transformer_exception_handler(
    handlers.collecting_transformer_exception
)

# Custom handler
def custom_handler(transformer, namespace, exception):
    print(f"Transformer error: {exception}")
    return False  # Continue with next transformer

broker.set_transformer_exception_handler(custom_handler)

# Disable handler (re-raise exceptions)
broker.set_transformer_exception_handler(None)
```

### Common Use Cases

**Data enrichment:**
```python
def enrich_user_data(namespace: str, kwargs: dict) -> dict:
    if 'user_id' in kwargs:
        kwargs['user_name'] = get_user_name(kwargs['user_id'])
    return kwargs
```

**Validation:**
```python
def validate_required_fields(namespace: str, kwargs: dict) -> dict | None:
    required = ['id', 'action']
    if not all(field in kwargs for field in required):
        return None  # Block invalid events
    return kwargs
```

**Logging:**
```python
def log_events(namespace: str, kwargs: dict) -> dict:
    print(f"[{namespace}] {kwargs}")
    return kwargs  # Don't modify, just observe
```

**Normalization:**
```python
from pathlib import Path

def normalize_paths(namespace: str, kwargs: dict) -> dict:
    if 'filepath' in kwargs:
        kwargs['filepath'] = str(Path(kwargs['filepath']).absolute())
    return kwargs
```

## Broker Event Notification

Actions within the broker itself can be subscribed to, including:
* Subscriber addition
* Subscriber removal
* Subscriber deletion from GC
* Synchronous event emitting
* Asynchronous event emitting
* All event emitting
* Namespace creation
* Namespace deletion

This is easily achieved using broker constants like so:
```python
@broker.subscribe(broker.BROKER_ON_SUBSCRIBER_ADDED)
def on_subscriber_added(using: str) -> None:
    print(f'New subscriber to namespace: {using}')
```

Available notifications are:
* BROKER_ON_SUBSCRIBER_ADDED
* BROKER_ON_SUBSCRIBER_REMOVED
* BROKER_ON_SUBSCRIBER_COLLECTED
* BROKER_ON_EMIT
* BROKER_ON_EMIT_ASYNC
* BROKER_ON_EMIT_ALL
* BROKER_ON_NAMESPACE_CREATED
* BROKER_ON_NAMESPACE_DELETED


## Reimport Protection

If the broker is reimported an `ImportError` is raised.

Broker is a singleton with a global namespace/subscribers table. To prevent data
loss the broker contains a reimport safeguard to keep the table from being
cleared from reimporting. This plus the protective closure makes it **very**
difficult to access outside the official interfaces.

# Example

```python
import broker


# Basic usage - register and emit
def on_file_saved(filename: str, size: int) -> None:
    print(f'File saved: {filename} ({size} bytes)')


broker.register_subscriber('file.save', on_file_saved)
broker.emit('file.save', filename='document.txt', size=1024)


# Wildcard subscriptions
def on_any_file_event(filename: str, size: int) -> None:
    print(f'File event: {filename}')


broker.register_subscriber('file.*', on_any_file_event)
broker.emit('file.save', filename='data.json', size=2048)
broker.emit('file.delete', filename='temp.txt', size=512)


# Priority-based execution (higher priority runs first)
def high_priority_handler(message: str) -> None:
    print('High priority:', message)


def low_priority_handler(message: str) -> None:
    print('Low priority:', message)


broker.register_subscriber('system.alert', high_priority_handler, priority=10)
broker.register_subscriber('system.alert', low_priority_handler, priority=1)
broker.emit('system.alert', message='Warning!')

# Async callbacks
import asyncio


async def async_handler(data: str) -> None:
    await asyncio.sleep(0.1)
    print(f'Async processed: {data}')


def sync_handler(data: str) -> None:
    print(f'Sync processed: {data}')


broker.register_subscriber('process.data', async_handler)
broker.register_subscriber('process.data', sync_handler)

# Use emit() for sync only
broker.emit('process.data', data='example')  # Only calls sync_handler

# Use emit_async() for both sync and async
await broker.emit_async('process.data', data='example')  # Calls both


# Flexible callbacks with **kwargs
def flexible_handler(**kwargs: object) -> None:
    print('Received:', kwargs)


broker.register_subscriber('flexible.event', flexible_handler)
broker.emit('flexible.event', foo='bar', count=42, active=True)


# Exception handling example
def might_fail(value: int) -> None:
    if value < 0:
        raise ValueError('Negative values not allowed')
    print(f'Processed: {value}')


def always_succeeds(value: int) -> None:
    print('Cleanup complete')


broker.register_subscriber('process', might_fail, priority=10)
broker.register_subscriber('process', always_succeeds, priority=5)

# With silent handler, both callbacks run even if first fails
from broker import handlers

broker.set_exception_handler(exceptions.silent_exception_handler)

broker.emit('process', value=-1)  # Both callbacks execute

# Unregister subscribers
broker.unregister_subscriber('file.save', on_file_saved)
```
