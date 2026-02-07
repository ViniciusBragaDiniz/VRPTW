"""Resolução do modelo VRPTW com eliminação de subciclos via planos de corte.

Este módulo orquestra o processo de resolução do VRPTW:

1. Carrega (ou gera) os pontos de parada para cada instância.
2. Para cada cenário (dia × turno × município), constrói e resolve o modelo
   CPLEX de programação linear inteira mista.
3. Implementa a eliminação de subciclos iterativa:
   - Resolve o modelo.
   - Se a solução contém subciclos, adiciona cortes e resolve novamente.
   - Repete até obter uma solução sem subciclos ou atingir o limite de tempo.
4. Salva os resultados em arquivos CSV e TXT.

Exemplo de uso:
    >>> from vrptw.solver import solve_all_instances
    >>> solve_all_instances()
"""

import gc
import logging
import math
import re
import time
from io import TextIOWrapper

import pandas as pd
from docplex.mp.model import Model

from .config import (
    DATA_PROCESSED_DIR,
    DATA_RAW_DIR,
    DEPOT_INDEX,
    DEPOT_LAT,
    DEPOT_LON,
    EARLIEST_DEPARTURE,
    INSTANCE_TYPES,
    LATEST_ARRIVAL,
    OUTPUT_CSV_DIR,
    OUTPUT_TEXT_DIR,
    ROUTE_TYPES,
    SHIFTS,
    TIME_LIMIT,
    TIME_SLOT_DURATION,
    VEHICLE_CAPACITY,
    WEEKDAYS,
)
from vrptw.model_builder import add_subtour_cuts, build_model, format_route_string
from data.point_generation import generate_bus_stops
from vrptw.utils import build_routes, calculate_distances

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Funções auxiliares de preparação de dados por cenário
# ---------------------------------------------------------------------------

def _build_depot_row(day: str, iteration: int = 0) -> dict:
    """Cria o registro do depósito (CEFET) para inserção no DataFrame.

    Args:
        day: Dia da semana abreviado.
        iteration: Iteração temporal corrente.

    Returns:
        Dicionário com os campos do depósito.
    """
    return {
        "lat": [DEPOT_LAT],
        "lon": [DEPOT_LON],
        "demanda_manha": [0],
        "demanda_tarde": [0],
        "demanda_noite": [0],
        "tempo_preparo": EARLIEST_DEPARTURE + TIME_SLOT_DURATION * iteration,
        "tempo_entrega": LATEST_ARRIVAL,
        "cd_municipio": "CEFET",
        "dia": day,
        "centroid_id": 0,
        "iteracao": iteration,
    }


def _prepare_iteration_data(
    day_data: pd.DataFrame,
    shift: str,
    day: str,
    municipality: str,
    iteration: int,
) -> pd.DataFrame | None:
    """Prepara o DataFrame para uma iteração específica de resolução.

    Filtra os dados por município e turno, adiciona o nó-depósito e
    configura os índices.

    Args:
        day_data: DataFrame com os dados do dia corrente.
        shift: Turno (``'manha'``, ``'tarde'``, ``'noite'``, ``'fim'``).
        day: Dia da semana abreviado.
        municipality: Nome do município.
        iteration: Iteração temporal.

    Returns:
        DataFrame indexado por ``centroid_id`` pronto para o solver, ou
        ``None`` se não houver demanda.
    """
    demand_col = f"demanda_{shift}"

    mun_data = day_data[day_data["cd_municipio"] == municipality].copy()
    mun_data = mun_data[mun_data[demand_col] > 0].reset_index(drop=True)

    if mun_data.empty:
        return None

    # Atribuir centroid_id (deslocado em 1 para reservar 0 ao depósito)
    centroids = mun_data.drop_duplicates(subset=["lat", "lon"])[["lat", "lon"]]
    centroids = centroids.reset_index(names="centroid_id")
    mun_data = mun_data.merge(centroids, on=["lat", "lon"], how="left")
    mun_data["centroid_id"] += 1

    # Inserir depósito como nó 0
    depot_row = _build_depot_row(day, iteration)
    iter_data = pd.concat(
        [pd.DataFrame.from_dict(depot_row), mun_data], ignore_index=True,
    )
    iter_data = iter_data[iter_data["iteracao"] == iteration]
    iter_data = iter_data.set_index("centroid_id").sort_index()

    if iter_data.empty:
        return None

    return iter_data


# ---------------------------------------------------------------------------
# Loop de resolução com eliminação de subciclos
# ---------------------------------------------------------------------------

def _solve_with_subtour_elimination(
    model: Model,
    travels: dict,
    num_vehicles: int,
    time_limit: float,
) -> tuple[dict | None, float, bool]:
    """Executa o loop de resolução com eliminação iterativa de subciclos.

    Args:
        model: Modelo CPLEX construído.
        travels: Dicionário de variáveis de viagem.
        num_vehicles: Número de veículos no modelo.
        time_limit: Limite de tempo total em segundos.

    Returns:
        Tupla ``(routes, elapsed_time, success)`` onde ``routes`` contém as
        rotas finais (ou ``None`` se o tempo expirou), ``elapsed_time`` é o
        tempo total de resolução e ``success`` indica se uma solução sem
        subciclos foi encontrada.
    """
    start = time.time()
    warm_start = None

    while True:
        if warm_start is not None:
            model.add_mip_start(warm_start)

        solution_obj = model.solve(log_output=False)
        if solution_obj is None:
            elapsed = time.time() - start
            logger.warning("Solver retornou None após %.1fs", elapsed)
            return None, elapsed, False

        solution = solution_obj.as_dict()
        elapsed = time.time() - start

        routes = build_routes(solution, num_vehicles)
        model.time_limit = max(time_limit - elapsed, 1)

        # Construir warm start e verificar subciclos
        warm_start = model.new_solution()
        subtour_found = False

        for k in range(num_vehicles):
            if not routes[k]:
                continue

            # Percorrer a rota como lista encadeada para warm start
            current = routes[k].pop(0)
            warm_start.add_var_value(travels[k, 0, current], 1)
            while current != 0:
                prev = current
                current = routes[k].pop(current)
                warm_start.add_var_value(travels[k, prev, current], 1)

            # Nós restantes indicam subciclos
            if routes[k]:
                subtour_found = True
                add_subtour_cuts(model, routes, travels, k)

        if not subtour_found:
            # Reconstruir rotas limpas para saída
            final_routes = build_routes(solution, num_vehicles)
            return final_routes, elapsed, True

        if elapsed > time_limit:
            logger.warning("Limite de tempo atingido (%.1fs)", elapsed)
            return None, elapsed, False


# ---------------------------------------------------------------------------
# Processamento de um cenário (município × iteração)
# ---------------------------------------------------------------------------

def _process_scenario(
    iter_data: pd.DataFrame,
    shift: str,
    municipality: str,
    iteration: int,
    output_file: TextIOWrapper,
) -> tuple[dict | None, list[dict]]:
    """Resolve o VRPTW para um cenário específico e escreve os resultados.

    Args:
        iter_data: DataFrame com dados da iteração (indexado por centroid_id).
        shift: Turno corrente.
        municipality: Nome do município.
        iteration: Iteração temporal.
        output_file: Arquivo de texto para escrita dos resultados.

    Returns:
        Tupla ``(summary_dict, detail_list)`` com o resumo e os detalhes
        da solução, ou ``(None, [])`` em caso de falha.
    """
    num_spots = len(iter_data)
    demand_col = f"demanda_{shift}"
    num_vehicles = math.ceil(iter_data[demand_col].sum() / VEHICLE_CAPACITY)

    if num_spots == 0:
        logger.info("Sem demanda nesta iteração")
        output_file.write("Sem demanda nesta iteração\n\n")
        return None, []

    output_file.write(
        f"Veículos Disponíveis {num_vehicles}, "
        f"Pontos de Ônibus com Demanda {num_spots}\n\n"
    )

    # Calcular matriz de distâncias
    distance_matrix, big_m = calculate_distances(
        iter_data, municipality, iteration, TIME_SLOT_DURATION,
    )

    # Construir modelo
    model = Model("vrptw")
    model.time_limit = TIME_LIMIT

    model_data = {
        "data": iter_data,
        "num_spots": num_spots,
        "necessary_vehicles": num_vehicles,
        "capacity": VEHICLE_CAPACITY,
        "iteracao": iteration,
        "fatia_tempo": TIME_SLOT_DURATION,
        "turno": shift,
        "distancia": distance_matrix,
        "big_m": big_m,
        "depot": DEPOT_INDEX,
    }

    model, travels = build_model(model, model_data)

    # Resolver com eliminação de subciclos
    routes, elapsed, success = _solve_with_subtour_elimination(
        model, travels, num_vehicles, TIME_LIMIT,
    )

    detail_list: list[dict] = []

    if success and routes is not None:
        output_file.write("Solução:\n")

        for k in range(num_vehicles):
            route_str = format_route_string(
                routes, travels, k,
                earliest_departure=EARLIEST_DEPARTURE,
                iteration=iteration,
                distance_matrix=distance_matrix,
            )
            if route_str:
                travel_time = float(
                    re.findall(r"\d+\.?\d*", route_str.split("|")[-1])[0]
                )
                detail_list.append({
                    "id_veiculo": k,
                    "num_pontos": len(routes.get(k, {})),
                    "tempo_viagem": travel_time,
                })
                output_file.write(route_str)
                logger.info(route_str.strip())
    else:
        output_file.write("Solução não encontrada no limite de tempo definido\n")

    summary = {
        "num_pontos": num_spots,
        "num_veiculos": num_vehicles,
        "tempo_exec": elapsed,
        "objective_value": model.objective_value if success else None,
    }

    output_file.write(f"Custo da Função Objetiva: {model.objective_value}\n")
    output_file.write(f"Tempo Total de Execução: {elapsed:.2f}s\n\n\n")
    logger.info("Objetivo: %s | Tempo: %.2fs", model.objective_value, elapsed)

    del model
    gc.collect()

    return summary, detail_list


# ---------------------------------------------------------------------------
# Pipeline principal
# ---------------------------------------------------------------------------

def solve_all_instances() -> None:
    """Executa a resolução do VRPTW para todas as instâncias configuradas.

    Itera sobre tipos de rota, instâncias, dias, turnos e municípios
    conforme definido em ``config.py``. Os resultados são salvos em
    arquivos CSV (resumo e detalhamento) e TXT (log textual das rotas).
    """
    # Garantir que os diretórios de saída existam
    OUTPUT_CSV_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_TEXT_DIR.mkdir(parents=True, exist_ok=True)

    # Carregar instâncias a pular
    skip_path = DATA_RAW_DIR / "pular_instancias.csv"
    skip_set: set[str] = set()
    if skip_path.exists():
        skip_df = pd.read_csv(skip_path, sep=";")
        skip_set = set(skip_df.iloc[:, 0].astype(str))

    for route_type in ROUTE_TYPES:
        # Carregar ou gerar pontos de parada
        instances: dict[str, pd.DataFrame] = {}
        for instance_name in INSTANCE_TYPES:
            csv_path = DATA_PROCESSED_DIR / f"pontos_de_onibus_{instance_name}_{route_type}.csv"
            try:
                instances[instance_name] = pd.read_csv(csv_path)
            except FileNotFoundError:
                logger.info(
                    "Arquivo não encontrado: %s. Gerando pontos...", csv_path,
                )
                instances[instance_name] = generate_bus_stops(instance_name)

        for instance_name, instance_data in instances.items():
            summaries: list[dict] = []
            details: list[dict] = []

            output_path = OUTPUT_TEXT_DIR / f"saida_cvrptw_{instance_name}_{route_type}.txt"

            with open(output_path, "w", encoding="utf-8") as output_file:
                for day in WEEKDAYS:
                    day_data = instance_data[instance_data["dia"] == day].copy()
                    day_data = day_data.reset_index(drop=True)
                    day_data["tempo_preparo"] = EARLIEST_DEPARTURE
                    day_data["tempo_entrega"] = LATEST_ARRIVAL
                    day_data["iteracao"] = 0

                    for shift in SHIFTS:
                        _write_shift_header(output_file, shift)

                        shift_data = day_data[
                            day_data[f"demanda_{shift}"] > 0
                        ].reset_index(drop=True)

                        if shift_data.empty:
                            continue

                        for municipality in shift_data["cd_municipio"].unique():
                            skip_key = f"{route_type},{instance_name},{day},{shift},{municipality}"
                            if skip_key in skip_set:
                                logger.info("Pulando instância: %s", skip_key)
                                continue

                            for iteration in shift_data["iteracao"].unique():
                                _write_iteration_header(
                                    output_file, iteration, municipality,
                                )
                                logger.info(
                                    "Resolvendo: %s | %s | %s | %s | iter=%d",
                                    day, shift, instance_name, municipality, iteration,
                                )

                                iter_data = _prepare_iteration_data(
                                    shift_data, shift, day, municipality, iteration,
                                )

                                if iter_data is None or iter_data.empty:
                                    output_file.write("Sem demanda nesta iteração\n\n")
                                    continue

                                summary, detail_items = _process_scenario(
                                    iter_data, shift, municipality, iteration, output_file,
                                )

                                if summary is not None:
                                    base_info = {
                                        "instancia": instance_name,
                                        "dia": day,
                                        "turno": shift,
                                        "cd_municipio": municipality,
                                        "iteracao": iteration,
                                    }
                                    summaries.append({**base_info, **summary})

                                    for detail in detail_items:
                                        details.append({**base_info, **detail})

                            # Salvar CSVs incrementalmente por município
                            _save_results(
                                summaries, details, instance_name, route_type,
                            )

            logger.info(
                "Instância %s (%s) concluída. Resultados em: %s",
                instance_name, route_type, output_path,
            )


# ---------------------------------------------------------------------------
# Funções de escrita e salvamento
# ---------------------------------------------------------------------------

def _write_shift_header(output_file: TextIOWrapper, shift: str) -> None:
    """Escreve o cabeçalho de turno no arquivo de saída."""
    horizon = LATEST_ARRIVAL - EARLIEST_DEPARTURE
    output_file.write(f"Horizonte de Tempo: {horizon} segundos\n\n")
    output_file.write("##############################\n")
    output_file.write(f"####  Turno Atual: {shift}  ####\n")
    output_file.write("##############################\n\n")


def _write_iteration_header(
    output_file: TextIOWrapper, iteration: int, municipality: str,
) -> None:
    """Escreve o cabeçalho de iteração no arquivo de saída."""
    departure_time = EARLIEST_DEPARTURE + TIME_SLOT_DURATION * iteration
    header = f"|Iteração{iteration}, Horário de Saída: {departure_time}|"
    output_file.write("_" * len(header) + "\n")
    output_file.write(header + "\n")
    output_file.write("|" + "_" * (len(header) - 2) + "|\n\n")
    output_file.write(municipality + "\n")


def _save_results(
    summaries: list[dict],
    details: list[dict],
    instance_name: str,
    route_type: str,
) -> None:
    """Salva os resultados parciais em CSVs."""
    if summaries:
        pd.DataFrame(summaries).to_csv(
            OUTPUT_CSV_DIR / f"solucao_cvrptw_{instance_name}_{route_type}.csv",
            index=False,
        )
    if details:
        pd.DataFrame(details).to_csv(
            OUTPUT_CSV_DIR / f"solucao_completa_cvrptw_{instance_name}_{route_type}.csv",
            index=False,
        )
