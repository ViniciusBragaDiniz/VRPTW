#!/usr/bin/env python3
"""Step 2 — Bus stop point generation via K-means.

Reads the processed student data (``data/processed/info_students.csv``),
applies clustering on geographic data to determine optimal bus stop
locations, and saves the result to ``data/processed/``.

Usage:
    $ python 02_generate_points.py [--filter FILTER] [--shift SHIFT]

Examples:
    $ python 02_generate_points.py                          # all, EXIT
    $ python 02_generate_points.py --filter tec --shift ENTRY
"""

import argparse
import logging
import sys

import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

from vrptw.config import DATA_PROCESSED_DIR
from data.point_generation import generate_bus_stops

logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate bus stop points via K-means.",
    )
    parser.add_argument(
        "--filter", default="full",
        help="Student filter: 'full', 'tec', or 'grad' (default: full)",
    )
    parser.add_argument(
        "--shift", default="EXIT",
        help="Shift: 'ENTRY' or 'EXIT' (default: EXIT)",
    )
    args = parser.parse_args()

    students_path = DATA_PROCESSED_DIR / "info_students.csv"
    if not students_path.exists():
        logger.error(
            "Student file not found: %s. "
            "Run step 1 (preprocessing) first.",
            students_path,
        )
        sys.exit(1)
    df_students = pd.read_csv(students_path)

    df = generate_bus_stops(df_students, student_filter=args.filter, shift=args.shift)

    DATA_PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    output_path = DATA_PROCESSED_DIR / f"bus_stops_{args.filter}_{args.shift}.csv"
    df.to_csv(output_path, index=False)
    logger.info("Saved to: %s (%d points)", output_path, len(df))


if __name__ == "__main__":
    main()
