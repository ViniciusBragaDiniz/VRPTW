"""Model builder sanity tests — build, solve, and verify tiny instances.

Tests that require solving (marked ``requires_cplex``) are skipped when no
CPLEX runtime is found.  Pure model-construction tests always run.
"""

import pytest

try:
    from docplex.mp.model import Model

    HAS_DOCPLEX = True
except ImportError:
    HAS_DOCPLEX = False

pytestmark = pytest.mark.skipif(not HAS_DOCPLEX, reason="docplex not installed")


def _cplex_available() -> bool:
    """Return True when a CPLEX solve actually works."""
    if not HAS_DOCPLEX:
        return False
    try:
        m = Model("probe")
        x = m.binary_var("x")
        m.maximize(x)
        return m.solve() is not None
    except Exception:  # noqa: BLE001
        return False


requires_cplex = pytest.mark.skipif(
    not _cplex_available(), reason="CPLEX runtime not available",
)


class TestBuildModel:
    """Sanity tests per OR_GUIDE §11.2."""

    @requires_cplex
    def test_trivial_instance_builds_and_solves(self, trivial_model_data):
        from vrptw.model_builder import build_model

        model = Model("test_trivial")
        model, travels = build_model(model, trivial_model_data)

        assert len(travels) > 0
        solution = model.solve()
        assert solution is not None

    @requires_cplex
    def test_trivial_objective_nonnegative(self, trivial_model_data):
        from vrptw.model_builder import build_model

        model = Model("test_obj")
        model, _ = build_model(model, trivial_model_data)
        solution = model.solve()

        assert solution is not None
        assert model.objective_value >= 0

    @requires_cplex
    def test_trivial_solution_is_feasible(self, trivial_model_data):
        """Solve a trivial instance and validate with the validation module."""
        from vrptw.model_builder import build_model
        from vrptw.utils import build_routes
        from vrptw.validation import validate_solution

        model = Model("test_feasibility")
        model, travels = build_model(model, trivial_model_data)
        solution_obj = model.solve()
        assert solution_obj is not None

        routes = build_routes(solution_obj.as_dict(), trivial_model_data["necessary_vehicles"])
        violations = validate_solution(routes, trivial_model_data)
        assert violations == [], f"Unexpected violations: {violations}"

    @requires_cplex
    def test_small_instance_solves(self, small_model_data):
        from vrptw.model_builder import build_model

        model = Model("test_small")
        model, _ = build_model(model, small_model_data)
        solution = model.solve()

        assert solution is not None
        assert model.objective_value >= 0

    @requires_cplex
    def test_infeasible_instance_returns_none(self, infeasible_model_data):
        from vrptw.model_builder import build_model

        model = Model("test_infeasible")
        model, _ = build_model(model, infeasible_model_data)
        solution = model.solve()

        assert solution is None


class TestVariableCreation:
    """Verify sparse variable creation (no self-loops)."""

    def test_no_self_loop_variables(self, trivial_model_data):
        from vrptw.model_builder import build_model

        model = Model("test_vars")
        model, travels = build_model(model, trivial_model_data)

        for k, i, j in travels:
            assert i != j, f"Self-loop variable found: ({k}, {i}, {j})"
