"""Travel (arc) decision variables: x[k, i, j]."""

from docplex.mp.model import Model


def create_travels(
    model: Model, *, model_data: dict, **kwargs,
) -> dict[str, dict]:
    """Create binary variables indicating whether vehicle *k* uses arc (i → j).

    Self-loops (i == j) are excluded to reduce model size
    (sparse representation).

    Returns:
        ``{"travels": {(k, i, j): Var, ...}}``
    """
    num_vehicles = model_data["necessary_vehicles"]
    city_data = model_data["data"]

    travels = {
        (k, i, j): model.binary_var(name=f"travels_{k}_{i}_{j}")
        for k in range(num_vehicles)
        for i in city_data.index
        for j in city_data.index
        if i != j
    }

    return {"travels": travels}
