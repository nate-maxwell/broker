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
from typing import Any
from typing import Callable
from typing import Optional

from broker import subscriber


logger = logging.getLogger(__name__)


SUBSCRIPTION_EXCEPTION_HANDLER = Callable[[subscriber.SUBSCRIBER, str, Exception], bool]
"""
Signature for exception handlers.

Exception handlers receive the failing callback, namespace, and exception, then
return True to stop delivery or False to continue to remaining subscribers.
"""

TRANSFORMER = Callable[[str, dict[str, Any]], Optional[dict[str, Any]]]
"""Transformer function type."""

TRANSFORMER_EXCEPTION_HANDLER = Callable[[TRANSFORMER, str, Exception], bool]
"""Signature for transformer exception handlers."""

STOP = True
CONTINUE = False


def get_callable_name(callable_: Callable) -> str:
    """
    Returns the name of the callable, using class name for items with __self__,
    __name__ for anything with __name__, or str(callback) if neither are found.
    """
    if hasattr(callable_, "__self__"):
        return f"{callable_.__self__.__class__.__name__}.{callable_.__name__}"
    elif hasattr(callable_, "__name__"):
        return callable_.__name__
    else:
        return str(callable_)


# -----Subscriber Exception Handlers-------------------------------------------


def stop_and_log_subscriber_exception(
    callback: subscriber.SUBSCRIBER, namespace: str, exception: Exception
) -> bool:
    """
    Handler that stops message delivery and logs the raised exception before
    reraising it.
    """
    logger.error(
        f"Exception in broker subscriber:\n"
        f"  Namespace: {namespace}\n"
        f"  Callback:  {get_callable_name(callback)}\n"
        f"  Exception: {exception.__class__.__name__}: {exception}",
        exc_info=True,
    )

    return STOP


def log_and_continue_subscriber_exception(
    callback: subscriber.SUBSCRIBER, namespace: str, exception: Exception
) -> bool:
    """Log subscriber errors but continue processing."""
    logger.warning(
        f"Subscriber error (continuing): "
        f"{get_callable_name(callback)} in {namespace}: {exception}"
    )
    return CONTINUE


def silent_subscriber_exception(
    _: subscriber.SUBSCRIBER, __: str, ___: Exception
) -> bool:
    """Silently ignore all exceptions."""
    return CONTINUE


exceptions_caught = []


def collect_subscriber_exception(
    callback: subscriber.SUBSCRIBER, namespace: str, exception: Exception
) -> bool:
    """
    Collect exceptions for batch processing.
    This appends exceptions caught to broker.handlers.exceptions_caught which
    is a list.
    Either manage the list manually or use this function as an example to create
    a more robust exception collector.
    """
    exceptions_caught.append(
        {
            "callback": get_callable_name(callback),
            "namespace": namespace,
            "exception": f"{exception.__class__.__name__}: {exception}",
            "exc_info": sys.exc_info(),
        }
    )
    return CONTINUE


# -----Transformer Exception Handlers------------------------------------------


def stop_and_log_transformer_exception(
    transformer: TRANSFORMER, namespace: str, exception: Exception
) -> bool:
    """Handler that stops transformer chain and logs the error."""
    logger.error(
        f"Exception in transformer:\n"
        f"  Namespace: {namespace}\n"
        f"  Transformer: {get_callable_name(transformer)}\n"
        f"  Exception: {exception.__class__.__name__}: {exception}",
        exc_info=True,
    )
    return STOP


def log_and_continue_transformer_exception(
    transformer: TRANSFORMER, namespace: str, exception: Exception
) -> bool:
    """Log transformer errors but continue processing."""
    logger.warning(
        f"Transformer error (continuing): "
        f"{get_callable_name(transformer)} in {namespace}: {exception}"
    )
    return CONTINUE


def silent_transformer_exception(_: TRANSFORMER, __: str, ___: Exception) -> bool:
    """Silently ignore transformer exceptions and continue."""
    return CONTINUE


transformer_exceptions_caught = []


def collecting_transformer_exception(
    transformer: TRANSFORMER, namespace: str, exception: Exception
) -> bool:
    """Collect transformer exceptions for batch processing."""
    transformer_exceptions_caught.append(
        {
            "transformer": get_callable_name(transformer),
            "namespace": namespace,
            "exception": f"{exception.__class__.__name__}: {exception}",
            "exc_info": sys.exc_info(),
        }
    )
    return CONTINUE
