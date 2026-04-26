"""Client demand satisfaction constraint."""

from docplex.mp.model import Model


def add_demand_constraints(
    model: Model, *, load: dict, model_data: dict, **kwargs,
) -> None:
    """Ensure every client's demand is fully served across all vehicles."""
    city_data = model_data["data"]
    shift = model_data["SHIFT"]
    num_vehicles = model_data["necessary_vehicles"]

    for i in city_data.index[1:]:
        model.add_constraint(
            model.sum(load[k, i] for k in range(num_vehicles))
            == city_data.loc[i, f"{shift}_DEMAND"],
            f"Demand_Client_{i}",
        )
