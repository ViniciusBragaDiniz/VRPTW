"""Pluggable constraint registry for the VRPTW model.

Each constraint lives in its own module.  ``EXECUTION_ORDER`` defines the
sequence in which constraints are added to the model.  The model builder
iterates this list, passing a shared keyword-argument dictionary so every
function can pick exactly the variables it needs.

To add a new constraint:
    1. Create ``vrptw/constraints/my_constraint.py`` with a function whose
       signature is ``def add_my_constraint(model, *, <needed vars>, **kwargs)``.
    2. Import it here and append it to ``EXECUTION_ORDER``.
"""

from typing import Callable

from docplex.mp.model import Model

from .capacity import add_capacity_constraints
from .demand import add_demand_constraints
from .depot import add_depot_constraints
from .flow_conservation import add_flow_conservation
from .no_self_loops import add_no_self_loops
from .single_pass import add_single_pass_constraints
from .time_windows import add_time_window_constraints
from .visit_required import add_visit_required_constraints

ConstraintFn = Callable[..., None]

EXECUTION_ORDER: list[ConstraintFn] = [
    add_capacity_constraints,
    add_demand_constraints,
    add_visit_required_constraints,
    add_depot_constraints,
    add_flow_conservation,
    add_single_pass_constraints,
    add_time_window_constraints,
    add_no_self_loops,
]
