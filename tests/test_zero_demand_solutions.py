"""Tests for zero-demand solution detection on real project data.

Runs the checks from against the actual bus-stops and solution CSV files.
Every test is read-only — nothing iswritten to disk.
Tests are skipped when data files are absent.
"""

import pandas as pd
import pytest

from exploration.check_zero_demand_solutions import (
    BUS_STOPS_DIR,
    SCENARIO_KEY,
    SHIFT_TO_DEMAND_COL,
    SOLUTION_PREFIXES,
    _load_zero_demand_scenarios,
    check_solutions,
)
from src.globals.config import INSTANCE_TYPES, OUTPUT_CSV_DIR, ROUTE_TYPES

_bus_stops_available = all(
    (BUS_STOPS_DIR / f"{inst}_{rt}.csv").exists()
    for inst in INSTANCE_TYPES
    for rt in ROUTE_TYPES
)
_solutions_available = any(
    (OUTPUT_CSV_DIR / f"{prefix}_{inst}_{rt}.csv").exists()
    for prefix in SOLUTION_PREFIXES
    for inst in INSTANCE_TYPES
    for rt in ROUTE_TYPES
)

skip_no_bus_stops = pytest.mark.skipif(
    not _bus_stops_available,
    reason="Bus-stops CSV files not found — skipping zero-demand tests",
)
skip_no_solutions = pytest.mark.skipif(
    not _solutions_available,
    reason="Solution CSV files not found — skipping zero-demand tests",
)


# ── _load_zero_demand_scenarios ───────────────────────────────────────────


@skip_no_bus_stops
class TestLoadZeroDemandScenarios:
    @pytest.mark.parametrize("instance", INSTANCE_TYPES)
    @pytest.mark.parametrize("route_type", ROUTE_TYPES)
    def test_returns_set(self, instance, route_type):
        result = _load_zero_demand_scenarios(instance, route_type)
        assert isinstance(result, set)

    @pytest.mark.parametrize("instance", INSTANCE_TYPES)
    @pytest.mark.parametrize("route_type", ROUTE_TYPES)
    def test_tuples_have_three_elements(self, instance, route_type):
        result = _load_zero_demand_scenarios(instance, route_type)
        for item in result:
            assert len(item) == 3, f"Expected 3-tuple, got {item}"

    @pytest.mark.parametrize("instance", INSTANCE_TYPES)
    @pytest.mark.parametrize("route_type", ROUTE_TYPES)
    def test_zero_scenarios_match_raw_data(self, instance, route_type):
        """Cross-check: independently verify each flagged scenario truly has
        zero demand in the source CSV."""
        zero = _load_zero_demand_scenarios(instance, route_type)
        if not zero:
            pytest.skip("No zero-demand scenarios for this combo")

        path = BUS_STOPS_DIR / f"{instance}_{route_type}.csv"
        bs = pd.read_csv(path)

        for day, shift, mun in zero:
            demand_col = SHIFT_TO_DEMAND_COL[shift]
            subset = bs[
                (bs["MUNICIPALITY_ID"] == mun) & (bs["DAYOFTHEWEEK"] == day)
            ]
            total = subset[demand_col].sum()
            assert total == 0, (
                f"{instance}_{route_type}: ({mun}, {day}, {shift}) flagged as "
                f"zero-demand but actual total is {total}"
            )


# ── check_solutions ───────────────────────────────────────────────────────


@skip_no_bus_stops
@skip_no_solutions
class TestCheckSolutions:
    def test_no_solutions_with_zero_demand(self):
        """Core assertion: no solution row should exist for a scenario whose
        bus-stop demand is zero."""
        bad = check_solutions()

        assert bad.empty, (
            f"{len(bad)} solution rows reference zero-demand scenarios:\n"
            f"{bad.to_string()}"
        )

    def test_all_solution_files_have_required_columns(self):
        """Every solution CSV that exists must contain the scenario key
        columns needed for the zero-demand check."""
        for prefix in SOLUTION_PREFIXES:
            for inst in INSTANCE_TYPES:
                for rt in ROUTE_TYPES:
                    path = OUTPUT_CSV_DIR / f"{prefix}_{inst}_{rt}.csv"
                    if not path.exists():
                        continue
                    df = pd.read_csv(path)
                    for col in SCENARIO_KEY:
                        assert col in df.columns, (
                            f"{path.name} is missing required column '{col}'"
                        )

    def test_solution_shifts_are_valid(self):
        """Every SHIFT value in solution files should map to a known demand
        column."""
        valid_shifts = set(SHIFT_TO_DEMAND_COL.keys())
        for prefix in SOLUTION_PREFIXES:
            for inst in INSTANCE_TYPES:
                for rt in ROUTE_TYPES:
                    path = OUTPUT_CSV_DIR / f"{prefix}_{inst}_{rt}.csv"
                    if not path.exists():
                        continue
                    df = pd.read_csv(path)
                    shifts_in_file = set(df["SHIFT"].unique())
                    invalid = shifts_in_file - valid_shifts
                    assert not invalid, (
                        f"{path.name} contains unknown shifts: {invalid}"
                    )

    def test_solution_municipalities_exist_in_bus_stops(self):
        """Every MUNICIPALITY_ID referenced in a solution file should appear
        in the corresponding bus-stops file."""
        for inst in INSTANCE_TYPES:
            for rt in ROUTE_TYPES:
                bs_path = BUS_STOPS_DIR / f"{inst}_{rt}.csv"
                if not bs_path.exists():
                    continue
                bs_muns = set(pd.read_csv(bs_path)["MUNICIPALITY_ID"].unique())

                for prefix in SOLUTION_PREFIXES:
                    sol_path = OUTPUT_CSV_DIR / f"{prefix}_{inst}_{rt}.csv"
                    if not sol_path.exists():
                        continue
                    sol_muns = set(pd.read_csv(sol_path)["MUNICIPALITY_ID"].unique())
                    unknown = sol_muns - bs_muns
                    assert not unknown, (
                        f"{sol_path.name} references municipalities not in "
                        f"{bs_path.name}: {unknown}"
                    )
