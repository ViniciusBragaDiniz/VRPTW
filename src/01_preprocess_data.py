#!/usr/bin/env python3
"""Step 1 — Student data preprocessing.

Loads raw data, enriches addresses via ViaCEP, geocodes via Google Maps,
and saves the processed results to ``data/processed/``.

Usage:
    $ python 01_preprocess_data.py
"""

import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

from src.pipeline.preprocessing import preprocess_student_data
from src.globals.config import DATA_PROCESSED_DIR

logger = logging.getLogger(__name__)


def main() -> None:
    results = preprocess_student_data()

    info_dir = DATA_PROCESSED_DIR / "info"
    info_dir.mkdir(parents=True, exist_ok=True)
    for name, df in results.items():
        output_path = info_dir / f"{name}.csv"
        df.to_csv(output_path, index=False)
        logger.info("Saved to: %s (%d records)", output_path, len(df))


if __name__ == "__main__":
    main()
