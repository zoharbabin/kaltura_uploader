# kaltura_uploader/decorators.py

import time
import logging
from functools import wraps
from typing import Callable, Tuple, TypeVar

T = TypeVar("T", bound=Callable[..., any])

def retry(
    exceptions: Tuple[Exception, ...],
    max_attempts: int = 5,
    initial_delay: float = 1.0,
    backoff_factor: float = 2.0
) -> Callable[[T], T]:
    """
    Decorator to retry a function call with exponential backoff.

    :param exceptions: Tuple of exception types to catch and retry.
    :param max_attempts: Maximum number of attempts before giving up.
    :param initial_delay: Initial sleep time in seconds for the first retry.
    :param backoff_factor: Multiplier for each subsequent delay.
    """
    def decorator(func: T) -> T:
        @wraps(func)
        def wrapper(*args, **kwargs):
            delay = initial_delay
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    if attempt == max_attempts:
                        logging.error(
                            f"Attempt {attempt}/{max_attempts} failed with error: {e}. No more retries."
                        )
                        raise
                    logging.warning(
                        f"Attempt {attempt}/{max_attempts} failed with error: {e}. "
                        f"Retrying in {delay:.1f}s..."
                    )
                    time.sleep(delay)
                    delay *= backoff_factor
        return wrapper  # type: ignore
    return decorator
