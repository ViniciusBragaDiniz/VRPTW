#!/usr/bin/env python3
"""Etapa 2 — Geração de pontos de parada via K-means.

Aplica clusterização nos dados geográficos dos alunos para determinar
os pontos de parada ótimos e calcula a demanda por turno/dia.

Uso:
    $ python 02_generate_points.py [--filter FILTER] [--shift SHIFT]

Exemplos:
    $ python 02_generate_points.py                          # todos, SAIDA
    $ python 02_generate_points.py --filter tec --shift ENTRADA
"""

import argparse
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

from vrptw.config import DATA_PROCESSED_DIR
from data.point_generation import generate_bus_stops


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

    df = generate_bus_stops(student_filter=args.filter, shift=args.shift)

    output_path = DATA_PROCESSED_DIR / f"pontos_de_onibus_{args.filter}_{args.shift}.csv"
    df.to_csv(output_path, index=False)
    logging.getLogger(__name__).info("Salvo em: %s (%d pontos)", output_path, len(df))


if __name__ == "__main__":
    main()
