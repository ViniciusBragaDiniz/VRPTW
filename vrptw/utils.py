"""Funções utilitárias para o modelo VRPTW.

Contém funções de uso geral compartilhadas pelos demais módulos do pacote:
cálculo de distância geodésica (Haversine), construção da matriz de tempos
de viagem, extração de rotas a partir da solução do CPLEX e preparação
de dados para particionamento temporal da demanda.

Exemplo de uso:
    >>> from vrptw.utils import haversine
    >>> dist = haversine(-22.70, -43.46, -22.90, -43.20)
    >>> print(f"Distância: {dist:.0f} m")
"""

import logging
import math
from typing import Any

import pandas as pd

from config import MUNICIPALITY_SPEED_KMH, DEFAULT_SPEED_KMH

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Cálculo de distância geodésica
# ---------------------------------------------------------------------------

def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calcula a distância entre dois pontos na superfície da Terra (Haversine).

    Args:
        lat1: Latitude do ponto 1 (graus decimais).
        lon1: Longitude do ponto 1 (graus decimais).
        lat2: Latitude do ponto 2 (graus decimais).
        lon2: Longitude do ponto 2 (graus decimais).

    Returns:
        Distância entre os dois pontos em metros.
    """
    EARTH_RADIUS_M = 6_371_000

    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return EARTH_RADIUS_M * c


# ---------------------------------------------------------------------------
# Matriz de tempos de viagem
# ---------------------------------------------------------------------------

def _speed_for_municipality(municipality: str) -> float:
    """Retorna a velocidade média (m/s) configurada para um município.

    Args:
        municipality: Nome padronizado do município.

    Returns:
        Velocidade em metros por segundo.
    """
    speed_kmh = MUNICIPALITY_SPEED_KMH.get(municipality, DEFAULT_SPEED_KMH)
    return speed_kmh / 3.6  # km/h → m/s


def calculate_distances(
    data: pd.DataFrame,
    municipality: str,
    iteration: int,
    time_slot: int,
) -> tuple[dict[int, dict[int, float]], float]:
    """Constrói a matriz de tempos de viagem entre todos os pares de pontos.

    Para cada par (i, j) com i ≠ j, calcula a distância Haversine em metros
    e a converte para tempo de viagem (segundos) usando a velocidade média
    configurada para o município. A diagonal (i == i) recebe ``inf``.

    Também calcula o valor Big-M necessário para as restrições de janela de
    tempo do modelo (o maior valor de ``tempo_entrega[i] + tempo_viagem[i][j]
    - (tempo_preparo[i] + time_slot * iteration)``).

    Args:
        data: DataFrame indexado por ``centroid_id`` com colunas ``lat``,
            ``lon``, ``tempo_preparo`` e ``tempo_entrega``.
        municipality: Nome padronizado do município (para seleção de velocidade).
        iteration: Iteração temporal corrente (usada no cálculo de Big-M).
        time_slot: Duração de cada fatia de tempo em segundos.

    Returns:
        Tupla ``(distance_matrix, big_m)`` onde ``distance_matrix`` é um
        dict-de-dicts e ``big_m`` é o escalar necessário para as restrições.
    """
    speed_ms = _speed_for_municipality(municipality)
    indices = data.index

    distance_matrix: dict[int, dict[int, float]] = {
        i: {j: 0.0 for j in indices} for i in indices
    }

    big_m = -1.0

    for i in indices:
        for j in indices:
            if i == j:
                distance_matrix[i][j] = float("inf")
                continue

            dist_m = haversine(
                data["lat"][i], data["lon"][i],
                data["lat"][j], data["lon"][j],
            )
            travel_time = round(dist_m / speed_ms)
            distance_matrix[i][j] = travel_time

            candidate = (
                data["tempo_entrega"][i]
                + travel_time
                - (data["tempo_preparo"][i] + time_slot * iteration)
            )
            big_m = max(big_m, candidate)

    return distance_matrix, big_m


# ---------------------------------------------------------------------------
# Extração de rotas a partir da solução CPLEX
# ---------------------------------------------------------------------------

def build_routes(solution: dict, num_vehicles: int) -> dict[int, dict[int, int]]:
    """Extrai as rotas de cada veículo a partir do dicionário de solução.

    Percorre as variáveis de decisão ``travels_k_i_j`` presentes na solução
    e reconstrói um dicionário de listas encadeadas representando as rotas.

    Args:
        solution: Dicionário retornado por ``model.solve().as_dict()``.
        num_vehicles: Número de veículos do modelo.

    Returns:
        Dicionário ``{k: {i: j, ...}}`` onde cada chave ``k`` é um veículo
        e o sub-dicionário mapeia nó de origem → nó de destino.
    """
    routes: dict[int, dict[int, int]] = {k: {} for k in range(num_vehicles)}

    for var, value in solution.items():
        if not var.name.startswith("t") or value < 0.001:
            continue

        parts = var.name.split("_")[1:]  # ["k", "i", "j"]
        k, i, j = int(parts[0]), int(parts[1]), int(parts[2])
        routes[k][i] = j

    return routes


# ---------------------------------------------------------------------------
# Preparação de dados (particionamento temporal de demanda)
# ---------------------------------------------------------------------------

def partition_demand(
    shift: str,
    model_data: pd.DataFrame,
    capacity: int,
    time_slot: int,
) -> pd.DataFrame:
    """Particiona a demanda em fatias temporais quando excede a capacidade.

    Para pontos cuja demanda total excede a capacidade de um único veículo,
    distribui a demanda em múltiplas iterações (fatias de tempo), permitindo
    que veículos realizem viagens escalonadas.

    Args:
        shift: Turno do dia (``'manha'``, ``'tarde'``, ``'noite'``).
        model_data: DataFrame com os dados de demanda e janelas de tempo.
        capacity: Capacidade máxima de cada veículo.
        time_slot: Duração de cada fatia de tempo (segundos).

    Returns:
        DataFrame expandido com linhas adicionais para cada iteração temporal.
    """
    demand_col = f"demanda_{shift}"
    data = model_data.copy()

    # Número de fatias possíveis no horizonte de tempo
    possible_splits = (
        (data["tempo_entrega"] - data["tempo_preparo"]) / time_slot
    ).apply(math.floor)

    # Viagens necessárias por município (demanda / capacidade)
    trips_needed = (
        data.groupby("cd_municipio")[demand_col].sum() / capacity
    ).apply(math.ceil)

    # Municípios cuja demanda total cabe em um único veículo
    single_vehicle = data.groupby("cd_municipio")[demand_col].sum() <= capacity

    data["iteracao"] = 0
    data.fillna(0, inplace=True)

    extra_rows: list[pd.DataFrame] = []

    for i in range(1, len(data)):
        municipality = data["cd_municipio"][i]

        if possible_splits[i] <= 0 or single_vehicle[municipality]:
            continue

        viable_splits = min(possible_splits[i], trips_needed[municipality])
        total_demand = data.loc[i, demand_col]
        split_demand = total_demand / viable_splits
        data.loc[i, demand_col] = math.ceil(split_demand)
        remaining = total_demand - math.ceil(split_demand)

        for iteration in range(1, viable_splits):
            row = data.loc[i].copy()
            alloc = min(math.ceil(split_demand), remaining)
            row[demand_col] = alloc
            remaining -= alloc
            row["tempo_preparo"] += time_slot * iteration
            row["iteracao"] = int(iteration)
            extra_rows.append(pd.DataFrame(row).T)

    if not extra_rows:
        return data

    data = pd.concat(
        [data] + extra_rows, ignore_index=True
    ).sort_values("iteracao")
    data = data[data[demand_col] > 0].reset_index(drop=True)
    return data


def partition_demand_failed_instances(
    shift: str,
    model_data: pd.DataFrame,
    capacity: int,
    time_slot: int,
) -> pd.DataFrame:
    """Repartição de demanda para instâncias que falharam na primeira tentativa.

    Variante de :func:`partition_demand` que distribui a demanda de forma
    mais granular, ponto-a-ponto, respeitando estritamente a capacidade
    do veículo em cada iteração.

    Args:
        shift: Turno do dia.
        model_data: DataFrame com os dados de demanda.
        capacity: Capacidade máxima de cada veículo.
        time_slot: Duração de cada fatia de tempo (segundos).

    Returns:
        DataFrame expandido com demanda repartida por iteração.
    """
    demand_col = f"demanda_{shift}"
    data = model_data.copy()

    possible_splits = math.floor(
        (data["tempo_entrega"].iloc[0] - data["tempo_preparo"].iloc[0]) / time_slot
    )

    trips_needed = (
        data.groupby("cd_municipio")[demand_col].sum() / capacity
    ).apply(math.ceil)

    data["iteracao"] = 0
    data.fillna(0, inplace=True)

    for municipality in data["cd_municipio"].unique():
        needed = min(possible_splits, trips_needed[municipality])

        for iteration in range(needed - 1):
            served = 0
            aux = data.copy()
            idx = aux[
                (aux["cd_municipio"] == municipality) & (aux["iteracao"] == iteration)
            ].index

            for i in idx:
                if (served + aux.loc[i, demand_col]) <= capacity:
                    served += aux.loc[i, demand_col]
                    aux.loc[i, demand_col] = 0
                else:
                    aux.loc[i, demand_col] -= capacity - served
                    served = capacity

            complementary_idx = aux.index[~aux.index.isin(idx)]
            aux.loc[complementary_idx, demand_col] = 0
            data[demand_col] = data[demand_col] - aux[demand_col]

            aux = aux[aux["cd_municipio"] == municipality].copy()
            aux["tempo_preparo"] = time_slot * (iteration + 1)
            aux["iteracao"] = iteration + 1
            data = pd.concat([data, aux], ignore_index=True)

    return data
