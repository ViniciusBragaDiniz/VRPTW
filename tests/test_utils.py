"""Tests for vrptw.utils — haversine, distance matrix, route extraction."""

import math

import pandas as pd
import pytest

from src.pipeline.utils import build_routes, calculate_distances, haversine


# ── Haversine ──────────────────────────────────────────────────────────────


class TestHaversine:
    def test_same_point_returns_zero(self):
        assert haversine(-22.70, -43.46, -22.70, -43.46) == 0.0

    def test_one_degree_latitude_at_equator(self):
        dist = haversine(0.0, 0.0, 1.0, 0.0)
        assert abs(dist - 111_195) < 200

    def test_known_distance_rio_sao_paulo(self):
        dist = haversine(-22.9068, -43.1729, -23.5505, -46.6333)
        assert 350_000 < dist < 370_000

    def test_symmetry(self):
        a = haversine(-22.70, -43.46, -22.90, -43.20)
        b = haversine(-22.90, -43.20, -22.70, -43.46)
        assert abs(a - b) < 1e-6

    def test_antipodal_points(self):
        dist = haversine(0.0, 0.0, 0.0, 180.0)
        half_circumference = math.pi * 6_371_000
        assert abs(dist - half_circumference) < 100


# ── Distance matrix ───────────────────────────────────────────────────────


class TestCalculateDistances:
    @pytest.fixture
    def two_node_df(self):
        df = pd.DataFrame({
            "lat": [-22.70, -22.71],
            "lon": [-43.46, -43.46],
            "earliest_departure": [0, 0],
            "latest_arrival": [14_400, 14_400],
        })
        df.index.name = "centroid_id"
        return df

    @pytest.fixture
    def three_node_df(self):
        df = pd.DataFrame({
            "lat": [-22.70, -22.71, -22.72],
            "lon": [-43.46, -43.46, -43.46],
            "earliest_departure": [0, 0, 0],
            "latest_arrival": [14_400, 14_400, 14_400],
        })
        df.index.name = "centroid_id"
        return df

    def test_diagonal_is_inf(self, two_node_df):
        dists, _ = calculate_distances(two_node_df, "Rio De Janeiro", 0, 1800)
        for i in two_node_df.index:
            assert dists[i][i] == float("inf")

    def test_non_diagonal_non_negative(self, three_node_df):
        dists, _ = calculate_distances(three_node_df, "Rio De Janeiro", 0, 1800)
        for i in three_node_df.index:
            for j in three_node_df.index:
                if i != j:
                    assert dists[i][j] >= 0

    def test_symmetry(self, two_node_df):
        dists, _ = calculate_distances(two_node_df, "Rio De Janeiro", 0, 1800)
        assert dists[0][1] == dists[1][0]

    def test_big_m_positive(self, two_node_df):
        _, big_m = calculate_distances(two_node_df, "Rio De Janeiro", 0, 1800)
        assert big_m > 0

    def test_uses_default_speed_for_unknown_municipality(self, two_node_df):
        dists_known, _ = calculate_distances(
            two_node_df, "Rio De Janeiro", 0, 1800,
        )
        dists_unknown, _ = calculate_distances(
            two_node_df, "UnknownCity", 0, 1800,
        )
        assert dists_known[0][1] != dists_unknown[0][1]


# ── Route extraction ──────────────────────────────────────────────────────


class _Var:
    """Minimal mock for a docplex decision variable (exposes ``.name``)."""

    def __init__(self, name: str):
        self.name = name


class TestBuildRoutes:
    def test_single_vehicle_route(self):
        solution = {
            _Var("travels_0_0_1"): 1.0,
            _Var("travels_0_1_0"): 1.0,
        }
        routes = build_routes(solution, 1)
        assert routes == {0: {0: 1, 1: 0}}

    def test_multi_vehicle_routes(self):
        solution = {
            _Var("travels_0_0_1"): 1.0,
            _Var("travels_0_1_0"): 1.0,
            _Var("travels_1_0_2"): 1.0,
            _Var("travels_1_2_0"): 1.0,
        }
        routes = build_routes(solution, 2)
        assert routes[0] == {0: 1, 1: 0}
        assert routes[1] == {0: 2, 2: 0}

    def test_empty_solution(self):
        routes = build_routes({}, 2)
        assert routes == {0: {}, 1: {}}

    def test_ignores_zero_values(self):
        solution = {
            _Var("travels_0_0_1"): 1.0,
            _Var("travels_0_1_0"): 1.0,
            _Var("travels_0_0_2"): 0.0,
        }
        routes = build_routes(solution, 1)
        assert 2 not in routes[0].values()

    def test_ignores_non_travel_variables(self):
        solution = {
            _Var("travels_0_0_1"): 1.0,
            _Var("travels_0_1_0"): 1.0,
            _Var("service_start_0_1"): 200.0,
            _Var("load_0_1"): 5.0,
        }
        routes = build_routes(solution, 1)
        assert routes == {0: {0: 1, 1: 0}}
