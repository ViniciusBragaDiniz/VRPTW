#!/usr/bin/env python3
"""VRPTW full pipeline orchestrator.

Executes the 4 pipeline steps in the correct sequence:

    1. Preprocessing — student data geocoding
    2. Point generation — K-means clustering per municipality
    3. Solving — MILP model with subtour elimination
    4. Post-processing — vehicle count minimization

Each step can be enabled or disabled via command-line arguments, allowing
re-execution of only the necessary steps.

Usage:
    # Run the full pipeline
    $ python run_pipeline.py

    # Skip preprocessing (data already geocoded)
    $ python run_pipeline.py --skip-preprocess

    # Run only solving and post-processing
    $ python run_pipeline.py --skip-preprocess --skip-points

    # Run only post-processing
    $ python run_pipeline.py --only-postprocess
"""

import argparse
import logging
import sys
import time

import pandas as pd

from src.globals.config import DATA_PROCESSED_DIR, INSTANCE_TYPES, ROUTE_TYPES

logger = logging.getLogger(__name__)


def _step_banner(step_number: int, title: str) -> None:
    """Print a visual banner delimiting the start of a step."""
    separator = "=" * 60
    logger.info(separator)
    logger.info("  STEP %d — %s", step_number, title)
    logger.info(separator)


def step_1_preprocess() -> None:
    """Step 1: student data preprocessing and geocoding.

    Calls the pure preprocessing function and persists the results
    to ``data/processed/``.
    """
    _step_banner(1, "Data preprocessing")
    from src.pipeline.preprocessing import preprocess_student_data

    results = preprocess_student_data()

    DATA_PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    for name, df in results.items():
        output_path = DATA_PROCESSED_DIR / "info" / f"{name}.csv"
        df.to_csv(output_path, index=False)
        logger.info("  -> %d records saved to %s", len(df), output_path)


def step_2_generate_points() -> None:
    """Step 2: bus stop point generation via K-means.

    Reads the student data processed in step 1 and generates points for
    each combination of instance and route type configured in
    ``config.py``. Persists results to ``data/processed/``.
    """
    _step_banner(2, "Bus stop point generation")
    from src.pipeline.point_generation import generate_bus_stops

    students_path = DATA_PROCESSED_DIR / "info" / "info_students.csv"
    if not students_path.exists():
        raise FileNotFoundError(
            f"Student file not found: {students_path}. "
            "Run step 1 (preprocessing) first."
        )
    df_students = pd.read_csv(students_path)

    DATA_PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    for route_type in ROUTE_TYPES:
        for instance in INSTANCE_TYPES:
            logger.info("Generating points: instance=%s, route=%s", instance, route_type)
            df = generate_bus_stops(
                df_students, student_filter=instance, shift=route_type,
            )
            output_path = DATA_PROCESSED_DIR / "bus_stops" / f"{instance}_{route_type}.csv"
            df.to_csv(output_path, index=False)
            logger.info("  -> %d points saved to %s", len(df), output_path)


def step_3_solve(*, relax: bool = False) -> None:
    """Step 3: VRPTW model solving (MIP or LP relaxation)."""
    mode = "LP relaxation (lower bounds)" if relax else "VRPTW model solving"
    _step_banner(3, mode)
    from src.models.solver.solution import solve_all_instances
    solve_all_instances(relax=relax)


def step_4_postprocess() -> None:
    """Step 4: vehicle count minimization."""
    _step_banner(4, "Post-processing (vehicle minimization)")
    from src.pipeline.postprocessing import minimize_vehicles
    minimize_vehicles()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="VRPTW pipeline orchestrator.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python run_pipeline.py                    # full pipeline\n"
            "  python run_pipeline.py --skip-preprocess   # skip geocoding\n"
            "  python run_pipeline.py --only-postprocess  # step 4 only\n"
        ),
    )
    parser.add_argument(
        "--skip-preprocess", action="store_true",
        help="Skip step 1 (preprocessing/geocoding)",
    )
    parser.add_argument(
        "--skip-points", action="store_true",
        help="Skip step 2 (bus stop point generation)",
    )
    parser.add_argument(
        "--skip-solve", action="store_true",
        help="Skip step 3 (model solving)",
    )
    parser.add_argument(
        "--skip-postprocess", action="store_true",
        help="Skip step 4 (vehicle minimization)",
    )
    parser.add_argument(
        "--only-postprocess", action="store_true",
        help="Run only step 4 (shortcut for --skip-preprocess --skip-points --skip-solve)",
    )
    parser.add_argument(
        "--relax", action="store_true",
        help="Solve LP relaxation only (lower bounds, no integer routes). "
             "Implies --skip-postprocess.",
    )
    args = parser.parse_args()

    if args.only_postprocess:
        args.skip_preprocess = True
        args.skip_points = True
        args.skip_solve = True

    if args.relax:
        args.skip_postprocess = True

    # Define steps to execute
    steps = []
    if not args.skip_preprocess:
        steps.append(("1. Preprocessing", step_1_preprocess))
    if not args.skip_points:
        steps.append(("2. Point generation", step_2_generate_points))
    if not args.skip_solve:
        solve_fn = lambda: step_3_solve(relax=args.relax)
        label = "3. LP relaxation" if args.relax else "3. VRPTW solving"
        steps.append((label, solve_fn))
    if not args.skip_postprocess:
        steps.append(("4. Post-processing", step_4_postprocess))

    if not steps:
        logger.warning("All steps were skipped. Nothing to execute.")
        return

    logger.info("VRPTW pipeline started — %d step(s) to execute", len(steps))
    pipeline_start = time.time()

    for name, func in steps:
        step_start = time.time()
        try:
            func()
            elapsed = time.time() - step_start
            logger.info("%s completed in %.1fs", name, elapsed)
        except Exception:
            elapsed = time.time() - step_start
            logger.exception("%s failed after %.1fs", name, elapsed)
            sys.exit(1)

    total = time.time() - pipeline_start
    logger.info("Pipeline complete in %.1fs", total)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    main()
