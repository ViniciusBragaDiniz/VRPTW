"""Pós-processamento: minimização do número de veículos por viagem.

Após a resolução do VRPTW, este módulo tenta reduzir o número de veículos
utilizados em cada viagem (combinação de tipo de rota, instância, dia, turno
e município). O algoritmo gera todas as partições possíveis dos tempos de
viagem das rotas e busca a partição válida com o menor número de subconjuntos,
respeitando a jornada máxima por veículo.

Exemplo de uso:
    >>> from vrptw.postprocessing import minimize_vehicles
    >>> df_adjusted = minimize_vehicles()
    >>> print(df_adjusted.head())
"""

import logging

import pandas as pd

from config import MAX_VEHICLE_WORK_TIME, OUTPUT_CSV_DIR

logger = logging.getLogger(__name__)


def generate_partitions(elements: list) -> list[list[list]]:
    """Gera recursivamente todas as partições de uma lista.

    Uma partição agrupa os elementos em subconjuntos não vazios e disjuntos
    cuja união é o conjunto original.

    Args:
        elements: Lista de elementos a particionar.

    Returns:
        Lista de partições. Cada partição é uma lista de subconjuntos (listas).

    Exemplo:
        >>> generate_partitions([1, 2])
        [[[2, 1]], [[1], [2]]]
    """
    if len(elements) == 1:
        return [[elements]]

    first = elements[0]
    result = []

    for partition in generate_partitions(elements[1:]):
        # Adicionar o primeiro elemento a cada subconjunto existente
        for i in range(len(partition)):
            new_partition = [subset[:] for subset in partition]
            new_partition[i].append(first)
            result.append(new_partition)

        # Criar novo subconjunto contendo apenas o primeiro elemento
        result.append([[first]] + partition)

    return result


def minimize_vehicles() -> pd.DataFrame:
    """Re-sequencia viagens para minimizar o número de veículos utilizados.

    Carrega as soluções detalhadas de rotas (entrada e saída), identifica
    viagens com múltiplos veículos e tenta consolidá-las em menos veículos
    respeitando a restrição de jornada máxima.

    Returns:
        DataFrame com o número de veículos ajustado por viagem.

    Raises:
        FileNotFoundError: Se os arquivos de solução não forem encontrados.
    """
    logger.info("Iniciando minimização de veículos")

    # Carregar soluções
    sol_entrada = pd.read_csv(OUTPUT_CSV_DIR / "solucao_completa_cvrptw_full_ENTRADA.csv")
    sol_entrada["tipo_de_rota"] = "ENTRADA"

    sol_saida = pd.read_csv(OUTPUT_CSV_DIR / "solucao_completa_cvrptw_full_SAIDA.csv")
    sol_saida["tipo_de_rota"] = "SAIDA"

    full_solution = pd.concat([sol_entrada, sol_saida], ignore_index=True)

    # Resumo agregado por viagem
    group_cols = ["tipo_de_rota", "instancia", "dia", "turno", "cd_municipio"]
    adjusted = full_solution.groupby(group_cols).agg(
        id_veiculo=("id_veiculo", "nunique"),
        tempo_viagem=("tempo_viagem", "sum"),
    )

    # Identificar viagens únicas
    trips = full_solution[group_cols].drop_duplicates()
    indexed_solution = full_solution.set_index(group_cols)

    adjusted_count = 0

    for _, row in trips.iterrows():
        trip_key = tuple(row)
        trip_data = indexed_solution.loc[trip_key]

        # Pular viagens com veículo único (não há como reduzir)
        if trip_data["id_veiculo"].nunique() == 1:
            continue

        travel_times = trip_data["tempo_viagem"].tolist()
        partitions = generate_partitions(travel_times)

        # Buscar a primeira partição válida (já ordenadas do menor para o maior)
        for partition in partitions:
            valid = all(
                sum(subset) <= MAX_VEHICLE_WORK_TIME
                for subset in partition
            )
            if valid:
                adjusted.loc[trip_key, "id_veiculo"] = len(partition)
                adjusted_count += 1
                break

    adjusted = adjusted.reset_index()
    output_path = OUTPUT_CSV_DIR / "solucao_ajustada.csv"
    adjusted.to_csv(output_path, index=False)

    logger.info(
        "Minimização concluída. %d viagens ajustadas. Salvo em: %s",
        adjusted_count,
        output_path,
    )
    return adjusted
