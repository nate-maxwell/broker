"""
Exception handling utilities for the event broker.

Provides exception handler functions for managing errors that occur during
subscriber callback execution.

Includes built-in handlers for common patterns:
stopping on error with logging (stop_and_log_[callback]_exceptions),
continuing on error with logging (log_and_continue_[callback]_exception)
silently continuing (silent_[callback]_exception),
and collecting exceptions for batch processing (collect_[callback]_exception).
"""

import logging
import sys
from typing import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from broker.subscriber import SUBSCRIBER_SIG
    from broker.transformer import TRANSFORMER_SIG

logger = logging.getLogger(__name__)


STOP = True
CONTINUE = False


def get_callable_name(callable_: Callable[..., object]) -> str:
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
    callback: "SUBSCRIBER_SIG", namespace: str, exception: Exception
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
    callback: "SUBSCRIBER_SIG", namespace: str, exception: Exception
) -> bool:
    """Log subscriber errors but continue processing."""
    logger.warning(
        f"Subscriber error (continuing): "
        f"{get_callable_name(callback)} in {namespace}: {exception}"
    )
    return CONTINUE


def silent_subscriber_exception(_: "SUBSCRIBER_SIG", __: str, ___: Exception) -> bool:
    """Silently ignore all exceptions."""
    return CONTINUE


exceptions_caught: list[dict[str, object]] = []


def collect_subscriber_exception(
    callback: "SUBSCRIBER_SIG", namespace: str, exception: Exception
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
    transformer: "TRANSFORMER_SIG", namespace: str, exception: Exception
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
    transformer: "TRANSFORMER_SIG", namespace: str, exception: Exception
) -> bool:
    """Log transformer errors but continue processing."""
    logger.warning(
        f"Transformer error (continuing): "
        f"{get_callable_name(transformer)} in {namespace}: {exception}"
    )
    return CONTINUE


def silent_transformer_exception(_: "TRANSFORMER_SIG", __: str, ___: Exception) -> bool:
    """Silently ignore transformer exceptions and continue."""
    return CONTINUE


transformer_exceptions_caught: list[dict[str, object]] = []


def collecting_transformer_exception(
    transformer: "TRANSFORMER_SIG", namespace: str, exception: Exception
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
