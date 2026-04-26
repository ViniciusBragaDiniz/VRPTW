"""Flow conservation constraint."""

from docplex.mp.model import Model


def add_flow_conservation(
    model: Model, *, travels: dict, model_data: dict, **kwargs,
) -> None:
    """Ensure each vehicle that enters a node also leaves it."""
    city_data = model_data["data"]
    num_vehicles = model_data["necessary_vehicles"]

    for k in range(num_vehicles):
        for i in city_data.index:
            outgoing = [j for j in city_data.index if (k, i, j) in travels]
            incoming = [j for j in city_data.index if (k, j, i) in travels]
            model.add_constraint(
                model.sum(travels[k, i, j] for j in outgoing)
                - model.sum(travels[k, j, i] for j in incoming)
                == 0,
                f"Flow_Conservation_Vehicle_{k}_Node_{i}",
            )
