"""Big-M time-window constraint."""

from docplex.mp.model import Model


def add_time_window_constraints(
    model: Model, *, travels: dict, service: dict, model_data: dict, **kwargs,
) -> None:
    """Big-M time-window constraints ensuring feasible arrival times."""
    city_data = model_data["data"]
    num_vehicles = model_data["necessary_vehicles"]
    distances = model_data["distance"]
    big_m = model_data["big_m"]

    for k in range(num_vehicles):
        for origin in city_data.index:
            for destination in city_data.index:
                if origin == destination or (k, origin, destination) not in travels:
                    continue
                model.add_constraint(
                    service[k, origin]
                    + distances[origin][destination]
                    - big_m * (1 - travels[k, origin, destination])
                    <= service[k, destination],
                    f"Time_Window_{k}_{origin}_{destination}",
                )
