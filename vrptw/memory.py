"""Process-level memory monitoring utilities.

Provides helpers to query the current resident set size (RSS) and enforce
a configurable memory budget so that the solver loop can skip scenarios
before they trigger an OS-level out-of-memory kill.

Usage example:
    >>> from vrptw.memory import check_memory_budget, log_memory_usage
    >>> if not check_memory_budget(8192):
    ...     print("Memory budget exceeded — skipping scenario")
    >>> log_memory_usage("after solve")
"""

import logging

import psutil

logger = logging.getLogger(__name__)


def get_process_memory_mb() -> float:
    """Return the current process RSS in megabytes."""
    return psutil.Process().memory_info().rss / (1024 * 1024)


def check_memory_budget(limit_mb: float) -> bool:
    """Return ``True`` if process RSS is below *limit_mb*, ``False`` otherwise.

    When the budget is exceeded a warning is logged with the current and
    allowed values.
    """
    current = get_process_memory_mb()
    if current > limit_mb:
        logger.warning(
            "Memory usage %.0f MB exceeds limit %.0f MB", current, limit_mb,
        )
        return False
    return True


def log_memory_usage(label: str) -> None:
    """Log the current process RSS at INFO level, tagged with *label*."""
    logger.info("[Memory] %s: %.0f MB RSS", label, get_process_memory_mb())
