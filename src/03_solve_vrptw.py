#!/usr/bin/env python3
"""Step 3 — VRPTW model solving.

Builds and solves the mixed-integer linear programming model for each
scenario (day x shift x municipality), with iterative subtour elimination.

Usage:
    $ python 03_solve_vrptw.py
"""

import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

from vrptw.solver import solve_all_instances


def main() -> None:
    solve_all_instances()


if __name__ == "__main__":
    main()
