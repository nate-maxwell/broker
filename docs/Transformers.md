## Transformers

Transformers intercept and modify event data before it reaches subscribers. They execute in priority order and are scoped to specific namespaces.

### Basic Transformer

```python
import datetime

@broker.transform('system', priority=10)
def add_timestamp(namespace: str, kwargs: dict) -> dict:
    """Add timestamp to all events."""
    now = datetime.datetime.now().time().isoformat()[:-4]
    kwargs['timestamp'] = now
    return kwargs

@broker.subscribe('system.startup')
def on_startup(timestamp: str) -> None:
    print(f'Started at {timestamp}')

broker.emit('system.startup')  # timestamp added automatically

# Output: Started at 14:32:16.32
```
Transformers do not alter the tracked signature for matching.

Signature validation happens after transformers intercept data, and validation
simply checks that the expected keywords are present. Transformers can add any
number of additional keywords, and as long as the expected keywords are present,
the validation will pass.

### Blocking Events

Return `None` to prevent event delivery:

```python
@broker.transform('user')
def validate_user(namespace: str, kwargs: dict) -> dict | None:
    """Block events with invalid user_id."""
    if 'user_id' not in kwargs or kwargs['user_id'] < 0:
        return None  # Event blocked - subscribers never called
    return kwargs

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
@broker.transform('user')
def enrich_user_data(namespace: str, kwargs: dict) -> dict:
    if 'user_id' in kwargs:
        kwargs['user_name'] = get_user_name(kwargs['user_id'])
        kwargs['permissions'] = get_permissions(kwargs['user_id'])
    return kwargs
```

**Path Normalization**
```python
from pathlib import Path

@broker.transform('file')
def normalize_paths(namespace: str, kwargs: dict) -> dict:
    if 'filepath' in kwargs:
        kwargs['filepath'] = str(Path(kwargs['filepath']).absolute())
    return kwargs
```

**Event Logging**
```python
@broker.transform('app')
def log_events(namespace: str, kwargs: dict) -> dict:
    print(f"[{namespace}] {kwargs}")
    return kwargs  # Pass through unchanged
```

**Validation and Filtering**
```python
def validate_required_fields(namespace: str, kwargs: dict) -> dict | None:
    required = ['id', 'action', 'timestamp']
    if not all(field in kwargs for field in required):
        return None  # Block incomplete events
    return kwargs
```
