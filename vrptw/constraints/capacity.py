"""Vehicle capacity constraint."""

from docplex.mp.model import Model


def add_capacity_constraints(
    model: Model, *, load: dict, model_data: dict, **kwargs,
) -> None:
    """Limit the total load served by each vehicle to its capacity."""
    capacity = model_data["capacity"]
    city_data = model_data["data"]
    num_vehicles = model_data["necessary_vehicles"]

    for k in range(num_vehicles):
        model.add_constraint(
            model.sum(load[k, i] for i in city_data.index) <= capacity,
            f"Capacity_Vehicle_{k}",
        )
