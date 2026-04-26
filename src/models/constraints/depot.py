"""Depot departure constraint."""

from docplex.mp.model import Model


def add_depot_constraints(
    model: Model, *, travels: dict, model_data: dict, **kwargs,
) -> None:
    """Force vehicles to depart from the depot before visiting clients."""
    depot = model_data["depot"]
    city_data = model_data["data"]
    num_spots = model_data["num_spots"]
    num_vehicles = model_data["necessary_vehicles"]

    for k in range(num_vehicles):
        model.add_constraint(
            model.sum(
                num_spots ** 2 * travels[k, depot, j]
                for j in city_data.index[1:]
                if (k, depot, j) in travels
            )
            - model.sum(
                travels[k, i, j]
                for i in city_data.index[1:]
                for j in city_data.index[1:]
                if (k, i, j) in travels
            ) >= 0,
            f"Depot_Exit_Vehicle_{k}",
        )
