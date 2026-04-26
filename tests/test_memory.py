"""Tests for the vrptw.memory module and solver memory safeguards."""

from unittest.mock import patch

from src.models.solver.memory import check_memory_budget, get_process_memory_mb, log_memory_usage


# ---------------------------------------------------------------------------
# get_process_memory_mb
# ---------------------------------------------------------------------------

class TestGetProcessMemoryMb:
    def test_returns_positive_float(self):
        result = get_process_memory_mb()
        assert isinstance(result, float)
        assert result > 0

    def test_result_is_in_reasonable_range(self):
        mb = get_process_memory_mb()
        assert 1 < mb < 100_000


# ---------------------------------------------------------------------------
# check_memory_budget
# ---------------------------------------------------------------------------

class TestCheckMemoryBudget:
    def test_returns_true_when_under_budget(self):
        assert check_memory_budget(999_999) is True

    def test_returns_false_when_over_budget(self):
        assert check_memory_budget(0.001) is False

    def test_logs_warning_when_over_budget(self, caplog):
        with caplog.at_level("WARNING", logger="src.models.solver.memory"):
            check_memory_budget(0.001)
        assert "exceeds limit" in caplog.text

    def test_no_warning_when_under_budget(self, caplog):
        with caplog.at_level("WARNING", logger="src.models.solver.memory"):
            check_memory_budget(999_999)
        assert "exceeds limit" not in caplog.text


# ---------------------------------------------------------------------------
# log_memory_usage
# ---------------------------------------------------------------------------

class TestLogMemoryUsage:
    def test_logs_label_and_rss(self, caplog):
        with caplog.at_level("INFO", logger="src.models.solver.memory"):
            log_memory_usage("test-label")
        assert "test-label" in caplog.text
        assert "MB RSS" in caplog.text


# ---------------------------------------------------------------------------
# Config defaults sanity
# ---------------------------------------------------------------------------

class TestConfigDefaults:
    def test_memory_config_values_are_positive(self):
        from src.globals.config import (
            PROCESS_MEMORY_LIMIT_MB,
            SOLVER_TREE_MEM_LIMIT,
            SOLVER_WORK_MEM,
        )

        assert SOLVER_WORK_MEM > 0
        assert SOLVER_TREE_MEM_LIMIT > 0
        assert PROCESS_MEMORY_LIMIT_MB > 0

    def test_node_file_strategy_is_valid(self):
        from src.globals.config import SOLVER_NODE_FILE_STRATEGY

        assert SOLVER_NODE_FILE_STRATEGY in {0, 1, 2, 3}
