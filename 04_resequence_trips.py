#!/usr/bin/env python3
"""Etapa 4 — Pós-processamento: minimização do número de veículos.

Consolida rotas de múltiplos veículos quando possível, reduzindo o
número total de veículos necessários respeitando a jornada máxima.

Uso:
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
