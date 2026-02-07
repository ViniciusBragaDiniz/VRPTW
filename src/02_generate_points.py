#!/usr/bin/env python3
"""Etapa 2 — Geração de pontos de parada via K-means.

Lê os dados de alunos processados (``data/processed/info_alunos.csv``),
aplica clusterização nos dados geográficos para determinar os pontos de
parada ótimos e salva o resultado em ``data/processed/``.

Uso:
    $ python 02_generate_points.py [--filter FILTER] [--shift SHIFT]

Exemplos:
    $ python 02_generate_points.py                          # todos, SAIDA
    $ python 02_generate_points.py --filter tec --shift ENTRADA
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
        description="Gera pontos de parada de ônibus via K-means.",
    )
    parser.add_argument(
        "--filter", default="full",
        help="Filtro de alunos: 'full', 'tec' ou 'grad' (padrão: full)",
    )
    parser.add_argument(
        "--shift", default="SAIDA",
        help="Turno: 'ENTRADA' ou 'SAIDA' (padrão: SAIDA)",
    )
    args = parser.parse_args()

    students_path = DATA_PROCESSED_DIR / "info_alunos.csv"
    if not students_path.exists():
        logger.error(
            "Arquivo de alunos não encontrado: %s. "
            "Execute a etapa 1 (pré-processamento) antes.",
            students_path,
        )
        sys.exit(1)
    df_students = pd.read_csv(students_path)

    df = generate_bus_stops(df_students, student_filter=args.filter, shift=args.shift)

    DATA_PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    output_path = DATA_PROCESSED_DIR / f"pontos_de_onibus_{args.filter}_{args.shift}.csv"
    df.to_csv(output_path, index=False)
    logger.info("Salvo em: %s (%d pontos)", output_path, len(df))


if __name__ == "__main__":
    main()
