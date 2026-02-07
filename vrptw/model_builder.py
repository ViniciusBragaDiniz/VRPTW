"""Construção do modelo de Programação Linear Inteira Mista (PLIM) para o VRPTW.

Este módulo encapsula a formulação matemática do problema: criação das
variáveis de decisão, função objetivo e restrições. A formulação segue o
modelo clássico de roteamento com janelas de tempo, com eliminação de
subciclos via planos de corte (lazy constraints).

Formulação:
    - **Variáveis**:
        - ``x[k,i,j]``: binária, 1 se o veículo k viaja de i para j.
        - ``s[k,i]``: contínua, instante de início do serviço no nó i pelo veículo k.
        - ``q[k,i]``: inteira, carga atendida no nó i pelo veículo k.
    - **Objetivo**: minimizar a distância total percorrida.
    - **Restrições**: capacidade, atendimento obrigatório, fluxo conservado,
      janelas de tempo (Big-M), passagem única e eliminação de subciclos.

Exemplo de uso:
    >>> from docplex.mp.model import Model
    >>> model = Model("vrptw")
    >>> model, travels = build_model(model, model_data)
"""

from docplex.mp.linear import LinearExpr
from docplex.mp.model import Model


# ---------------------------------------------------------------------------
# Variáveis de decisão
# ---------------------------------------------------------------------------

def _build_variables(
    model: Model,
    model_data: dict,
) -> tuple[dict, dict, dict]:
    """Cria as variáveis de decisão do modelo VRPTW.

    Args:
        model: Instância do modelo DOCPLEX.
        model_data: Dicionário com os dados da instância. Espera as chaves
            ``necessary_vehicles``, ``capacity``, ``data`` (DataFrame).

    Returns:
        Tupla ``(travels, service, vehicle_load)`` contendo os dicionários
        de variáveis indexados por ``(k, i, j)`` ou ``(k, i)``.
    """
    num_vehicles = model_data["necessary_vehicles"]
    capacity = model_data["capacity"]
    city_data = model_data["data"]

    # x[k,i,j] - veículo k viaja do nó i ao nó j
    travels = {
        (k, i, j): model.binary_var(name=f"travels_{k}_{i}_{j}")
        for k in range(num_vehicles)
        for i in city_data.index
        for j in city_data.index
    }

    # s[k,i] - instante de início do serviço no nó i pelo veículo k
    service = {
        (k, i): model.continuous_var(
            lb=city_data["tempo_preparo"][i],
            ub=city_data["tempo_entrega"][i],
            name=f"service_start_{k}_{i}",
        )
        for k in range(num_vehicles)
        for i in city_data.index
    }

    # q[k,i] - carga atendida no nó i pelo veículo k
    vehicle_load = {
        (k, i): model.integer_var(
            lb=0, ub=capacity, name=f"load_{k}_{i}"
        )
        for k in range(num_vehicles)
        for i in city_data.index
    }

    return travels, service, vehicle_load


# ---------------------------------------------------------------------------
# Função objetivo
# ---------------------------------------------------------------------------

def _build_objective(model: Model, travels: dict, model_data: dict) -> None:
    """Define a função objetivo: minimizar a distância total percorrida.

    Args:
        model: Instância do modelo DOCPLEX.
        travels: Dicionário de variáveis de viagem ``(k, i, j)``.
        model_data: Dicionário com ``distancia`` (matriz de tempos) e ``data``.
    """
    distances = model_data["distancia"]
    city_data = model_data["data"]
    num_vehicles = model_data["necessary_vehicles"]

    model.minimize(
        model.sum(
            travels[k, i, j] * distances[i][j]
            for i in city_data.index
            for j in city_data.index
            for k in range(num_vehicles)
        )
    )


# ---------------------------------------------------------------------------
# Restrições
# ---------------------------------------------------------------------------

def _build_constraints(
    model: Model,
    travels: dict,
    service: dict,
    load: dict,
    model_data: dict,
) -> None:
    """Adiciona todas as restrições ao modelo VRPTW.

    Restrições implementadas:
        1. Capacidade total por veículo.
        2. Atendimento obrigatório de cada cliente (demanda).
        3. Visitação obrigatória: para atender carga, é preciso visitar o ponto.
        4. Saída a partir do depósito.
        5. Conservação de fluxo em cada nó.
        6. Passagem única: cada veículo passa no máximo uma vez por nó.
        7. Janelas de tempo (formulação Big-M).
        8. Remoção da diagonal (proibir auto-loops).

    Args:
        model: Instância do modelo DOCPLEX.
        travels: Variáveis de viagem ``(k, i, j)``.
        service: Variáveis de tempo de serviço ``(k, i)``.
        load: Variáveis de carga ``(k, i)``.
        model_data: Dicionário com os dados da instância.
    """
    capacity = model_data["capacity"]
    depot = model_data["depot"]
    city_data = model_data["data"]
    shift = model_data["turno"]
    num_spots = model_data["num_spots"]
    num_vehicles = model_data["necessary_vehicles"]
    distances = model_data["distancia"]
    big_m = model_data["big_m"]

    # 1. Capacidade total de cada veículo
    for k in range(num_vehicles):
        model.add_constraint(
            model.sum(load[k, i] for i in city_data.index) <= capacity,
            f"Capacity_Vehicle_{k}",
        )

    # 2. Atendimento obrigatório de cada cliente
    for i in city_data.index[1:]:
        model.add_constraint(
            model.sum(load[k, i] for k in range(num_vehicles))
            == city_data.loc[i, f"demanda_{shift}"],
            f"Demand_Client_{i}",
        )

    # 3. Visitação obrigatória (para atender carga, precisa visitar o ponto)
    for k in range(num_vehicles):
        for i in city_data.index:
            model.add_constraint(
                model.sum(capacity * travels[k, i, j] for j in city_data.index)
                - load[k, i] >= 0,
                f"Visit_Required_{i}_Vehicle_{k}",
            )

    # 4. Saída a partir do depósito
    for k in range(num_vehicles):
        model.add_constraint(
            model.sum(
                num_spots ** 2 * travels[k, depot, j]
                for j in city_data.index[1:]
            )
            - model.sum(
                travels[k, i, j]
                for i in city_data.index[1:]
                for j in city_data.index[1:]
            ) >= 0,
            f"Depot_Exit_Vehicle_{k}",
        )

    # 5. Conservação de fluxo
    for k in range(num_vehicles):
        for i in city_data.index:
            model.add_constraint(
                model.sum(
                    travels[k, i, j] - travels[k, j, i]
                    for j in city_data.index
                ) == 0,
                f"Flow_Conservation_Vehicle_{k}_Node_{i}",
            )

    # 6. Passagem única por nó
    for k in range(num_vehicles):
        for i in city_data.index:
            model.add_constraint(
                model.sum(travels[k, i, j] for j in city_data.index) <= 1,
                f"Single_Pass_Vehicle_{k}_Node_{i}",
            )

    # 7. Janelas de tempo (Big-M)
    for k in range(num_vehicles):
        for idx_i in range(len(city_data)):
            origin = city_data.index[idx_i]
            for idx_j in range(idx_i + 1, len(city_data)):
                destination = city_data.index[idx_j]
                model.add_constraint(
                    service[k, origin]
                    + distances[origin][destination]
                    - big_m * (1 - travels[k, origin, destination])
                    <= service[k, destination],
                    f"Time_Window_{k}_{origin}_{destination}",
                )

    # 8. Remoção da diagonal (proibir i→i)
    model.add_constraint(
        model.sum(
            travels[k, i, i]
            for k in range(num_vehicles)
            for i in city_data.index
        ) == 0,
        "No_Self_Loops",
    )


# ---------------------------------------------------------------------------
# Eliminação de subciclos
# ---------------------------------------------------------------------------

def add_subtour_cuts(
    model: Model,
    routes: dict[int, dict[int, int]],
    travels: dict,
    vehicle: int,
) -> None:
    """Adiciona restrições de eliminação de subciclos para um veículo.

    Percorre todos os ciclos desconectados do depósito encontrados nas rotas
    do veículo e insere uma desigualdade que proíbe aquele subciclo específico.

    Args:
        model: Instância do modelo DOCPLEX.
        routes: Dicionário de rotas do veículo (lista encadeada ``{i: j}``).
        travels: Variáveis de viagem ``(k, i, j)``.
        vehicle: Índice do veículo.
    """
    cut_count = 0

    while routes[vehicle]:
        cut_expr = LinearExpr(model)
        size = 0

        first_node = next(iter(routes[vehicle]))
        current = routes[vehicle].pop(first_node)
        cut_expr += travels[vehicle, int(first_node), int(current)]

        while current != first_node:
            next_node = routes[vehicle].pop(current)
            cut_expr += travels[vehicle, int(current), int(next_node)]
            size += 1
            current = next_node

        cut_count += 1
        model.add_constraint(cut_expr <= size, f"SubtourCut_{vehicle}_{cut_count}")


def format_route_string(
    routes: dict[int, dict[int, int]],
    travels: dict,
    vehicle: int,
    earliest_departure: int,
    iteration: int,
    distance_matrix: dict,
) -> str:
    """Formata a rota de um veículo como string legível.

    Percorre a lista encadeada da rota do veículo e produz uma string
    descritiva com o caminho e os tempos de início/fim.

    Args:
        routes: Dicionário de rotas do veículo.
        travels: Variáveis de viagem (não utilizado diretamente, mantido por compatibilidade).
        vehicle: Índice do veículo.
        earliest_departure: Instante mais cedo de partida (segundos).
        iteration: Iteração temporal corrente.
        distance_matrix: Matriz de tempos de viagem.

    Returns:
        String formatada descrevendo a rota, ou string vazia se a rota estiver vazia.
    """
    if not routes[vehicle]:
        return ""

    first_node = next(iter(routes[vehicle]))
    current = routes[vehicle].pop(first_node)

    route_str = f"Veículo {vehicle} Início [{earliest_departure + 1800 * iteration}s] |Rota: 0"
    total_time = distance_matrix[first_node][current]

    while current != first_node:
        next_node = routes[vehicle].pop(current)
        total_time += distance_matrix[current][next_node]
        route_str += f" -> {current}"
        current = next_node

    route_str += " -> 0"
    route_str += f"| Fim [{earliest_departure + total_time + 1800 * iteration}s]\n"
    return route_str


# ---------------------------------------------------------------------------
# Função principal de construção
# ---------------------------------------------------------------------------

def build_model(
    model: Model,
    model_data: dict,
) -> tuple[Model, dict]:
    """Constrói o modelo VRPTW completo (variáveis + objetivo + restrições).

    Args:
        model: Instância do modelo DOCPLEX (vazia ou pré-configurada).
        model_data: Dicionário com todos os dados da instância.

    Returns:
        Tupla ``(model, travels)`` com o modelo configurado e o dicionário
        de variáveis de viagem (necessário para o loop de resolução).
    """
    travels, service, load = _build_variables(model, model_data)
    _build_objective(model, travels, model_data)
    _build_constraints(model, travels, service, load, model_data)

    return model, travels
