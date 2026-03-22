"""Tests for vrptw.validation — input data and solution checks."""

from vrptw.validation import validate_input_data, validate_solution


# ── validate_input_data ────────────────────────────────────────────────────


class TestValidateInputData:
    def test_valid_data_returns_no_errors(self, trivial_model_data):
        assert validate_input_data(trivial_model_data) == []

    def test_valid_small_instance(self, small_model_data):
        assert validate_input_data(small_model_data) == []

    def test_missing_keys(self):
        errors = validate_input_data({"capacity": 10})
        assert len(errors) == 1
        assert "Missing required keys" in errors[0]

    def test_negative_capacity(self, trivial_model_data):
        trivial_model_data["capacity"] = -1
        errors = validate_input_data(trivial_model_data)
        assert any("Capacity" in e for e in errors)

    def test_zero_vehicles(self, trivial_model_data):
        trivial_model_data["necessary_vehicles"] = 0
        errors = validate_input_data(trivial_model_data)
        assert any("vehicle" in e.lower() for e in errors)

    def test_invalid_time_window(self, trivial_model_data):
        trivial_model_data["data"].loc[1, "earliest_departure"] = 20_000
        trivial_model_data["data"].loc[1, "latest_arrival"] = 10_000
        errors = validate_input_data(trivial_model_data)
        assert any("time window" in e.lower() for e in errors)

    def test_negative_demand(self, trivial_model_data):
        trivial_model_data["data"].loc[1, "AFTERNOON_DEMAND"] = -5
        errors = validate_input_data(trivial_model_data)
        assert any("Negative demand" in e for e in errors)

    def test_negative_distance(self, trivial_model_data):
        trivial_model_data["distance"][0][1] = -10
        errors = validate_input_data(trivial_model_data)
        assert any("Negative distance" in e for e in errors)

    def test_negative_big_m(self, trivial_model_data):
        trivial_model_data["big_m"] = -1
        errors = validate_input_data(trivial_model_data)
        assert any("big_m" in e for e in errors)

    def test_missing_dataframe_column(self, trivial_model_data):
        trivial_model_data["data"] = trivial_model_data["data"].drop(
            columns=["lat"]
        )
        errors = validate_input_data(trivial_model_data)
        assert any("missing columns" in e.lower() for e in errors)


# ── validate_solution ──────────────────────────────────────────────────────


class TestValidateSolution:
    def test_valid_trivial_solution(self, trivial_model_data):
        routes = {0: {0: 1, 1: 0}}
        assert validate_solution(routes, trivial_model_data) == []

    def test_capacity_violation(self, trivial_model_data):
        trivial_model_data["capacity"] = 2
        routes = {0: {0: 1, 1: 0}}
        violations = validate_solution(routes, trivial_model_data)
        assert any(v["type"] == "capacity" for v in violations)

    def test_unvisited_client(self, trivial_model_data):
        routes = {0: {}}
        violations = validate_solution(routes, trivial_model_data)
        assert any(v["type"] == "demand" for v in violations)

    def test_time_window_violation(self, trivial_model_data):
        trivial_model_data["data"].loc[1, "latest_arrival"] = 50
        trivial_model_data["distance"][0][1] = 100
        routes = {0: {0: 1, 1: 0}}
        violations = validate_solution(routes, trivial_model_data)
        assert any(v["type"] == "time_window" for v in violations)

    def test_duplicate_visit_flagged(self, small_model_data):
        routes = {
            0: {0: 1, 1: 0},
            1: {0: 1, 1: 0},  # vehicle 1 also visits node 1
        }
        violations = validate_solution(routes, small_model_data)
        assert any(v["type"] == "flow" for v in violations)

    def test_empty_routes_with_demand(self, trivial_model_data):
        routes = {0: {}}
        violations = validate_solution(routes, trivial_model_data)
        assert len(violations) > 0

    def test_no_demand_no_violation(self, trivial_model_data):
        trivial_model_data["data"].loc[1, "AFTERNOON_DEMAND"] = 0
        routes = {0: {}}
        assert validate_solution(routes, trivial_model_data) == []
