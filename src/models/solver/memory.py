"""Process-level memory monitoring utilities.

Provides helpers to query the current resident set size (RSS) and enforce
a configurable memory budget so that the solver loop can skip scenarios
before they trigger an OS-level out-of-memory kill.

Also provides :class:`MemoryAbortListener`, a DOcplex progress listener
that aborts the CPLEX solve **mid-flight** when RSS exceeds a threshold,
preventing the OS OOM killer from terminating the process.

Usage example:
    >>> from src.models.solver.memory import check_memory_budget, log_memory_usage
    >>> if not check_memory_budget(8192):
    ...     print("Memory budget exceeded — skipping scenario")
    >>> log_memory_usage("after solve")
"""

import logging

import psutil
from docplex.mp.progress import ProgressListener

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


class MemoryAbortListener(ProgressListener):
    """DOcplex progress listener that aborts the solve when RSS is too high.

    Registered on a :class:`docplex.mp.model.Model` via
    ``model.add_progress_listener(listener)``, this callback is invoked by
    CPLEX at every incumbent or progress event during branch-and-bound.
    If the process RSS exceeds *limit_mb* it calls :meth:`abort`, which
    asks CPLEX to stop and return the best solution found so far.

    Args:
        limit_mb: Maximum allowed process RSS in megabytes.
    """

    def __init__(self, limit_mb: float) -> None:
        super().__init__()
        self._limit_mb = limit_mb
        self.aborted = False

    def notify_progress(self, progress_data) -> None:  # noqa: ANN001
        current = get_process_memory_mb()
        if current > self._limit_mb:
            logger.warning(
                "MemoryAbortListener: RSS %.0f MB exceeds limit %.0f MB — aborting solve",
                current,
                self._limit_mb,
            )
            self.aborted = True
            self.abort()
