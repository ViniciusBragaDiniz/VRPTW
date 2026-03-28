"""Post-processing: vehicle count minimization per trip.

After solving the VRPTW, this module attempts to reduce the number of vehicles
used in each trip (combination of route type, instance, day, shift, and
municipality). The algorithm generates all possible partitions of route travel
times and searches for the valid partition with the fewest subsets, subject to
the maximum work time per vehicle.

Usage example:
    >>> from vrptw.postprocessing import minimize_vehicles
    >>> df_adjusted = minimize_vehicles()
    >>> print(df_adjusted.head())
"""

import logging

import pandas as pd

from .config import INSTANCE_TYPES, MAX_VEHICLE_WORK_TIME, OUTPUT_CSV_DIR, ROUTE_TYPES

logger = logging.getLogger(__name__)


MAX_PARTITION_ELEMENTS = 12


def generate_partitions(elements: list) -> list[list[list]]:
    """Recursively generate all partitions of a list.

    A partition groups elements into non-empty, disjoint subsets whose
    union is the original set.

    Args:
        elements: List of elements to partition.

    Returns:
        List of partitions. Each partition is a list of subsets (lists).

    Raises:
        ValueError: If the input exceeds ``MAX_PARTITION_ELEMENTS`` (Bell
            numbers grow super-exponentially).

    Example:
        >>> generate_partitions([1, 2])
        [[[2, 1]], [[1], [2]]]
    """
    if len(elements) > MAX_PARTITION_ELEMENTS:
        raise ValueError(
            f"Cannot partition {len(elements)} elements "
            f"(limit {MAX_PARTITION_ELEMENTS}): Bell numbers grow super-exponentially."
        )

    if len(elements) == 1:
        return [[elements]]

    first = elements[0]
    result = []

    for partition in generate_partitions(elements[1:]):
        for i in range(len(partition)):
            new_partition = [subset[:] for subset in partition]
            new_partition[i].append(first)
            result.append(new_partition)

        result.append([[first]] + partition)

    return result


def minimize_vehicles(
    instance_types: list[str] | None = None,
    route_types: list[str] | None = None,
) -> pd.DataFrame:
    """Re-sequence trips to minimize the number of vehicles used.

    Loads the detailed route solutions for the given instance and route
    types, identifies trips with multiple vehicles, and attempts to
    consolidate them into fewer vehicles subject to the maximum work
    time constraint.

    Args:
        instance_types: Instance names to process (default: ``INSTANCE_TYPES``
            from config).
        route_types: Route directions to process (default: ``ROUTE_TYPES``
            from config).

    Returns:
        DataFrame with the adjusted vehicle count per trip.

    Raises:
        FileNotFoundError: If no solution files are found.
    """
    instance_types = instance_types or INSTANCE_TYPES
    route_types = route_types or ROUTE_TYPES

    logger.info(
        "Starting vehicle minimization (instances=%s, routes=%s)",
        instance_types, route_types,
    )

    frames: list[pd.DataFrame] = []
    for instance_name in instance_types:
        for route_type in route_types:
            path = (
                OUTPUT_CSV_DIR
                / f"detailed_solution_cvrptw_{instance_name}_{route_type}.csv"
            )
            if not path.exists():
                logger.warning("Solution file not found, skipping: %s", path)
                continue
            df = pd.read_csv(path)
            df["route_type"] = route_type
            frames.append(df)

    if not frames:
        raise FileNotFoundError(
            f"No solution files found for instance_types={instance_types}, "
            f"route_types={route_types} in {OUTPUT_CSV_DIR}"
        )

    full_solution = pd.concat(frames, ignore_index=True)

    # Aggregated summary per trip
    group_cols = ["route_type", "INSTANCE", "DAYOFTHEWEEK", "SHIFT", "MUNICIPALITY_ID"]
    adjusted = full_solution.groupby(group_cols).agg(
        vehicle_id=("vehicle_id", "nunique"),
        travel_time=("travel_time", "sum"),
    )

    # Identify unique trips
    trips = full_solution[group_cols].drop_duplicates()
    indexed_solution = full_solution.set_index(group_cols)

    adjusted_count = 0

    for _, row in trips.iterrows():
        trip_key = tuple(row)
        trip_data = indexed_solution.loc[trip_key]

        # Skip single-vehicle trips (no reduction possible)
        if trip_data["vehicle_id"].nunique() == 1:
            continue

        travel_times = trip_data["travel_time"].tolist()

        if len(travel_times) > MAX_PARTITION_ELEMENTS:
            logger.warning(
                "Trip %s has %d vehicles, exceeding partition limit (%d). Skipping.",
                trip_key, len(travel_times), MAX_PARTITION_ELEMENTS,
            )
            continue

        partitions = generate_partitions(travel_times)

        for partition in partitions:
            valid = all(
                sum(subset) <= MAX_VEHICLE_WORK_TIME
                for subset in partition
            )
            if valid:
                adjusted.loc[trip_key, "vehicle_id"] = len(partition)
                adjusted_count += 1
                break

    adjusted = adjusted.reset_index()
    output_path = OUTPUT_CSV_DIR / "solution_adjusted.csv"
    adjusted.to_csv(output_path, index=False)

    logger.info(
        "Minimization complete. %d trips adjusted. Saved to: %s",
        adjusted_count,
        output_path,
    )
    return adjusted
