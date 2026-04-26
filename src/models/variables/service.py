"""Service-start-time decision variables: s[k, i]."""

from docplex.mp.model import Model


def create_service(
    model: Model, *, model_data: dict, **kwargs,
) -> dict[str, dict]:
    """Create continuous variables for the service start time at each node.

    Bounds are derived from the node's time window
    (``earliest_departure`` / ``latest_arrival``).

    Returns:
        ``{"service": {(k, i): Var, ...}}``
    """
    num_vehicles = model_data["necessary_vehicles"]
    city_data = model_data["data"]

    service = {
        (k, i): model.continuous_var(
            lb=city_data["earliest_departure"][i],
            ub=city_data["latest_arrival"][i],
            name=f"service_start_{k}_{i}",
        )
        for k in range(num_vehicles)
        for i in city_data.index
    }

    return {"service": service}
