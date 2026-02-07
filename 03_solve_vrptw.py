#!/usr/bin/env python3
"""Etapa 3 — Resolução do modelo VRPTW.

Constrói e resolve o modelo de programação linear inteira mista para cada
cenário (dia × turno × município), com eliminação iterativa de subciclos.

Uso:
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
