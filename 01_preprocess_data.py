#!/usr/bin/env python3
"""Etapa 1 — Pré-processamento dos dados de alunos.

Carrega os dados brutos, enriquece endereços via ViaCEP, georreferencia
via Google Maps e salva os resultados processados.

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

from vrptw.preprocessing import preprocess_student_data


def main() -> None:
    preprocess_student_data()


if __name__ == "__main__":
    main()
