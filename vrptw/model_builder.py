"""Mixed-Integer Linear Programming (MILP) model construction for the VRPTW.

This module encapsulates the mathematical formulation of the problem: creation
of decision variables, objective function, and constraints. The formulation
follows the classical vehicle routing model with time windows, with subtour
elimination via cutting planes (lazy constraints).

Formulation:
    - **Variables**:
        - ``x[k,i,j]``: binary, 1 if vehicle k travels from i to j.
        - ``s[k,i]``: continuous, service start time at node i by vehicle k.
        - ``q[k,i]``: integer, load served at node i by vehicle k.
    - **Objective**: minimize total travel distance.
    - **Constraints**: capacity, mandatory service, flow conservation,
      time windows (Big-M), single visit, and subtour elimination.

Usage example:
    >>> from docplex.mp.model import Model
    >>> model = Model("vrptw")
    >>> model, travels = build_model(model, model_data)
"""

from docplex.mp.linear import LinearExpr
from docplex.mp.model import Model


# ---------------------------------------------------------------------------
# Decision variables
# ---------------------------------------------------------------------------

def _build_variables(
    model: Model,
    model_data: dict,
) -> tuple[dict, dict, dict]:
    """Create the VRPTW model decision variables.

    Args:
        model: DOCPLEX model instance.
        model_data: Dictionary with instance data. Expects keys
            ``necessary_vehicles``, ``capacity``, ``data`` (DataFrame).

    Returns:
        Tuple ``(travels, service, vehicle_load)`` containing variable
        dictionaries indexed by ``(k, i, j)`` or ``(k, i)``.
    """
    num_vehicles = model_data["necessary_vehicles"]
    capacity = model_data["capacity"]
    city_data = model_data["data"]

    # x[k,i,j] - vehicle k travels from node i to node j
    travels = {
        (k, i, j): model.binary_var(name=f"travels_{k}_{i}_{j}")
        for k in range(num_vehicles)
        for i in city_data.index
        for j in city_data.index
    }

    # s[k,i] - service start time at node i by vehicle k
    service = {
        (k, i): model.continuous_var(
            lb=city_data["tempo_preparo"][i],
            ub=city_data["tempo_entrega"][i],
            name=f"service_start_{k}_{i}",
        )
        for k in range(num_vehicles)
        for i in city_data.index
    }

    # q[k,i] - load served at node i by vehicle k
    vehicle_load = {
        (k, i): model.integer_var(
            lb=0, ub=capacity, name=f"load_{k}_{i}"
        )
        for k in range(num_vehicles)
        for i in city_data.index
    }

    return travels, service, vehicle_load


# ---------------------------------------------------------------------------
# Objective function
# ---------------------------------------------------------------------------

def _build_objective(model: Model, travels: dict, model_data: dict) -> None:
    """Define the objective function: minimize total travel distance.

    Args:
        model: DOCPLEX model instance.
        travels: Travel variable dictionary ``(k, i, j)``.
        model_data: Dictionary with ``distancia`` (time matrix) and ``data``.
    """
    distances = model_data["distancia"]
    city_data = model_data["data"]
    num_vehicles = model_data["necessary_vehicles"]

    model.minimize(
        model.sum(
            travels[k, i, j] * distances[i][j]
            for i in city_data.index
            for j in city_data.index
            for k in range(num_vehicles)
        )
    )


# ---------------------------------------------------------------------------
# Constraints
# ---------------------------------------------------------------------------

def _build_constraints(
    model: Model,
    travels: dict,
    service: dict,
    load: dict,
    model_data: dict,
) -> None:
    """Add all constraints to the VRPTW model.

    Implemented constraints:
        1. Total capacity per vehicle.
        2. Mandatory service for each client (demand).
        3. Mandatory visit: to serve load, the point must be visited.
        4. Departure from the depot.
        5. Flow conservation at each node.
        6. Single pass: each vehicle visits each node at most once.
        7. Time windows (Big-M formulation).
        8. Diagonal removal (forbid self-loops).

    Args:
        model: DOCPLEX model instance.
        travels: Travel variables ``(k, i, j)``.
        service: Service time variables ``(k, i)``.
        load: Load variables ``(k, i)``.
        model_data: Dictionary with instance data.
    """
    capacity = model_data["capacity"]
    depot = model_data["depot"]
    city_data = model_data["data"]
    shift = model_data["turno"]
    num_spots = model_data["num_spots"]
    num_vehicles = model_data["necessary_vehicles"]
    distances = model_data["distancia"]
    big_m = model_data["big_m"]

    # 1. Total capacity per vehicle
    for k in range(num_vehicles):
        model.add_constraint(
            model.sum(load[k, i] for i in city_data.index) <= capacity,
            f"Capacity_Vehicle_{k}",
        )

    # 2. Mandatory service for each client
    for i in city_data.index[1:]:
        model.add_constraint(
            model.sum(load[k, i] for k in range(num_vehicles))
            == city_data.loc[i, f"{shift}_DEMAND"],
            f"Demand_Client_{i}",
        )

    # 3. Mandatory visit (to serve load, the point must be visited)
    for k in range(num_vehicles):
        for i in city_data.index:
            model.add_constraint(
                model.sum(capacity * travels[k, i, j] for j in city_data.index)
                - load[k, i] >= 0,
                f"Visit_Required_{i}_Vehicle_{k}",
            )

    # 4. Departure from the depot
    for k in range(num_vehicles):
        model.add_constraint(
            model.sum(
                num_spots ** 2 * travels[k, depot, j]
                for j in city_data.index[1:]
            )
            - model.sum(
                travels[k, i, j]
                for i in city_data.index[1:]
                for j in city_data.index[1:]
            ) >= 0,
            f"Depot_Exit_Vehicle_{k}",
        )

    # 5. Flow conservation
    for k in range(num_vehicles):
        for i in city_data.index:
            model.add_constraint(
                model.sum(
                    travels[k, i, j] - travels[k, j, i]
                    for j in city_data.index
                ) == 0,
                f"Flow_Conservation_Vehicle_{k}_Node_{i}",
            )

    # 6. Single pass per node
    for k in range(num_vehicles):
        for i in city_data.index:
            model.add_constraint(
                model.sum(travels[k, i, j] for j in city_data.index) <= 1,
                f"Single_Pass_Vehicle_{k}_Node_{i}",
            )

    # 7. Time windows (Big-M)
    for k in range(num_vehicles):
        for idx_i in range(len(city_data)):
            origin = city_data.index[idx_i]
            for idx_j in range(idx_i + 1, len(city_data)):
                destination = city_data.index[idx_j]
                model.add_constraint(
                    service[k, origin]
                    + distances[origin][destination]
                    - big_m * (1 - travels[k, origin, destination])
                    <= service[k, destination],
                    f"Time_Window_{k}_{origin}_{destination}",
                )

    # 8. Diagonal removal (forbid i->i)
    model.add_constraint(
        model.sum(
            travels[k, i, i]
            for k in range(num_vehicles)
            for i in city_data.index
        ) == 0,
        "No_Self_Loops",
    )


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
) -> str:
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

    Returns:
        Formatted string describing the route, or empty string if the route is empty.
    """
    if not routes[vehicle]:
        return ""

    first_node = next(iter(routes[vehicle]))
    current = routes[vehicle].pop(first_node)

    route_str = f"Vehicle {vehicle} Start [{earliest_departure + 1800 * iteration}s] |Route: 0"
    total_time = distance_matrix[first_node][current]

    while current != first_node:
        next_node = routes[vehicle].pop(current)
        total_time += distance_matrix[current][next_node]
        route_str += f" -> {current}"
        current = next_node

    route_str += " -> 0"
    route_str += f"| End [{earliest_departure + total_time + 1800 * iteration}s]\n"
    return route_str


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
    travels, service, load = _build_variables(model, model_data)
    _build_objective(model, travels, model_data)
    _build_constraints(model, travels, service, load, model_data)

    return model, travels
