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

Staging is unaffected by pause — `stage()` always queues events regardless
of pause state. Only dispatch is suppressed:
```python
with broker.paused():
    broker.stage('file.saved', filename='test.exr')  # staged, not suppressed

broker.emit_staged()  # delivered
```

### Staging Events

Events can be staged for deferred dispatch using `stage()`. Staged events are
held until explicitly dispatched, allowing you to batch emissions and control
exactly when they fire.
```python
broker.stage('file.saved', filename='render.exr', size=4096)
broker.stage('file.saved', filename='preview.jpg', size=512)
broker.stage('render.done', frame=42)

# Dispatch all staged events via emit() - sync subscribers only
broker.emit_staged()

# Or dispatch via emit_async() - both sync and async subscribers
await broker.emit_staged_async()
```

Staged events are flushed from the registry after dispatch by default. Pass
`flush=False` to retain them for repeated dispatch:
```python
broker.stage('session.heartbeat', status='ok')

broker.emit_staged(flush=False)  # dispatch but keep staged
broker.emit_staged(flush=False)  # dispatch again
broker.emit_staged()             # dispatch and flush
```

Events staged inside a subscriber callback during dispatch are not consumed
by the current `emit_staged` call — they survive to the next one:
```python
def handler(status: str) -> None:
    broker.stage('app.status', status='follow_up')

broker.register_subscriber('app.status', handler)
broker.stage('app.status', status='ready')

broker.emit_staged()  # dispatches 'ready', stages 'follow_up'
broker.emit_staged()  # dispatches 'follow_up'
```

To discard staged events without dispatching, use `clear_staged()`:
```python
broker.stage('file.saved', filename='temp.txt', size=0)
broker.clear_staged()  # discarded, nothing dispatched
```

### Pausing Emission

The broker can be paused using the `broker.paused()` context manager. While
paused, all calls to `emit()` and `emit_async()` are suppressed silently.
Emission resumes automatically when the context exits, even if an exception
is raised.
```python
with broker.paused():
    broker.emit('file.saved', filename='test.exr')  # suppressed
    await broker.emit_async('render.done', frame=42)  # suppressed

broker.emit('file.saved', filename='test.exr')  # delivered
```
