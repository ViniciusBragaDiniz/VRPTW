#!/usr/bin/env python3
"""Etapa 1 — Pré-processamento dos dados de alunos.

Carrega os dados brutos, enriquece endereços via ViaCEP, georreferencia
via Google Maps e salva os resultados processados em ``data/processed/``.

Uso:
    $ python 01_preprocess_data.py
"""

import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

from data.preprocessing import preprocess_student_data
from vrptw.config import DATA_PROCESSED_DIR

logger = logging.getLogger(__name__)


def main() -> None:
    results = preprocess_student_data()

    DATA_PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    for name, df in results.items():
        output_path = DATA_PROCESSED_DIR / f"{name}.csv"
        df.to_csv(output_path, index=False)
        logger.info("Salvo em: %s (%d registros)", output_path, len(df))


if __name__ == "__main__":
    main()
