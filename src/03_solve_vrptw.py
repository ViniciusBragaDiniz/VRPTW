#!/usr/bin/env python3
"""Step 3 — VRPTW model solving.

Builds and solves the mixed-integer linear programming model for each
scenario (day x shift x municipality), with iterative subtour elimination.

Usage:
    $ python 03_solve_vrptw.py
    $ python 03_solve_vrptw.py --relax   # LP relaxation (lower bounds only)
"""

import argparse
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

from src.models.solver.solution import solve_all_instances


def main() -> None:
    parser = argparse.ArgumentParser(description="Step 3 — VRPTW model solving")
    parser.add_argument(
        "--relax", action="store_true",
        help="Solve LP relaxation only (lower bounds, no integer routes)",
    )
    args = parser.parse_args()
    solve_all_instances(relax=args.relax)


if __name__ == "__main__":
    main()
