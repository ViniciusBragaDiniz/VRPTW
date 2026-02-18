#!/usr/bin/env python3
"""Step 4 — Post-processing: vehicle count minimization.

Consolidates routes from multiple vehicles when possible, reducing
the total number of vehicles needed while respecting the maximum
work time.

Usage:
    $ python 04_resequence_trips.py
"""

import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

from vrptw.postprocessing import minimize_vehicles


def main() -> None:
    minimize_vehicles()


if __name__ == "__main__":
    main()
