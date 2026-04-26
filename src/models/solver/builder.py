"""Mixed-Integer Linear Programming (MILP) model construction for the VRPTW.

This module encapsulates the mathematical formulation of the problem: creation
of decision variables, objective function, and constraints. The formulation
follows the classical vehicle routing model with time windows, with subtour
elimination via cutting planes (lazy constraints).

Formulation:
    - **Variables**: pluggable, defined in ``vrptw.variables`` and
      registered in its ``EXECUTION_ORDER``.
    - **Objective**: minimize total travel distance.
    - **Constraints**: pluggable, defined in ``vrptw.constraints`` and
      registered in its ``EXECUTION_ORDER``.

Usage example:
    >>> from docplex.mp.model import Model
    >>> model = Model("vrptw")
    >>> model, travels = build_model(model, model_data)
"""

from docplex.mp.linear import LinearExpr
from docplex.mp.model import Model

from src.globals.config import TIME_SLOT_DURATION
from src.models.constraints import EXECUTION_ORDER as CONSTRAINT_ORDER
from src.models.variables import EXECUTION_ORDER as VARIABLE_ORDER


# ---------------------------------------------------------------------------
# Decision variables
# ---------------------------------------------------------------------------

def _build_variables(
    model: Model,
    model_data: dict,
) -> dict[str, dict]:
    """Create the VRPTW model decision variables.

    Iterates through ``VARIABLE_ORDER`` (defined in ``vrptw.variables``).
    Each function receives ``model_data`` and any variables already created
    by earlier functions (via ``**kwargs``), and returns a ``dict[str, dict]``
    that is merged into the shared variable namespace.

    Args:
        model: DOCPLEX model instance.
        model_data: Dictionary with instance data.

    Returns:
        Dictionary mapping variable-group names (``"travels"``,
        ``"service"``, ``"load"``, …) to their variable dictionaries.
    """
    variables: dict[str, dict] = {}
    for create_vars in VARIABLE_ORDER:
        new_vars = create_vars(model, model_data=model_data, **variables)
        variables.update(new_vars)
    return variables


# ---------------------------------------------------------------------------
# Objective function
# ---------------------------------------------------------------------------

def _build_objective(model: Model, travels: dict, model_data: dict) -> None:
    """Define the objective function: minimize total travel distance.

    Args:
        model: DOCPLEX model instance.
        travels: Travel variable dictionary ``(k, i, j)`` (sparse: no self-loops).
        model_data: Dictionary with ``distance`` (time matrix) and ``data``.
    """
    distances = model_data["distance"]

    model.minimize(
        model.sum(
            var * distances[i][j]
            for (k, i, j), var in travels.items()
        )
    )


# ---------------------------------------------------------------------------
# Constraints
# ---------------------------------------------------------------------------

def _build_constraints(
    model: Model,
    model_data: dict,
    **variables: dict,
) -> None:
    """Add all constraints to the VRPTW model.

    Iterates through ``CONSTRAINT_ORDER`` (defined in ``vrptw.constraints``),
    forwarding the full variable namespace so each constraint function can
    pick exactly the decision-variable groups it needs.

    Args:
        model: DOCPLEX model instance.
        model_data: Dictionary with instance data.
        **variables: Variable dictionaries produced by ``_build_variables``
            (e.g. ``travels``, ``service``, ``load``).
    """
    kwargs = {"model_data": model_data, **variables}
    for add_constraint in CONSTRAINT_ORDER:
        add_constraint(model, **kwargs)


# ---------------------------------------------------------------------------
# LP relaxation
# ---------------------------------------------------------------------------

def relax_model(model: Model) -> None:
    """Relax all integer and binary variables to continuous (LP relaxation).

    Binary variables become continuous on [0, 1]; integer variables become
    continuous with their existing bounds.  The resulting LP provides a
    lower bound on the optimal MIP objective.

    Args:
        model: DOCPLEX model instance (modified in-place).
    """
    continuous = model.continuous_vartype
    for var in model.iter_variables():
        if var.vartype != continuous:
            var.set_vartype(continuous)


# ---------------------------------------------------------------------------
# Subtour elimination
# ---------------------------------------------------------------------------

def add_subtour_cuts(
    model: Model,
    routes: dict[int, dict[int, int]],
    travels: dict,
    vehicle: int,
) -> None:
    """Add subtour elimination constraints for a vehicle.

    Traverses all cycles disconnected from the depot found in the vehicle's
    routes and inserts an inequality that forbids that specific subtour.

    Args:
        model: DOCPLEX model instance.
        routes: Vehicle route dictionary (linked list ``{i: j}``).
        travels: Travel variables ``(k, i, j)``.
        vehicle: Vehicle index.
    """
    cut_count = 0

    while routes[vehicle]:
        cut_expr = LinearExpr(model)
        size = 0

        first_node = next(iter(routes[vehicle]))
        current = routes[vehicle].pop(first_node)
        cut_expr += travels[vehicle, int(first_node), int(current)]

        while current != first_node:
            next_node = routes[vehicle].pop(current)
            cut_expr += travels[vehicle, int(current), int(next_node)]
            size += 1
            current = next_node

        cut_count += 1
        model.add_constraint(cut_expr <= size, f"SubtourCut_{vehicle}_{cut_count}")


def format_route_string(
    routes: dict[int, dict[int, int]],
    travels: dict,
    vehicle: int,
    earliest_departure: int,
    iteration: int,
    distance_matrix: dict,
    time_slot: int = TIME_SLOT_DURATION,
) -> tuple[str, float]:
    """Format a vehicle's route as a readable string.

    Traverses the vehicle's route linked list and produces a descriptive
    string with the path and start/end times.

    Args:
        routes: Vehicle route dictionary.
        travels: Travel variables (not used directly, kept for compatibility).
        vehicle: Vehicle index.
        earliest_departure: Earliest departure time (seconds).
        iteration: Current time iteration.
        distance_matrix: Travel time matrix.
        time_slot: Duration of each time slot (seconds).

    Returns:
        Tuple ``(route_str, total_time)`` where ``route_str`` is a formatted
        description of the route (empty string if empty) and ``total_time``
        is the route's travel time in seconds (0.0 if empty).
    """
    if not routes[vehicle]:
        return "", 0.0

    first_node = next(iter(routes[vehicle]))
    current = routes[vehicle].pop(first_node)

    route_str = f"Vehicle {vehicle} Start [{earliest_departure + time_slot * iteration}s] |Route: 0"
    total_time = distance_matrix[first_node][current]

    while current != first_node:
        next_node = routes[vehicle].pop(current)
        total_time += distance_matrix[current][next_node]
        route_str += f" -> {current}"
        current = next_node

    route_str += " -> 0"
    route_str += f"| End [{earliest_departure + total_time + time_slot * iteration}s]\n"
    return route_str, total_time


# ---------------------------------------------------------------------------
# Main build function
# ---------------------------------------------------------------------------

def build_model(
    model: Model,
    model_data: dict,
) -> tuple[Model, dict]:
    """Build the complete VRPTW model (variables + objective + constraints).

    Args:
        model: DOCPLEX model instance (empty or pre-configured).
        model_data: Dictionary with all instance data.

    Returns:
        Tuple ``(model, travels)`` with the configured model and the
        travel variable dictionary (needed for the solution loop).
    """
    variables = _build_variables(model, model_data)
    _build_objective(model, variables["travels"], model_data)
    _build_constraints(model, model_data, **variables)

    return model, variables["travels"]
