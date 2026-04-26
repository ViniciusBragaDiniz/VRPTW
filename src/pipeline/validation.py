"""Input data validation and solution feasibility checking.

Provides pre-solve data validation (ensuring ``model_data`` is well-formed)
and post-solve solution validation (checking that routes respect all
constraints using the original data, independent of the solver).

Usage example:
    >>> from src.pipeline.validation import validate_input_data, validate_solution
    >>> errors = validate_input_data(model_data)
    >>> if errors:
    ...     raise ValueError(errors)
    >>> violations = validate_solution(routes, model_data)
"""

import logging
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)

_REQUIRED_MODEL_DATA_KEYS = frozenset({
    "data", "num_spots", "necessary_vehicles", "capacity",
    "iteration", "time_slot", "SHIFT", "distance", "big_m", "depot",
})


# ---------------------------------------------------------------------------
# Input data validation
# ---------------------------------------------------------------------------

def validate_input_data(model_data: dict[str, Any]) -> list[str]:
    """Validate consistency of input data before model construction.

    Checks structural requirements (required keys, column existence)
    and semantic constraints (non-negative demands, valid time windows,
    positive capacity, well-formed distance matrix).

    Args:
        model_data: Dictionary with all instance data, as constructed
            by the solver before calling ``build_model``.

    Returns:
        List of error messages. An empty list indicates valid data.
    """
    errors: list[str] = []

    missing = _REQUIRED_MODEL_DATA_KEYS - set(model_data.keys())
    if missing:
        errors.append(f"Missing required keys: {sorted(missing)}")
        return errors

    if model_data["capacity"] <= 0:
        errors.append(f"Capacity must be positive, got {model_data['capacity']}")

    if model_data["necessary_vehicles"] < 1:
        errors.append(
            f"At least 1 vehicle required, got {model_data['necessary_vehicles']}"
        )

    city_data = model_data["data"]
    if not isinstance(city_data, pd.DataFrame):
        errors.append("'data' must be a pandas DataFrame")
        return errors

    shift = model_data["SHIFT"]
    demand_col = f"{shift}_DEMAND"
    required_cols = {"lat", "lon", "earliest_departure", "latest_arrival", demand_col}
    missing_cols = required_cols - set(city_data.columns)
    if missing_cols:
        errors.append(f"DataFrame missing columns: {sorted(missing_cols)}")
        return errors

    for i in city_data.index[1:]:
        demand = city_data.loc[i, demand_col]
        if demand < 0:
            errors.append(f"Negative demand at node {i}: {demand}")

    for i in city_data.index:
        earliest = city_data.loc[i, "earliest_departure"]
        latest = city_data.loc[i, "latest_arrival"]
        if earliest > latest:
            errors.append(
                f"Invalid time window at node {i}: "
                f"earliest ({earliest}) > latest ({latest})"
            )

    distances = model_data["distance"]
    if not isinstance(distances, dict):
        errors.append("'distance' must be a dict-of-dicts")
    else:
        for i, row in distances.items():
            for j, val in row.items():
                if i != j and val < 0:
                    errors.append(f"Negative distance from {i} to {j}: {val}")

    if model_data["big_m"] <= 0:
        errors.append(f"big_m must be positive, got {model_data['big_m']}")

    return errors


# ---------------------------------------------------------------------------
# Solution validation helpers
# ---------------------------------------------------------------------------

def _extract_path(route_map: dict[int, int], depot: int) -> list[int]:
    """Extract the ordered node path from a linked-list route map.

    Args:
        route_map: Dictionary ``{origin: destination}`` representing
            a vehicle's route as a linked list.
        depot: Depot node index.

    Returns:
        Ordered list of nodes starting and ending at the depot.
        Empty list if the depot is absent from the route.
    """
    if depot not in route_map:
        return []

    path = [depot]
    current = route_map[depot]
    visited = {depot}

    while current != depot:
        if current in visited:
            path.append(current)
            break
        visited.add(current)
        path.append(current)
        if current not in route_map:
            break
        current = route_map[current]

    path.append(depot)
    return path


# ---------------------------------------------------------------------------
# Solution validation
# ---------------------------------------------------------------------------

def validate_solution(
    routes: dict[int, dict[int, int]],
    model_data: dict[str, Any],
    tolerance: float = 1e-6,
) -> list[dict[str, Any]]:
    """Validate that a solution satisfies constraints using the original data.

    Performs an independent feasibility check on the routes produced by the
    solver.  The checks assume the common case where each client is served
    by exactly one vehicle (no demand splitting).

    Checks performed:
        1. **Capacity** – total demand served by a vehicle ≤ capacity.
        2. **Demand** – every client with positive demand is visited.
        3. **Time windows** – a feasible schedule exists for each route.
        4. **Flow** – each client appears in at most one vehicle's route.

    Args:
        routes: Vehicle routes as returned by ``build_routes``:
            ``{k: {i: j, ...}}`` linked-list per vehicle.
        model_data: Dictionary with instance data.
        tolerance: Numerical tolerance for constraint checks.

    Returns:
        List of violation dicts with keys ``type``, ``message``, and
        optionally ``vehicle`` / ``node``.  Empty list ⇒ feasible.
    """
    violations: list[dict[str, Any]] = []
    city_data = model_data["data"]
    capacity = model_data["capacity"]
    depot = model_data["depot"]
    distances = model_data["distance"]
    shift = model_data["SHIFT"]
    demand_col = f"{shift}_DEMAND"

    client_visits: dict[int, list[int]] = {}

    for k, route_map in routes.items():
        if not route_map:
            continue

        path = _extract_path(route_map, depot)
        if len(path) < 2:
            continue

        # -- Capacity --
        vehicle_load = sum(
            city_data.loc[node, demand_col]
            for node in path
            if node != depot and node in city_data.index
        )
        if vehicle_load > capacity + tolerance:
            violations.append({
                "type": "capacity",
                "vehicle": k,
                "message": (
                    f"Vehicle {k} load ({vehicle_load}) "
                    f"exceeds capacity ({capacity})"
                ),
            })

        # -- Time-window feasibility --
        time = float(city_data.loc[depot, "earliest_departure"])
        for idx in range(len(path) - 1):
            i, j = path[idx], path[idx + 1]
            travel = distances.get(i, {}).get(j)
            if travel is None or travel == float("inf"):
                continue
            arrival = time + travel
            earliest = float(city_data.loc[j, "earliest_departure"])
            latest = float(city_data.loc[j, "latest_arrival"])
            service_start = max(arrival, earliest)
            if service_start > latest + tolerance:
                violations.append({
                    "type": "time_window",
                    "vehicle": k,
                    "node": j,
                    "message": (
                        f"Vehicle {k} arrives at node {j} at "
                        f"{service_start:.1f}, latest_arrival is {latest}"
                    ),
                })
            time = service_start

        # -- Track visits for flow / demand checks --
        for node in path:
            if node == depot:
                continue
            client_visits.setdefault(node, []).append(k)

    # -- Demand satisfaction --
    for i in city_data.index:
        if i == depot:
            continue
        expected = city_data.loc[i, demand_col]
        if expected <= 0:
            continue
        if i not in client_visits:
            violations.append({
                "type": "demand",
                "node": i,
                "message": (
                    f"Node {i} has demand {expected} but was not visited"
                ),
            })

    # -- Flow: each client visited at most once --
    for node, vehicles in client_visits.items():
        if len(vehicles) > 1:
            violations.append({
                "type": "flow",
                "node": node,
                "message": (
                    f"Node {node} visited by {len(vehicles)} vehicles "
                    f"({vehicles}), expected at most 1"
                ),
            })

    return violations
