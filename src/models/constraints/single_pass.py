"""Single-pass constraint (each vehicle visits each node at most once)."""

from docplex.mp.model import Model


def add_single_pass_constraints(
    model: Model, *, travels: dict, model_data: dict, **kwargs,
) -> None:
    """Each vehicle visits each node at most once."""
    city_data = model_data["data"]
    num_vehicles = model_data["necessary_vehicles"]

    for k in range(num_vehicles):
        for i in city_data.index:
            outgoing = [j for j in city_data.index if (k, i, j) in travels]
            model.add_constraint(
                model.sum(travels[k, i, j] for j in outgoing) <= 1,
                f"Single_Pass_Vehicle_{k}_Node_{i}",
            )
