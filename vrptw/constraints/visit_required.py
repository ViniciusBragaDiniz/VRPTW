"""Visit-required linking constraint (load <-> travel)."""

from docplex.mp.model import Model


def add_visit_required_constraints(
    model: Model, *, travels: dict, load: dict, model_data: dict, **kwargs,
) -> None:
    """Link load variables to travel variables: a node must be visited to be served."""
    capacity = model_data["capacity"]
    city_data = model_data["data"]
    num_vehicles = model_data["necessary_vehicles"]

    for k in range(num_vehicles):
        for i in city_data.index:
            outgoing = [j for j in city_data.index if (k, i, j) in travels]
            model.add_constraint(
                model.sum(capacity * travels[k, i, j] for j in outgoing)
                - load[k, i] >= 0,
                f"Visit_Required_{i}_Vehicle_{k}",
            )
