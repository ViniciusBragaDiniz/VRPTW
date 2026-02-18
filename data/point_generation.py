"""Bus stop point generation via K-means clustering.

Uses student geographic data to identify optimal stop locations,
applying the elbow method (Kneedle) to determine the ideal number
of clusters per municipality.

Pipeline:
    1. For each municipality with enough students, runs K-means for
       a range of k values and records the inertia (WCSS).
    2. Identifies the "elbow" in the inertia curve.
    3. Generates final centroids and calculates demand per shift/day.

.. note::
    This module **does not perform any disk I/O**. The function
    ``generate_bus_stops`` receives and returns DataFrames, ensuring
    pipeline idempotency.

Usage example:
    >>> from data.point_generation import generate_bus_stops
    >>> df_stops = generate_bus_stops(df_students, student_filter="full", shift="EXIT")
"""

import logging

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.cluster import k_means

from vrptw.config import (
    IMGS_DIR,
    KMEANS_N_INIT,
    MIN_STUDENTS_PER_MUNICIPALITY,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Elbow method
# ---------------------------------------------------------------------------

def _plot_elbow(
    k_values: np.ndarray,
    inertias: np.ndarray,
    elbow_k: int,
    elbow_index: int,
) -> None:
    """Plot the elbow method chart and save it as an image.

    Draws the inertia curve, the reference line (from first to last point)
    and a perpendicular at the elbow point for visualization.

    Args:
        k_values: Tested k values.
        inertias: Corresponding inertia values (will be scaled x10^4).
        elbow_k: k value identified as the elbow.
        elbow_index: Index of the elbow in the arrays.
    """
    scaled_inertias = inertias * 10_000

    elbow_x = k_values[elbow_index]
    elbow_y = scaled_inertias[elbow_index]

    x1, y1 = k_values[0], scaled_inertias[0]
    x2, y2 = k_values[-1], scaled_inertias[-1]

    # Reference line slope and its perpendicular
    if x2 - x1 != 0:
        ref_slope = (y2 - y1) / (x2 - x1)
    else:
        ref_slope = np.inf

    if ref_slope not in (0, np.inf):
        perp_slope = -1 / ref_slope
    elif ref_slope == 0:
        perp_slope = np.inf
    else:
        perp_slope = 0

    x_range = np.linspace(min(k_values), max(k_values), 100)
    if perp_slope != np.inf:
        perp_y = perp_slope * (x_range - elbow_x) + elbow_y
    else:
        perp_y = np.linspace(min(scaled_inertias), max(scaled_inertias), 100)
        x_range = np.full_like(perp_y, elbow_x)

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(k_values, scaled_inertias, "bo-", label="Inertia Curve")
    ax.plot([x1, x2], [y1, y2], "r-", label="Reference Line")
    ax.plot(elbow_x, elbow_y, "go", markersize=10, label=f"Elbow (k={elbow_k})")
    ax.plot(x_range, perp_y, "g--", label="Perpendicular at Elbow")

    ax.set_xlabel("Number of Clusters (k)")
    ax.set_ylabel("Inertia (WCSS) x 10^4")
    ax.set_xticks(k_values)
    ax.set_aspect("equal", "box")
    ax.grid(True)

    amplitude = max(scaled_inertias) - min(scaled_inertias)
    ax.set_ylim(
        min(scaled_inertias) - 0.1 * amplitude,
        max(scaled_inertias) + 0.1 * amplitude,
    )
    ax.legend(loc="lower center", ncol=4, fancybox=True, shadow=True,
              bbox_to_anchor=(0.5, -0.2))
    fig.tight_layout()

    IMGS_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(IMGS_DIR / "elbow_illustration.png")
    plt.close(fig)


def find_elbow(
    k_values: list | np.ndarray,
    inertias: list | np.ndarray,
    plot: bool = False,
) -> int:
    """Find the optimal k using the elbow method (Kneedle).

    Identifies the point on the inertia curve with the greatest perpendicular
    distance to the line drawn between the first and last points.

    Args:
        k_values: Tested k values.
        inertias: Corresponding inertia values.
        plot: If ``True``, generates and saves the elbow chart.

    Returns:
        The k value considered optimal.
    """
    k_arr = np.array(k_values)
    inertia_arr = np.array(inertias)

    x1, y1 = k_arr[0], inertia_arr[0]
    x2, y2 = k_arr[-1], inertia_arr[-1]

    line_vec = np.array([x2 - x1, y2 - y1])
    line_unit = line_vec / np.linalg.norm(line_vec)

    points = np.vstack((k_arr, inertia_arr)).T
    from_start = points - np.array([x1, y1])

    projections = np.outer(np.dot(from_start, line_unit), line_unit)
    perpendicular = from_start - projections
    distances = np.linalg.norm(perpendicular, axis=1)

    elbow_idx = int(np.argmax(distances))

    if plot:
        _plot_elbow(k_arr, inertia_arr, k_arr[elbow_idx], elbow_idx)

    return k_arr[elbow_idx]


# ---------------------------------------------------------------------------
# Bus stop generation
# ---------------------------------------------------------------------------

def generate_bus_stops(
    df_students: pd.DataFrame,
    student_filter: str = "full",
    shift: str = "EXIT",
) -> pd.DataFrame:
    """Generate bus stop points (centroids) from student data.

    For each municipality with enough students, applies K-means and the
    elbow method to determine the optimal number of clusters. Calculates
    demand per shift and weekday for each generated centroid.

    **Does not perform any disk I/O** — receives and returns DataFrames,
    ensuring idempotency.

    Args:
        df_students: DataFrame with student data (output from
            preprocessing).
        student_filter: Student type filter (``"full"`` for all,
            ``"tec"`` for technical, ``"undergrad"`` for undergraduate).
        shift: Shift to consider (``"ENTRY"`` or ``"EXIT"``).

    Returns:
        DataFrame with columns ``lon``, ``lat``, ``MUNICIPALITY_ID``,
        ``MORNING_DEMAND``, ``AFTERNOON_DEMAND``, ``NIGHT_DEMAND``,
        ``LATE_DEMAND`` and ``DAYOFTHEWEEK``.
    """
    logger.info("Generating bus stops: filter=%s, shift=%s", student_filter, shift)

    # Copy to avoid modifying the caller's DataFrame
    df_students = df_students.copy()
    df_students.columns = df_students.columns.str.upper()

    if student_filter != "full":
        df_students = df_students[
            df_students["STUDENT_ID"].str.contains(student_filter)
        ]

    municipalities = df_students["CITY"].unique()
    weekdays = df_students["DAYOFTHEWEEK"].unique()

    bus_stops: list[pd.DataFrame] = []
    skipped_municipalities = 0
    skipped_students = 0

    for municipality in municipalities:
        mun_students = df_students[
            df_students["CITY"] == municipality
        ].drop_duplicates(subset="STUDENT_ID")

        if len(mun_students) < MIN_STUDENTS_PER_MUNICIPALITY:
            skipped_municipalities += 1
            skipped_students += len(mun_students)
            continue

        logger.info("Municipality: %s | Students: %d", municipality, len(mun_students))

        # Determine optimal k via elbow method
        k_range = range(2, len(mun_students) + 1)
        wcss = []
        for k in k_range:
            _, _, inertia = k_means(
                mun_students[["LATITUDE", "LONGITUDE"]], k, n_init=KMEANS_N_INIT,
            )
            wcss.append(inertia)

        optimal_k = find_elbow(k_range, wcss, plot=False)

        # Generate centroids with optimal k
        centroids, classes, _ = k_means(
            mun_students[["LATITUDE", "LONGITUDE"]], optimal_k, n_init=KMEANS_N_INIT,
        )
        mun_students = mun_students.copy()
        mun_students["CLUSTER"] = classes

        merged = df_students.merge(
            mun_students[["STUDENT_ID", "CLUSTER"]], how="left", on="STUDENT_ID",
        )

        for day in weekdays:
            centroids_df = pd.DataFrame(centroids, columns=["lon", "lat"])
            centroids_df["MUNICIPALITY_ID"] = municipality

            day_filter = merged["DAYOFTHEWEEK"] == day
            shift_col = f"{shift}_SHIFT"

            for demand_name, shift_value in [
                ("MORNING_DEMAND", "MORNING"),
                ("AFTERNOON_DEMAND", "AFTERNOON"),
                ("NIGHT_DEMAND", "NIGHT"),
                ("LATE_DEMAND", "LATE"),
            ]:
                demand = (
                    merged[(merged[shift_col] == shift_value) & day_filter]
                    .groupby("CLUSTER")[shift_col]
                    .count()
                )
                centroids_df.loc[demand.index, demand_name] = demand

            centroids_df["DAYOFTHEWEEK"] = day
            centroids_df.fillna(0, inplace=True)
            bus_stops.append(centroids_df)

    result = pd.concat(bus_stops, ignore_index=True)

    logger.info(
        "Skipped municipalities: %d | Skipped students: %d",
        skipped_municipalities,
        skipped_students,
    )

    return result
