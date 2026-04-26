"""No-self-loop constraint (safety guard)."""

from docplex.mp.model import Model


def add_no_self_loops(
    model: Model, *, travels: dict, model_data: dict, **kwargs,
) -> None:
    """Forbid any vehicle from traveling from a node to itself.

    With sparse variable creation (i != j), this constraint is
    automatically satisfied and becomes a no-op, but is kept for
    safety in case the variable set is changed.
    """
    city_data = model_data["data"]
    num_vehicles = model_data["necessary_vehicles"]

    self_loops = [
        travels[k, i, i]
        for k in range(num_vehicles)
        for i in city_data.index
        if (k, i, i) in travels
    ]
    if self_loops:
        model.add_constraint(model.sum(self_loops) == 0, "No_Self_Loops")
