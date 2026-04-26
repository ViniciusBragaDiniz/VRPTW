"""Pluggable variable registry for the VRPTW model.

Each variable group lives in its own module.  ``EXECUTION_ORDER`` defines the
sequence in which variable groups are created.  The model builder iterates
this list, passing ``model_data`` and the variables created so far via
keyword arguments so that later variable groups can depend on earlier ones
if needed.

Each function must return a ``dict[str, dict]`` mapping one or more variable
names (e.g. ``"travels"``) to their variable dictionaries.  The builder
merges all returned dicts into a single namespace that is then forwarded
to the constraint layer.

To add a new variable group:
    1. Create ``vrptw/variables/my_vars.py`` with a function whose signature
       is ``def create_my_vars(model, *, model_data, **kwargs) -> dict[str, dict]``.
    2. Import it here and append it to ``EXECUTION_ORDER``.
"""

from typing import Callable

from .load import create_load
from .service import create_service
from .travels import create_travels

VariableFn = Callable[..., dict[str, dict]]

EXECUTION_ORDER: list[VariableFn] = [
    create_travels,
    create_service,
    create_load,
]
