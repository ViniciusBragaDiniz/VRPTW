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

from .config import MAX_VEHICLE_WORK_TIME, OUTPUT_CSV_DIR

logger = logging.getLogger(__name__)


def generate_partitions(elements: list) -> list[list[list]]:
    """Recursively generate all partitions of a list.

    A partition groups elements into non-empty, disjoint subsets whose
    union is the original set.

    Args:
        elements: List of elements to partition.

    Returns:
        List of partitions. Each partition is a list of subsets (lists).

    Example:
        >>> generate_partitions([1, 2])
        [[[2, 1]], [[1], [2]]]
    """
    if len(elements) == 1:
        return [[elements]]

    first = elements[0]
    result = []

    for partition in generate_partitions(elements[1:]):
        # Add the first element to each existing subset
        for i in range(len(partition)):
            new_partition = [subset[:] for subset in partition]
            new_partition[i].append(first)
            result.append(new_partition)

        # Create a new subset containing only the first element
        result.append([[first]] + partition)

    return result


def minimize_vehicles() -> pd.DataFrame:
    """Re-sequence trips to minimize the number of vehicles used.

    Loads the detailed route solutions (inbound and outbound), identifies
    trips with multiple vehicles, and attempts to consolidate them into
    fewer vehicles subject to the maximum work time constraint.

    Returns:
        DataFrame with the adjusted vehicle count per trip.

    Raises:
        FileNotFoundError: If the solution files are not found.
    """
    logger.info("Starting vehicle minimization")

    # Load solutions
    sol_ENTRY = pd.read_csv(OUTPUT_CSV_DIR / "solution_completa_cvrptw_full_ENTRY.csv")
    sol_ENTRY["tipo_de_rota"] = "ENTRY"

    solution_exit = pd.read_csv(OUTPUT_CSV_DIR / "solution_completa_cvrptw_full_EXIT.csv")
    solution_exit["tipo_de_rota"] = "EXIT"

    full_solution = pd.concat([sol_ENTRY, solution_exit], ignore_index=True)

    # Aggregated summary per trip
    group_cols = ["tipo_de_rota", "instancia", "DAYOFTHEWEEK", "turno", "cd_municipio"]
    adjusted = full_solution.groupby(group_cols).agg(
        id_veiculo=("id_veiculo", "nunique"),
        tempo_viagem=("tempo_viagem", "sum"),
    )

    # Identify unique trips
    trips = full_solution[group_cols].drop_duplicates()
    indexed_solution = full_solution.set_index(group_cols)

    adjusted_count = 0

    for _, row in trips.iterrows():
        trip_key = tuple(row)
        trip_data = indexed_solution.loc[trip_key]

        # Skip single-vehicle trips (no reduction possible)
        if trip_data["id_veiculo"].nunique() == 1:
            continue

        travel_times = trip_data["tempo_viagem"].tolist()
        partitions = generate_partitions(travel_times)

        # Search for the first valid partition (already sorted smallest to largest)
        for partition in partitions:
            valid = all(
                sum(subset) <= MAX_VEHICLE_WORK_TIME
                for subset in partition
            )
            if valid:
                adjusted.loc[trip_key, "id_veiculo"] = len(partition)
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
