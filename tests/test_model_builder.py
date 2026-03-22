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


class TestVariablePackage:
    """Verify the pluggable variable registry."""

    def test_execution_order_is_non_empty(self):
        from vrptw.variables import EXECUTION_ORDER

        assert len(EXECUTION_ORDER) > 0

    def test_all_entries_are_callable(self):
        from vrptw.variables import EXECUTION_ORDER

        for fn in EXECUTION_ORDER:
            assert callable(fn), f"{fn} is not callable"

    def test_execution_order_matches_expected_count(self):
        from vrptw.variables import EXECUTION_ORDER

        assert len(EXECUTION_ORDER) == 3

    def test_build_variables_returns_expected_keys(self, trivial_model_data):
        from vrptw.model_builder import _build_variables

        model = Model("test_var_keys")
        variables = _build_variables(model, trivial_model_data)

        assert "travels" in variables
        assert "service" in variables
        assert "load" in variables

    def test_individual_variable_fn_returns_dict(self, trivial_model_data):
        from vrptw.variables import EXECUTION_ORDER

        model = Model("test_var_individual")
        accumulated: dict[str, dict] = {}

        for create_vars in EXECUTION_ORDER:
            result = create_vars(
                model, model_data=trivial_model_data, **accumulated,
            )
            assert isinstance(result, dict)
            for key, val in result.items():
                assert isinstance(key, str)
                assert isinstance(val, dict)
            accumulated.update(result)

    def test_travels_excludes_self_loops(self, trivial_model_data):
        from vrptw.variables.travels import create_travels

        model = Model("test_no_loops")
        result = create_travels(model, model_data=trivial_model_data)

        for k, i, j in result["travels"]:
            assert i != j


class TestConstraintPackage:
    """Verify the pluggable constraint registry."""

    def test_execution_order_is_non_empty(self):
        from vrptw.constraints import EXECUTION_ORDER

        assert len(EXECUTION_ORDER) > 0

    def test_all_entries_are_callable(self):
        from vrptw.constraints import EXECUTION_ORDER

        for fn in EXECUTION_ORDER:
            assert callable(fn), f"{fn} is not callable"

    def test_execution_order_matches_expected_count(self):
        from vrptw.constraints import EXECUTION_ORDER

        assert len(EXECUTION_ORDER) == 8

    def test_individual_constraint_adds_constraints(self, trivial_model_data):
        """Each constraint function in EXECUTION_ORDER should add at
        least one constraint (or silently no-op) without raising."""
        from vrptw.model_builder import _build_variables

        model = Model("test_individual")
        variables = _build_variables(model, trivial_model_data)
        kwargs = {"model_data": trivial_model_data, **variables}

        from vrptw.constraints import EXECUTION_ORDER

        for add_constraint in EXECUTION_ORDER:
            before = model.number_of_constraints
            add_constraint(model, **kwargs)
            after = model.number_of_constraints
            assert after >= before, (
                f"{add_constraint.__name__} removed constraints"
            )

    def test_constraint_names_are_unique(self, trivial_model_data):
        """All constraint names generated by the full build must be unique."""
        from vrptw.model_builder import build_model

        model = Model("test_names")
        model, _ = build_model(model, trivial_model_data)

        names = [ct.name for ct in model.iter_constraints() if ct.name]
        assert len(names) == len(set(names)), "Duplicate constraint names found"
