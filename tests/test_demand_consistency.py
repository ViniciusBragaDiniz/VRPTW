"""Tests for demand consistency on real project data.

Runs the checks from against the actual bus-stops and student files. 
Every test is read-only — nothing is written to disk.  
Tests are skipped when data files are absent.
"""

import pytest

from exploration.check_demand_consistency import (
    BUS_STOPS_DIR,
    DEMAND_COLS,
    GROUP_KEYS,
    STUDENTS_PATH,
    _build_student_counts,
    _load_aggregated,
    _threshold_report,
    check_consistency,
)
from src.globals.config import MIN_STUDENTS_PER_MUNICIPALITY, ROUTE_TYPES

_bus_stops_available = all(
    (BUS_STOPS_DIR / f"{inst}_{rt}.csv").exists()
    for inst in ("full", "tec", "grad")
    for rt in ROUTE_TYPES
)

skip_no_bus_stops = pytest.mark.skipif(
    not _bus_stops_available,
    reason="Bus-stops CSV files not found — skipping data consistency tests",
)
skip_no_students = pytest.mark.skipif(
    not STUDENTS_PATH.exists(),
    reason="Student info file not found — skipping threshold tests",
)


# ── _load_aggregated ─────────────────────────────────────────────────────


@skip_no_bus_stops
class TestLoadAggregated:
    @pytest.mark.parametrize("instance", ["full", "tec", "grad"])
    @pytest.mark.parametrize("route_type", ROUTE_TYPES)
    def test_returns_non_empty_dataframe(self, instance, route_type):
        df = _load_aggregated(instance, route_type)
        assert len(df) > 0

    @pytest.mark.parametrize("instance", ["full", "tec", "grad"])
    @pytest.mark.parametrize("route_type", ROUTE_TYPES)
    def test_has_expected_columns(self, instance, route_type):
        df = _load_aggregated(instance, route_type)
        for col in GROUP_KEYS + DEMAND_COLS:
            assert col in df.columns

    @pytest.mark.parametrize("instance", ["full", "tec", "grad"])
    @pytest.mark.parametrize("route_type", ROUTE_TYPES)
    def test_demand_values_are_non_negative(self, instance, route_type):
        df = _load_aggregated(instance, route_type)
        for col in DEMAND_COLS:
            assert (df[col] >= 0).all(), (
                f"Negative demand in {instance}_{route_type} column {col}"
            )


# ── check_consistency ─────────────────────────────────────────────────────


@skip_no_bus_stops
class TestCheckConsistency:
    def test_tec_plus_grad_equals_full_or_explained_by_threshold(self):
        """Core assertion: every mismatch must be explainable by the
        MIN_STUDENTS_PER_MUNICIPALITY threshold.  Unexplained mismatches
        are a data-integrity failure."""
        result = check_consistency()

        if result.empty:
            return

        student_counts = _build_student_counts()
        if student_counts is not None:
            threshold_df = _threshold_report(student_counts)
            if not threshold_df.empty:
                threshold_cities = set(threshold_df["CITY"])
                unexplained = result[
                    ~result["MUNICIPALITY_ID"].isin(threshold_cities)
                ]
            else:
                unexplained = result
        else:
            unexplained = result

        assert unexplained.empty, (
            f"{len(unexplained)} unexplained demand mismatches found "
            f"(tec + grad != full):\n{unexplained.to_string()}"
        )

    @pytest.mark.parametrize("route_type", ROUTE_TYPES)
    def test_no_missing_municipalities_in_combined(self, route_type):
        """Every municipality in the full file should appear in tec+grad
        (or be explained by the threshold)."""
        full = _load_aggregated("full", route_type)
        tec = _load_aggregated("tec", route_type)
        grad = _load_aggregated("grad", route_type)

        combined_keys = set(
            zip(tec["MUNICIPALITY_ID"], tec["DAYOFTHEWEEK"])
        ) | set(
            zip(grad["MUNICIPALITY_ID"], grad["DAYOFTHEWEEK"])
        )
        full_keys = set(
            zip(full["MUNICIPALITY_ID"], full["DAYOFTHEWEEK"])
        )

        missing = full_keys - combined_keys
        if not missing:
            return

        student_counts = _build_student_counts()
        if student_counts is not None:
            threshold_df = _threshold_report(student_counts)
            threshold_cities = set(threshold_df["CITY"]) if not threshold_df.empty else set()
            unexplained = {(m, d) for m, d in missing if m not in threshold_cities}
        else:
            unexplained = missing

        assert not unexplained, (
            f"{route_type}: {len(unexplained)} municipality/day pairs present "
            f"in full but missing in tec+grad (not explained by threshold): "
            f"{unexplained}"
        )


# ── _build_student_counts ────────────────────────────────────────────────


@skip_no_students
class TestBuildStudentCounts:
    def test_returns_dataframe(self):
        result = _build_student_counts()
        assert result is not None
        assert len(result) > 0

    def test_contains_all_filter_labels(self):
        result = _build_student_counts()
        labels = set(result["filter"])
        assert {"full", "tec", "grad"} <= labels

    def test_full_count_gte_subset_counts(self):
        """For every city, the full count should be >= max(tec, grad)."""
        result = _build_student_counts()
        pivot = result.pivot_table(
            index="CITY", columns="filter", values="n_students", fill_value=0,
        )
        for col in ("tec", "grad"):
            if col in pivot.columns:
                violations = pivot[pivot["full"] < pivot[col]]
                assert violations.empty, (
                    f"Cities where {col} count exceeds full:\n{violations}"
                )


# ── _threshold_report ────────────────────────────────────────────────────


@skip_no_students
class TestThresholdReport:
    def test_threshold_report_structure(self):
        counts = _build_student_counts()
        report = _threshold_report(counts)
        if report.empty:
            pytest.skip("No municipalities hit the threshold edge case")
        for col in ("CITY", "tec_skipped", "grad_skipped"):
            assert col in report.columns

    def test_skipped_municipalities_below_threshold(self):
        """Every municipality flagged as tec_skipped must have fewer than
        MIN_STUDENTS_PER_MUNICIPALITY tec students."""
        counts = _build_student_counts()
        report = _threshold_report(counts)
        if report.empty:
            pytest.skip("No municipalities hit the threshold edge case")

        for _, row in report.iterrows():
            if row["tec_skipped"]:
                assert row["tec"] < MIN_STUDENTS_PER_MUNICIPALITY
            if row["grad_skipped"]:
                assert row["grad"] < MIN_STUDENTS_PER_MUNICIPALITY
