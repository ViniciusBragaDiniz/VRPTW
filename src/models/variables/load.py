"""Vehicle load decision variables: q[k, i]."""

from docplex.mp.model import Model


def create_load(
    model: Model, *, model_data: dict, **kwargs,
) -> dict[str, dict]:
    """Create integer variables for the load served at each node.

    Each variable is bounded by ``[0, capacity]``.

    Returns:
        ``{"load": {(k, i): Var, ...}}``
    """
    num_vehicles = model_data["necessary_vehicles"]
    capacity = model_data["capacity"]
    city_data = model_data["data"]

    load = {
        (k, i): model.integer_var(
            lb=0, ub=capacity, name=f"load_{k}_{i}",
        )
        for k in range(num_vehicles)
        for i in city_data.index
    }

    return {"load": load}
