"""Utility functions for the VRPTW model.

Contains general-purpose functions shared across the package modules:
geodesic distance calculation (Haversine), travel time matrix construction,
route extraction from the CPLEX solution, and data preparation for temporal
demand partitioning.

Usage example:
    >>> from vrptw.utils import haversine
    >>> dist = haversine(-22.70, -43.46, -22.90, -43.20)
    >>> print(f"Distance: {dist:.0f} m")
"""

import logging
import math
from typing import Any

import pandas as pd

from .config import MUNICIPALITY_SPEED_KMH, DEFAULT_SPEED_KMH

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Geodesic distance calculation
# ---------------------------------------------------------------------------

def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the distance between two points on Earth's surface (Haversine).

    Args:
        lat1: Latitude of point 1 (decimal degrees).
        lon1: Longitude of point 1 (decimal degrees).
        lat2: Latitude of point 2 (decimal degrees).
        lon2: Longitude of point 2 (decimal degrees).

    Returns:
        Distance between the two points in meters.
    """
    EARTH_RADIUS_M = 6_371_000

    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return EARTH_RADIUS_M * c


# ---------------------------------------------------------------------------
# Travel time matrix
# ---------------------------------------------------------------------------

def _speed_for_municipality(municipality: str) -> float:
    """Return the configured average speed (m/s) for a municipality.

    Args:
        municipality: Standardized municipality name.

    Returns:
        Speed in meters per second.
    """
    speed_kmh = MUNICIPALITY_SPEED_KMH.get(municipality, DEFAULT_SPEED_KMH)
    return speed_kmh / 3.6  # km/h -> m/s


def calculate_distances(
    data: pd.DataFrame,
    municipality: str,
    iteration: int,
    time_slot: int,
) -> tuple[dict[int, dict[int, float]], float]:
    """Build the travel time matrix between all pairs of points.

    For each pair (i, j) with i != j, calculates the Haversine distance in
    meters and converts it to travel time (seconds) using the average speed
    configured for the municipality. The diagonal (i == i) receives ``inf``.

    Also calculates the Big-M value needed for the time window constraints
    of the model (the largest value of ``tempo_entrega[i] + travel_time[i][j]
    - (tempo_preparo[i] + time_slot * iteration)``).

    Args:
        data: DataFrame indexed by ``centroid_id`` with columns ``lat``,
            ``lon``, ``tempo_preparo``, and ``tempo_entrega``.
        municipality: Standardized municipality name (for speed selection).
        iteration: Current time iteration (used in Big-M calculation).
        time_slot: Duration of each time slot in seconds.

    Returns:
        Tuple ``(distance_matrix, big_m)`` where ``distance_matrix`` is a
        dict-of-dicts and ``big_m`` is the scalar needed for the constraints.
    """
    speed_ms = _speed_for_municipality(municipality)
    indices = data.index

    distance_matrix: dict[int, dict[int, float]] = {
        i: {j: 0.0 for j in indices} for i in indices
    }

    big_m = -1.0

    for i in indices:
        for j in indices:
            if i == j:
                distance_matrix[i][j] = float("inf")
                continue

            dist_m = haversine(
                data["lat"][i], data["lon"][i],
                data["lat"][j], data["lon"][j],
            )
            travel_time = round(dist_m / speed_ms)
            distance_matrix[i][j] = travel_time

            candidate = (
                data["tempo_entrega"][i]
                + travel_time
                - (data["tempo_preparo"][i] + time_slot * iteration)
            )
            big_m = max(big_m, candidate)

    return distance_matrix, big_m


# ---------------------------------------------------------------------------
# Route extraction from CPLEX solution
# ---------------------------------------------------------------------------

def build_routes(solution: dict, num_vehicles: int) -> dict[int, dict[int, int]]:
    """Extract each vehicle's routes from the solution dictionary.

    Traverses the ``travels_k_i_j`` decision variables present in the
    solution and rebuilds a dictionary of linked lists representing the routes.

    Args:
        solution: Dictionary returned by ``model.solve().as_dict()``.
        num_vehicles: Number of vehicles in the model.

    Returns:
        Dictionary ``{k: {i: j, ...}}`` where each key ``k`` is a vehicle
        and the sub-dictionary maps origin node -> destination node.
    """
    routes: dict[int, dict[int, int]] = {k: {} for k in range(num_vehicles)}

    for var, value in solution.items():
        if not var.name.startswith("t") or value < 0.001:
            continue

        parts = var.name.split("_")[1:]  # ["k", "i", "j"]
        k, i, j = int(parts[0]), int(parts[1]), int(parts[2])
        routes[k][i] = j

    return routes


# ---------------------------------------------------------------------------
# Data preparation (temporal demand partitioning)
# ---------------------------------------------------------------------------

def partition_demand(
    shift: str,
    model_data: pd.DataFrame,
    capacity: int,
    time_slot: int,
) -> pd.DataFrame:
    """Partition demand into time slots when it exceeds capacity.

    For points whose total demand exceeds a single vehicle's capacity,
    distributes the demand across multiple iterations (time slots), allowing
    vehicles to make staggered trips.

    Args:
        shift: Time of day shift (``'manha'``, ``'AFTERNOON'``, ``'NIGHT'``).
        model_data: DataFrame with demand and time window data.
        capacity: Maximum capacity of each vehicle.
        time_slot: Duration of each time slot (seconds).

    Returns:
        Expanded DataFrame with additional rows for each time iteration.
    """
    demand_col = f"{shift}_DEMAND"
    data = model_data.copy()

    # Number of possible splits within the time horizon
    possible_splits = (
        (data["tempo_entrega"] - data["tempo_preparo"]) / time_slot
    ).apply(math.floor)

    # Trips needed per municipality (demand / capacity)
    trips_needed = (
        data.groupby("MUNICIPALITY_ID")[demand_col].sum() / capacity
    ).apply(math.ceil)

    # Municipalities whose total demand fits in a single vehicle
    single_vehicle = data.groupby("MUNICIPALITY_ID")[demand_col].sum() <= capacity

    data["iteracao"] = 0
    data.fillna(0, inplace=True)

    extra_rows: list[pd.DataFrame] = []

    for i in range(1, len(data)):
        municipality = data["MUNICIPALITY_ID"][i]

        if possible_splits[i] <= 0 or single_vehicle[municipality]:
            continue

        viable_splits = min(possible_splits[i], trips_needed[municipality])
        total_demand = data.loc[i, demand_col]
        split_demand = total_demand / viable_splits
        data.loc[i, demand_col] = math.ceil(split_demand)
        remaining = total_demand - math.ceil(split_demand)

        for iteration in range(1, viable_splits):
            row = data.loc[i].copy()
            alloc = min(math.ceil(split_demand), remaining)
            row[demand_col] = alloc
            remaining -= alloc
            row["tempo_preparo"] += time_slot * iteration
            row["iteracao"] = int(iteration)
            extra_rows.append(pd.DataFrame(row).T)

    if not extra_rows:
        return data

    data = pd.concat(
        [data] + extra_rows, ignore_index=True
    ).sort_values("iteracao")
    data = data[data[demand_col] > 0].reset_index(drop=True)
    return data


def partition_demand_failed_instances(
    shift: str,
    model_data: pd.DataFrame,
    capacity: int,
    time_slot: int,
) -> pd.DataFrame:
    """Re-partition demand for instances that failed on the first attempt.

    Variant of :func:`partition_demand` that distributes demand more
    granularly, point-by-point, strictly respecting the vehicle capacity
    at each iteration.

    Args:
        shift: Time of day shift.
        model_data: DataFrame with demand data.
        capacity: Maximum capacity of each vehicle.
        time_slot: Duration of each time slot (seconds).

    Returns:
        Expanded DataFrame with re-partitioned demand per iteration.
    """
    demand_col = f"{shift}_DEMAND"
    data = model_data.copy()

    possible_splits = math.floor(
        (data["tempo_entrega"].iloc[0] - data["tempo_preparo"].iloc[0]) / time_slot
    )

    trips_needed = (
        data.groupby("MUNICIPALITY_ID")[demand_col].sum() / capacity
    ).apply(math.ceil)

    data["iteracao"] = 0
    data.fillna(0, inplace=True)

    for municipality in data["MUNICIPALITY_ID"].unique():
        needed = min(possible_splits, trips_needed[municipality])

        for iteration in range(needed - 1):
            served = 0
            aux = data.copy()
            idx = aux[
                (aux["MUNICIPALITY_ID"] == municipality) & (aux["iteracao"] == iteration)
            ].index

            for i in idx:
                if (served + aux.loc[i, demand_col]) <= capacity:
                    served += aux.loc[i, demand_col]
                    aux.loc[i, demand_col] = 0
                else:
                    aux.loc[i, demand_col] -= capacity - served
                    served = capacity

            complementary_idx = aux.index[~aux.index.isin(idx)]
            aux.loc[complementary_idx, demand_col] = 0
            data[demand_col] = data[demand_col] - aux[demand_col]

            aux = aux[aux["MUNICIPALITY_ID"] == municipality].copy()
            aux["tempo_preparo"] = time_slot * (iteration + 1)
            aux["iteracao"] = iteration + 1
            data = pd.concat([data, aux], ignore_index=True)

    return data
