"""VRPTW model solving with subtour elimination via cutting planes.

This module orchestrates the VRPTW solving process:

1. Loads (or generates) the bus stop points for each instance.
2. For each scenario (day x shift x municipality), builds and solves the
   CPLEX mixed-integer linear programming model.
3. Implements iterative subtour elimination:
   - Solves the model.
   - If the solution contains subtours, adds cuts and re-solves.
   - Repeats until a subtour-free solution is found or the time limit is reached.
4. Saves results to CSV and TXT files.

Usage example:
    >>> from vrptw.solver import solve_all_instances
    >>> solve_all_instances()
"""

import gc
import logging
import math
import time
from io import TextIOWrapper

import pandas as pd
from docplex.mp.model import Model

from .config import (
    DATA_PROCESSED_DIR,
    DATA_RAW_DIR,
    DEPOT_INDEX,
    DEPOT_LAT,
    DEPOT_LON,
    EARLIEST_DEPARTURE,
    INSTANCE_TYPES,
    LATEST_ARRIVAL,
    MIP_GAP,
    OUTPUT_CSV_DIR,
    OUTPUT_TEXT_DIR,
    PROCESS_MEMORY_LIMIT_MB,
    ROUTE_TYPES,
    SHIFTS,
    SOLVER_LOG_OUTPUT,
    SOLVER_MEMORY_EMPHASIS,
    SOLVER_NODE_FILE_STRATEGY,
    SOLVER_THREADS,
    SOLVER_TREE_MEM_LIMIT,
    SOLVER_WORK_MEM,
    TIME_LIMIT,
    TIME_SLOT_DURATION,
    VEHICLE_CAPACITY,
    WEEKDAYS,
)
from vrptw.memory import check_memory_budget, log_memory_usage
from vrptw.model_builder import (
    add_subtour_cuts,
    build_model,
    format_route_string,
    relax_model,
)
from vrptw.utils import build_routes, calculate_distances

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Scenario data preparation helpers
# ---------------------------------------------------------------------------

def _build_depot_row(day: str, iteration: int = 0) -> dict:
    """Create the depot (CEFET) record for DataFrame insertion.

    Args:
        day: Abbreviated weekday name.
        iteration: Current time iteration.

    Returns:
        Dictionary with the depot fields.
    """
    return {
        "lat": [DEPOT_LAT],
        "lon": [DEPOT_LON],
        "MORNING_DEMAND": [0],
        "AFTERNOON_DEMAND": [0],
        "NIGHT_DEMAND": [0],
        "LATE_DEMAND": [0],
        "earliest_departure": EARLIEST_DEPARTURE + TIME_SLOT_DURATION * iteration,
        "latest_arrival": LATEST_ARRIVAL,
        "MUNICIPALITY_ID": "CEFET",
        "DAYOFTHEWEEK": day,
        "centroid_id": 0,
        "iteration": iteration,
    }


def _prepare_iteration_data(
    day_data: pd.DataFrame,
    shift: str,
    day: str,
    municipality: str,
    iteration: int,
) -> pd.DataFrame | None:
    """Prepare the DataFrame for a specific solving iteration.

    Filters data by municipality and shift, adds the depot node and
    configures indices.

    Args:
        day_data: DataFrame with current day data.
        shift: Shift (``'MORNING'``, ``'AFTERNOON'``, ``'NIGHT'``, ``'LATE'``).
        day: Abbreviated weekday name.
        municipality: Municipality name.
        iteration: Time iteration.

    Returns:
        DataFrame indexed by ``centroid_id`` ready for the solver, or
        ``None`` if there is no demand.
    """
    demand_col = f"{shift}_DEMAND"
    demand_cols = ["MORNING_DEMAND", "AFTERNOON_DEMAND", "NIGHT_DEMAND", "LATE_DEMAND"]

    mun_data = day_data[day_data["MUNICIPALITY_ID"] == municipality].copy()
    mun_data = mun_data[mun_data[demand_col] > 0].reset_index(drop=True)

    if mun_data.empty:
        return None

    # Aggregate rows that share the same coordinates (sum demands)
    group_cols = ["lat", "lon", "MUNICIPALITY_ID", "DAYOFTHEWEEK",
                  "earliest_departure", "latest_arrival", "iteration"]
    existing_demand_cols = [c for c in demand_cols if c in mun_data.columns]
    agg_map = {c: "sum" for c in existing_demand_cols}
    mun_data = mun_data.groupby(
        [c for c in group_cols if c in mun_data.columns], as_index=False,
    ).agg(agg_map)

    # Assign centroid_id (offset by 1 to reserve 0 for the depot)
    mun_data = mun_data.reset_index(drop=True)
    mun_data["centroid_id"] = mun_data.index + 1

    # Insert depot as node 0
    depot_row = _build_depot_row(day, iteration)
    iter_data = pd.concat(
        [pd.DataFrame.from_dict(depot_row), mun_data], ignore_index=True,
    )
    iter_data = iter_data[iter_data["iteration"] == iteration]
    iter_data = iter_data.set_index("centroid_id").sort_index()

    if iter_data.empty:
        return None

    return iter_data


# ---------------------------------------------------------------------------
# Solving loop with subtour elimination
# ---------------------------------------------------------------------------

def _solve_with_subtour_elimination(
    model: Model,
    travels: dict,
    num_vehicles: int,
    time_limit: float,
) -> tuple[dict | None, float, bool]:
    """Execute the solving loop with iterative subtour elimination.

    Args:
        model: Built CPLEX model.
        travels: Travel variable dictionary.
        num_vehicles: Number of vehicles in the model.
        time_limit: Total time limit in seconds.

    Returns:
        Tuple ``(routes, elapsed_time, success)`` where ``routes`` contains
        the final routes (or ``None`` if time expired), ``elapsed_time`` is
        the total solving time, and ``success`` indicates whether a
        subtour-free solution was found.
    """
    start = time.time()
    warm_start = None

    while True:
        if warm_start is not None:
            model.add_mip_start(warm_start)

        solution_obj = model.solve(log_output=SOLVER_LOG_OUTPUT)
        if solution_obj is None:
            elapsed = time.time() - start
            logger.warning("Solver returned None after %.1fs", elapsed)
            return None, elapsed, False

        solution = solution_obj.as_dict()
        elapsed = time.time() - start

        routes = build_routes(solution, num_vehicles)
        model.time_limit = max(time_limit - elapsed, 1)

        # Build warm start and check for subtours
        warm_start = model.new_solution()
        subtour_found = False

        for k in range(num_vehicles):
            if not routes[k]:
                continue

            # Traverse route as linked list for warm start
            current = routes[k].pop(0)
            warm_start.add_var_value(travels[k, 0, current], 1)
            while current != 0:
                prev = current
                current = routes[k].pop(current)
                warm_start.add_var_value(travels[k, prev, current], 1)

            # Remaining nodes indicate subtours
            if routes[k]:
                subtour_found = True
                add_subtour_cuts(model, routes, travels, k)

        if not subtour_found:
            # Rebuild clean routes for output
            final_routes = build_routes(solution, num_vehicles)
            return final_routes, elapsed, True

        if elapsed > time_limit:
            logger.warning("Time limit reached (%.1fs)", elapsed)
            return None, elapsed, False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_mip_gap(model: Model) -> float | None:
    """Return the MIP relative gap from the last solve, or ``None`` if unavailable."""
    try:
        details = model.solve_details
        gap = details.mip_relative_gap
        if gap is not None and math.isfinite(gap):
            return gap
    except Exception:  # noqa: BLE001
        pass
    return None


# ---------------------------------------------------------------------------
# Scenario processing (municipality x iteration)
# ---------------------------------------------------------------------------

def _process_scenario(
    iter_data: pd.DataFrame,
    shift: str,
    municipality: str,
    iteration: int,
    output_file: TextIOWrapper,
    *,
    relax: bool = False,
) -> tuple[dict | None, list[dict]]:
    """Solve the VRPTW for a specific scenario and write results.

    Args:
        iter_data: DataFrame with iteration data (indexed by centroid_id).
        shift: Current shift.
        municipality: Municipality name.
        iteration: Time iteration.
        output_file: Text file for writing results.
        relax: If ``True``, solve the LP relaxation only and report the
            objective as a lower bound (no subtour elimination, no routes).

    Returns:
        Tuple ``(summary_dict, detail_list)`` with the summary and details
        of the solution, or ``(None, [])`` on failure.
    """
    num_spots = len(iter_data)
    demand_col = f"{shift}_DEMAND"
    num_vehicles = math.ceil(iter_data[demand_col].sum() / VEHICLE_CAPACITY)

    if num_spots == 0:
        logger.info("No demand in this iteration")
        output_file.write("No demand in this iteration\n\n")
        return None, []

    output_file.write(
        f"Available Vehicles {num_vehicles}, "
        f"Bus Stops with Demand {num_spots}\n\n"
    )

    # Calculate distance matrix
    distance_matrix, big_m = calculate_distances(
        iter_data, municipality, iteration, TIME_SLOT_DURATION,
    )

    # Build model
    model = Model("vrptw")
    model.time_limit = TIME_LIMIT
    model.parameters.mip.tolerances.mipgap = MIP_GAP
    model.parameters.threads = SOLVER_THREADS
    model.parameters.workmem = SOLVER_WORK_MEM
    model.parameters.mip.limits.treememory = SOLVER_TREE_MEM_LIMIT
    model.parameters.mip.strategy.file = SOLVER_NODE_FILE_STRATEGY
    model.parameters.emphasis.memory = int(SOLVER_MEMORY_EMPHASIS)

    model_data = {
        "data": iter_data,
        "num_spots": num_spots,
        "necessary_vehicles": num_vehicles,
        "capacity": VEHICLE_CAPACITY,
        "iteration": iteration,
        "time_slot": TIME_SLOT_DURATION,
        "SHIFT": shift,
        "distance": distance_matrix,
        "big_m": big_m,
        "depot": DEPOT_INDEX,
    }

    model, travels = build_model(model, model_data)

    if relax:
        return _solve_relaxed(model, num_spots, num_vehicles, output_file)

    return _solve_mip(
        model, travels, num_vehicles, num_spots,
        distance_matrix, iteration, output_file,
    )


def _solve_relaxed(
    model: Model,
    num_spots: int,
    num_vehicles: int,
    output_file: TextIOWrapper,
) -> tuple[dict | None, list[dict]]:
    """Solve the LP relaxation and return the lower bound."""
    relax_model(model)

    start = time.time()
    solution_obj = model.solve(log_output=SOLVER_LOG_OUTPUT)
    elapsed = time.time() - start

    lower_bound = model.objective_value if solution_obj else None

    output_file.write(f"LP Lower Bound: {lower_bound}\n")
    output_file.write(f"Execution Time: {elapsed:.2f}s\n\n\n")

    logger.info("LP Lower Bound: %s | Time: %.2fs", lower_bound, elapsed)

    summary = {
        "num_points": num_spots,
        "num_vehicles": num_vehicles,
        "exec_time": elapsed,
        "travel_time": lower_bound,
        "gap": None,
    }

    del model
    gc.collect()

    return summary, []


def _solve_mip(
    model: Model,
    travels: dict,
    num_vehicles: int,
    num_spots: int,
    distance_matrix: dict,
    iteration: int,
    output_file: TextIOWrapper,
) -> tuple[dict | None, list[dict]]:
    """Solve the MIP with subtour elimination and extract routes."""
    routes, elapsed, success = _solve_with_subtour_elimination(
        model, travels, num_vehicles, TIME_LIMIT,
    )

    detail_list: list[dict] = []

    if success and routes is not None:
        output_file.write("Solution:\n")

        for k in range(num_vehicles):
            num_points = len(routes.get(k, {}))
            route_str, travel_time = format_route_string(
                routes, travels, k,
                earliest_departure=EARLIEST_DEPARTURE,
                iteration=iteration,
                distance_matrix=distance_matrix,
            )
            if route_str:
                detail_list.append({
                    "vehicle_id": k,
                    "num_points": num_points,
                    "travel_time": travel_time,
                })
                output_file.write(route_str)
                logger.info(route_str.strip())
    else:
        output_file.write("No solution found within the defined time limit\n")

    gap = _get_mip_gap(model)
    objective = model.objective_value if success else None
    summary = {
        "num_points": num_spots,
        "num_vehicles": num_vehicles,
        "exec_time": elapsed,
        "travel_time": objective,
        "gap": gap if gap is not None else 0.0,
    }

    output_file.write(f"Objective Function Cost: {objective}\n")
    output_file.write(f"Total Execution Time: {elapsed:.2f}s\n\n\n")

    logger.info("Objective: %s | Time: %.2fs", objective, elapsed)

    del model
    gc.collect()

    return summary, detail_list


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def solve_all_instances(*, relax: bool = False) -> None:
    """Solve the VRPTW for all configured instances.

    Iterates over route types, instances, days, shifts, and municipalities
    as defined in ``config.py``. Results are saved to CSV files (summary
    and details) and TXT files (textual route log).

    Args:
        relax: If ``True``, solve the LP relaxation of every scenario
            instead of the full MIP.  Results are written with a
            ``relaxed_`` prefix so they never overwrite integer solutions.
    """
    file_prefix = "relaxed_" if relax else ""
    # Ensure output directories exist
    OUTPUT_CSV_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_TEXT_DIR.mkdir(parents=True, exist_ok=True)

    # Load instances to skip (already solved)
    skip_path = DATA_RAW_DIR / "skip_instances.csv"
    if skip_path.exists():
        skip_df = pd.read_csv(skip_path)
    else:
        skip_df = pd.DataFrame(columns=["route_type", "instance", "day", "shift", "municipality"])
    skip_set = set(skip_df.apply(lambda r: ",".join(r.astype(str)), axis=1))

    for route_type in ROUTE_TYPES:
        # Load bus stop points (generated by step 2)
        instances: dict[str, pd.DataFrame] = {}
        for instance_name in INSTANCE_TYPES:
            csv_path = DATA_PROCESSED_DIR / "bus_stops" / f"{instance_name}_{route_type}.csv"
            if not csv_path.exists():
                raise FileNotFoundError(
                    f"Bus stop file not found: {csv_path}. "
                    f"Run step 2 (point generation) before solving."
                )
            instances[instance_name] = pd.read_csv(csv_path)

        for instance_name, instance_data in instances.items():
            summaries: list[dict] = []
            details: list[dict] = []

            output_path = OUTPUT_TEXT_DIR / f"{file_prefix}solution_cvrptw_{instance_name}_{route_type}.txt"

            with open(output_path, "w", encoding="utf-8") as output_file:
                for day in WEEKDAYS:
                    day_data = instance_data[instance_data["DAYOFTHEWEEK"] == day].copy()
                    day_data = day_data.reset_index(drop=True)
                    day_data["earliest_departure"] = EARLIEST_DEPARTURE
                    day_data["latest_arrival"] = LATEST_ARRIVAL
                    day_data["iteration"] = 0

                    for shift in SHIFTS:
                        _write_shift_header(output_file, shift)

                        shift_data = day_data[
                            day_data[f"{shift}_DEMAND"] > 0
                        ].reset_index(drop=True)

                        if shift_data.empty:
                            continue

                        for municipality in shift_data["MUNICIPALITY_ID"].unique():
                            skip_key = f"{route_type},{instance_name},{day},{shift},{municipality}"
                            if not relax and skip_key in skip_set:
                                logger.info("Skipping instance: %s", skip_key)
                                continue

                            for iteration in shift_data["iteration"].unique():
                                _write_iteration_header(
                                    output_file, iteration, municipality,
                                )
                                logger.info(
                                    "Solving: %s | %s | %s | %s | iter=%d",
                                    day, shift, instance_name, municipality, iteration,
                                )

                                iter_data = _prepare_iteration_data(
                                    shift_data, shift, day, municipality, iteration,
                                )

                                if iter_data is None or iter_data.empty:
                                    output_file.write("No demand in this iteration\n\n")
                                    continue


                                if not check_memory_budget(PROCESS_MEMORY_LIMIT_MB):
                                    logger.warning(
                                        "Skipping scenario due to high memory: %s",
                                        skip_key,
                                    )
                                    output_file.write(
                                        "Skipped: process memory limit exceeded\n\n",
                                    )
                                    continue

                                try:
                                    summary, detail_items = _process_scenario(
                                        iter_data, shift, municipality, iteration,
                                        output_file, relax=relax,
                                    )
                                except Exception:
                                    logger.exception(
                                        "Scenario failed, continuing: %s", skip_key,
                                    )
                                    output_file.write(
                                        "Skipped: solver error (see logs)\n\n",
                                    )
                                    gc.collect()
                                    log_memory_usage("after failed scenario cleanup")
                                    continue

                                if summary is not None:
                                    base_info = {
                                        "INSTANCE": instance_name,
                                        "DAYOFTHEWEEK": day,
                                        "SHIFT": shift,
                                        "MUNICIPALITY_ID": municipality,
                                        "iteration": iteration,
                                    }
                                    summaries.append({**base_info, **summary})

                                    for detail in detail_items:
                                        details.append({**base_info, **detail})

                            if not relax:
                                # Register solved instance in skip DataFrame
                                # Only skip instances that were solved to optimality (gap == 0)
                                gap = summary.get('gap') or 0.0
                                if (skip_key not in skip_set) and summary['travel_time'] is not None and gap <= 0:
                                    skip_df = pd.concat([skip_df, pd.DataFrame([{
                                        "route_type": route_type,
                                        "instance": instance_name,
                                        "day": day,
                                        "shift": shift,
                                        "municipality": municipality,
                                    }])], ignore_index=True)
                                    skip_set.add(skip_key)
                                    skip_df.to_csv(skip_path, index=False)

                            # Save CSVs incrementally per municipality
                            _save_results(
                                summaries, details, instance_name, route_type,
                                prefix=file_prefix,
                            )

            logger.info(
                "Instance %s (%s) complete. Results at: %s",
                instance_name, route_type, output_path,
            )


# ---------------------------------------------------------------------------
# Writing and saving functions
# ---------------------------------------------------------------------------

def _write_shift_header(output_file: TextIOWrapper, shift: str) -> None:
    """Write the shift header to the output file."""
    horizon = LATEST_ARRIVAL - EARLIEST_DEPARTURE
    output_file.write(f"Time Horizon: {horizon} seconds\n\n")
    output_file.write("##############################\n")
    output_file.write(f"####  Current Shift: {shift}  ####\n")
    output_file.write("##############################\n\n")


def _write_iteration_header(
    output_file: TextIOWrapper, iteration: int, municipality: str,
) -> None:
    """Write the iteration header to the output file."""
    departure_time = EARLIEST_DEPARTURE + TIME_SLOT_DURATION * iteration
    header = f"|Iteration{iteration}, Departure Time: {departure_time}|"
    output_file.write("_" * len(header) + "\n")
    output_file.write(header + "\n")
    output_file.write("|" + "_" * (len(header) - 2) + "|\n\n")
    output_file.write(municipality + "\n")


def _save_results(
    summaries: list[dict],
    details: list[dict],
    instance_name: str,
    route_type: str,
    *,
    prefix: str = "",
) -> None:
    """Save partial results to CSV files."""
    if summaries:
        pd.DataFrame(summaries).to_csv(
            OUTPUT_CSV_DIR / f"{prefix}solution_cvrptw_{instance_name}_{route_type}.csv",
            index=False,
        )
    if details:
        pd.DataFrame(details).to_csv(
            OUTPUT_CSV_DIR / f"{prefix}detailed_solution_cvrptw_{instance_name}_{route_type}.csv",
            index=False,
        )
