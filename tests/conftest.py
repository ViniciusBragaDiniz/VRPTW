"""Shared fixtures for VRPTW tests."""

import pandas as pd
import pytest


def _make_model_data(
    *,
    lats: list[float],
    lons: list[float],
    demands: list[int],
    capacity: int,
    num_vehicles: int,
    distances: dict[int, dict[int, float]],
    big_m: float,
    earliest: list[int] | None = None,
    latest: list[int] | None = None,
) -> dict:
    """Helper to build a ``model_data`` dict from compact parameters."""
    n = len(lats)
    earliest = earliest or [0] * n
    latest = latest or [14_400] * n

    city_data = pd.DataFrame({
        "lat": lats,
        "lon": lons,
        "AFTERNOON_DEMAND": demands,
        "earliest_departure": earliest,
        "latest_arrival": latest,
        "MUNICIPALITY_ID": ["CEFET"] + ["Rio De Janeiro"] * (n - 1),
    })
    city_data.index.name = "centroid_id"

    return {
        "data": city_data,
        "num_spots": n,
        "necessary_vehicles": num_vehicles,
        "capacity": capacity,
        "iteration": 0,
        "time_slot": 1800,
        "SHIFT": "AFTERNOON",
        "distance": distances,
        "big_m": big_m,
        "depot": 0,
    }


@pytest.fixture
def trivial_model_data():
    """Depot + 1 client, 1 vehicle — minimal solvable instance."""
    return _make_model_data(
        lats=[-22.70, -22.71],
        lons=[-43.46, -43.46],
        demands=[0, 5],
        capacity=50,
        num_vehicles=1,
        distances={
            0: {0: float("inf"), 1: 100},
            1: {0: 100, 1: float("inf")},
        },
        big_m=14_500,
    )


@pytest.fixture
def small_model_data():
    """Depot + 3 clients, 2 vehicles — solvable with moderate load."""
    return _make_model_data(
        lats=[-22.70, -22.71, -22.72, -22.73],
        lons=[-43.46, -43.46, -43.46, -43.46],
        demands=[0, 10, 10, 10],
        capacity=20,
        num_vehicles=2,
        distances={
            0: {0: float("inf"), 1: 100, 2: 200, 3: 300},
            1: {0: 100, 1: float("inf"), 2: 100, 3: 200},
            2: {0: 200, 1: 100, 2: float("inf"), 3: 100},
            3: {0: 300, 1: 200, 2: 100, 3: float("inf")},
        },
        big_m=14_700,
    )


@pytest.fixture
def infeasible_model_data():
    """Demand exceeds total fleet capacity — infeasible."""
    return _make_model_data(
        lats=[-22.70, -22.71],
        lons=[-43.46, -43.46],
        demands=[0, 100],
        capacity=10,
        num_vehicles=1,
        distances={
            0: {0: float("inf"), 1: 100},
            1: {0: 100, 1: float("inf")},
        },
        big_m=14_500,
    )
