#!/usr/bin/env python3
"""Orquestrador do pipeline completo do VRPTW.

Executa as 4 etapas do pipeline na sequência correta:

    1. Pré-processamento — geocodificação dos dados de alunos
    2. Geração de pontos — clusterização K-means por município
    3. Resolução — modelo PLIM com eliminação de subciclos
    4. Pós-processamento — minimização do número de veículos

Cada etapa pode ser habilitada ou desabilitada via argumentos de linha de
comando, permitindo reexecutar apenas as etapas necessárias.

Uso:
    # Executar o pipeline completo
    $ python run_pipeline.py

    # Pular o pré-processamento (dados já geocodificados)
    $ python run_pipeline.py --skip-preprocess

    # Executar apenas a resolução e o pós-processamento
    $ python run_pipeline.py --skip-preprocess --skip-points

    # Executar apenas o pós-processamento
    $ python run_pipeline.py --only-postprocess
"""

import argparse
import logging
import sys
import time

from vrptw.config import DATA_PROCESSED_DIR, INSTANCE_TYPES, ROUTE_TYPES

logger = logging.getLogger(__name__)


def _step_banner(step_number: int, title: str) -> None:
    """Imprime um banner visual delimitando o início de uma etapa."""
    separator = "=" * 60
    logger.info(separator)
    logger.info("  ETAPA %d — %s", step_number, title)
    logger.info(separator)


def step_1_preprocess() -> None:
    """Etapa 1: pré-processamento e geocodificação dos dados de alunos."""
    _step_banner(1, "Pré-processamento de dados")
    from data.preprocessing import preprocess_student_data
    preprocess_student_data()


def step_2_generate_points() -> None:
    """Etapa 2: geração de pontos de parada via K-means.

    Gera pontos para cada combinação de instância e tipo de rota
    configurada em ``config.py``.
    """
    _step_banner(2, "Geração de pontos de parada")
    from data.point_generation import generate_bus_stops

    for route_type in ROUTE_TYPES:
        for instance in INSTANCE_TYPES:
            logger.info("Gerando pontos: instância=%s, rota=%s", instance, route_type)
            df = generate_bus_stops(student_filter=instance, shift=route_type)
            output_path = DATA_PROCESSED_DIR / f"pontos_de_onibus_{instance}_{route_type}.csv"
            df.to_csv(output_path, index=False)
            logger.info("  -> %d pontos salvos em %s", len(df), output_path)


def step_3_solve() -> None:
    """Etapa 3: resolução do modelo VRPTW."""
    _step_banner(3, "Resolução do modelo VRPTW")
    from vrptw.solver import solve_all_instances
    solve_all_instances()


def step_4_postprocess() -> None:
    """Etapa 4: minimização do número de veículos."""
    _step_banner(4, "Pós-processamento (minimização de veículos)")
    from vrptw.postprocessing import minimize_vehicles
    minimize_vehicles()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Orquestrador do pipeline VRPTW.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Exemplos:\n"
            "  python run_pipeline.py                    # pipeline completo\n"
            "  python run_pipeline.py --skip-preprocess   # sem geocodificação\n"
            "  python run_pipeline.py --only-postprocess  # só etapa 4\n"
        ),
    )
    parser.add_argument(
        "--skip-preprocess", action="store_true",
        help="Pular a etapa 1 (pré-processamento/geocodificação)",
    )
    parser.add_argument(
        "--skip-points", action="store_true",
        help="Pular a etapa 2 (geração de pontos de parada)",
    )
    parser.add_argument(
        "--skip-solve", action="store_true",
        help="Pular a etapa 3 (resolução do modelo)",
    )
    parser.add_argument(
        "--skip-postprocess", action="store_true",
        help="Pular a etapa 4 (minimização de veículos)",
    )
    parser.add_argument(
        "--only-postprocess", action="store_true",
        help="Executar apenas a etapa 4 (atalho para --skip-preprocess --skip-points --skip-solve)",
    )
    args = parser.parse_args()

    if args.only_postprocess:
        args.skip_preprocess = True
        args.skip_points = True
        args.skip_solve = True

    # Definir as etapas a executar
    steps = []
    if not args.skip_preprocess:
        steps.append(("1. Pré-processamento", step_1_preprocess))
    if not args.skip_points:
        steps.append(("2. Geração de pontos", step_2_generate_points))
    if not args.skip_solve:
        steps.append(("3. Resolução VRPTW", step_3_solve))
    if not args.skip_postprocess:
        steps.append(("4. Pós-processamento", step_4_postprocess))

    if not steps:
        logger.warning("Todas as etapas foram puladas. Nada a executar.")
        return

    logger.info("Pipeline VRPTW iniciado — %d etapa(s) a executar", len(steps))
    pipeline_start = time.time()

    for name, func in steps:
        step_start = time.time()
        try:
            func()
            elapsed = time.time() - step_start
            logger.info("%s concluída em %.1fs", name, elapsed)
        except Exception:
            elapsed = time.time() - step_start
            logger.exception("%s falhou após %.1fs", name, elapsed)
            sys.exit(1)

    total = time.time() - pipeline_start
    logger.info("Pipeline completo em %.1fs", total)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    main()
