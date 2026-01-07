"""
Exception handling utilities for the event broker.

Provides exception handler functions and type definitions for managing errors
that occur during subscriber callback execution. Includes built-in handlers for
common patterns: stopping on error with logging (stop_on_exception_handler),
silently continuing (silent_exception_handler), and collecting exceptions for
batch processing (collecting_exception_handler).
"""

import logging
import sys
from typing import Callable

from broker import subscriber


logger = logging.getLogger(__name__)


EXCEPTION_HANDLER = Callable[[subscriber.CALLBACK, str, Exception], bool]
"""
Signature for exception handlers.

Exception handlers receive the failing callback, namespace, and exception, then
return True to stop delivery or False to continue to remaining subscribers.
"""

STOP = True
CONTINUE = False


def get_callback_name(callback: subscriber.CALLBACK) -> str:
    """
    Returns the name of the callback, using class name for items with __self__,
    __name__ for anything with __name__, or str(callback) if neither are found.
    """
    if hasattr(callback, "__self__"):
        return f"{callback.__self__.__class__.__name__}.{callback.__name__}"
    elif hasattr(callback, "__name__"):
        return callback.__name__
    else:
        return str(callback)


def stop_and_log_exception_handler(
    callback: subscriber.CALLBACK, namespace: str, exception: Exception
) -> bool:
    """
    Handler that stops message delivery and logs the raised exception before
    reraising it.
    """
    logger.error(
        f"Exception in broker subscriber:\n"
        f"  Namespace: {namespace}\n"
        f"  Callback:  {get_callback_name(callback)}\n"
        f"  Exception: {exception.__class__.__name__}: {exception}",
        exc_info=True,
    )

    return STOP


def silent_exception_handler(_: subscriber.CALLBACK, __: str, ___: Exception) -> bool:
    """Silently ignore all exceptions."""
    return CONTINUE


exceptions_caught = []


def collecting_exception_handler(
    callback: subscriber.CALLBACK, namespace: str, exception: Exception
) -> bool:
    """
    Collect exceptions for batch processing.
    This appends exceptions caught to broker.exceptions.exceptions_caught which
    is a list.
    Either manage the list manually or use this function as an example to create
    a more robust exception collector.
    """
    exceptions_caught.append(
        {
            "callback": get_callback_name(callback),
            "namespace": namespace,
            "exception": f"{exception.__class__.__name__}: {exception}",
            "exc_info": sys.exc_info(),
        }
    )
    return CONTINUE
