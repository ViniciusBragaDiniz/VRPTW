"""Tests for data.point_generation — elbow detection."""

import numpy as np

from data.point_generation import find_elbow


class TestFindElbow:
    def test_clear_elbow(self):
        k_values = [2, 3, 4, 5, 6, 7]
        inertias = [1000, 200, 50, 40, 35, 32]
        elbow = find_elbow(k_values, inertias)
        assert elbow in {3, 4}

    def test_returns_value_in_range(self):
        k_values = [2, 3, 4, 5]
        inertias = [100, 75, 50, 25]
        elbow = find_elbow(k_values, inertias)
        assert elbow in k_values

    def test_steep_then_flat(self):
        k_values = list(range(2, 10))
        inertias = [500, 100, 90, 85, 83, 82, 81.5, 81]
        elbow = find_elbow(k_values, inertias)
        assert 3 <= elbow <= 5

    def test_accepts_numpy_arrays(self):
        k_arr = np.array([2, 3, 4, 5, 6])
        inertias = np.array([100, 30, 15, 12, 11])
        elbow = find_elbow(k_arr, inertias)
        assert elbow in k_arr
