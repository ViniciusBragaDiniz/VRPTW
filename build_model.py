from docplex.mp.linear import LinearExpr

def build_vars(model, model_data: dict):
    """
    Cria as variáveis de decisão do modelo.
    Args:
        model: Modelo de otimização.
        data: Dados necessários para a construção do modelo.
    Returns:
        model: Modelo com as variáveis de decisão adicionadas.
    """
    necessary_vehicles = model_data['necessary_vehicles']
    capacity = model_data['capacity']
    iteracao = model_data['iteracao']
    fatia_tempo = model_data['fatia_tempo']
    city_data = model_data['data']

    # Matriz tridimensional k*v²
    travels = {(k,i,j): model.binary_var(name=f'travels_{k}_{i}_{j}') for k in range(necessary_vehicles) for i in city_data.index for j in city_data.index}

    service = {(k,i): model.continuous_var(
    lb=city_data['tempo_preparo'][i],
        ub=city_data['tempo_entrega'][i],name=f'service_start_{k}_{i}') 
        for k in range(necessary_vehicles) for i in city_data.index} # Momento em que o serviço começa no cliente i

    vehicle_capacity = {(k,i): model.integer_var(lb=0,ub=capacity,name=f'clients_at_{i}_with_{k}') for k in range(necessary_vehicles) for i in city_data.index}

    return travels, service, vehicle_capacity

def build_objective(model, travels, model_data: dict):
    """
    Define a função objetivo do modelo.
    Args:
        model: Modelo de otimização.
        travels: Variáveis de decisão de viagens.
        model_data: Dados necessários para a construção do modelo.
    """
    distancia = model_data['distancia']
    city_data = model_data['data']
    necessary_vehicles = model_data['necessary_vehicles']
    # Função objetivo: minimizar a soma das distâncias percorridas pelos veículos
    model.minimize(model.sum(travels[k,i,j]*distancia[i][j] for i in city_data.index for j in city_data.index for k in range(necessary_vehicles)))

def build_constraints(model, travels_matrix, service_matrix, capacity_matrix, model_data: dict):
    """
    Adiciona as restrições ao modelo.
    Args:
        model: Modelo de otimização.
        travels: Variáveis de decisão de viagens.
        service: Variáveis de decisão de serviço.
        capacity: Variáveis de capacidade dos veículos.
        model_data: Dados necessários para a construção do modelo.
    """
    vehicle_capacity = model_data['capacity']
    depot = model_data['depot']
    city_data = model_data['data']
    turno = model_data['turno']
    num_spots = model_data['num_spots']
    necessary_vehicles = model_data['necessary_vehicles']
    distances = model_data['distancia']
    big_m = model_data['big_m']

    #Respeitar Tempo de Entrega
        #Respeitar Capacidade
    for k in range(necessary_vehicles):
        consumed_capacity = model.sum(capacity_matrix[k, i] for i in city_data.index)
        model.add_constraint(consumed_capacity <= vehicle_capacity, 'Capacity_Vehicle_' + str(k))

    # Atender o cliente i é obrigatório
    for i in city_data.index[1:]:
        demand_met = model.sum(capacity_matrix[k, i] for k in range(necessary_vehicles))
        model.add_constraint(demand_met == city_data.loc[i, 'demanda_' + turno], 'Visit_Client_' + str(i))

    # Para pegar clientes é preciso visitar o ponto
    for k in range(necessary_vehicles):
        for i in city_data.index:
            visit_i = model.sum(vehicle_capacity * travels_matrix[k, i, j] for j in city_data.index)
            model.add_constraint(visit_i - capacity_matrix[k, i] >= 0, f"Visit_Client_{i}_Vehicle_{k}")

    # Saída a Partir do Depósito
    for k in range(necessary_vehicles):
        model.add_constraint(
            model.sum((num_spots * num_spots) * travels_matrix[k, depot, j]
                      for j in city_data.index[1:]) -
            model.sum(travels_matrix[k, i, j]
                      for i in city_data.index[1:]
                      for j in city_data.index[1:]) >= 0,
            'Exit_Depot_Vehicle_' + str(k))

    # Conservação de Fluxo
    for k in range(necessary_vehicles):
        for i in city_data.index:
            model.add_constraint(
                model.sum(travels_matrix[k, i, j] - travels_matrix[k, j, i]
                          for j in city_data.index) == 0,
                f'Flux_Conservation_Vehicle_{k}_Node_{i}')

    # Passagem Única de Fluxo
    for k in range(necessary_vehicles):
        for i in city_data.index:
            model.add_constraint(
                model.sum(travels_matrix[k, i, j]
                          for j in city_data.index) <= 1,
                f'Unique_Passage_Vehicle_{k}_Node_{i}')

    # Tempo de Saída
    for k in range(necessary_vehicles):
        for i in range(len(city_data)):
            exit = city_data.index[i]
            for j in range(i+1,len(city_data)):
                arrival = city_data.index[j]
                model.add_constraint(service_matrix[k, exit] + distances[exit][arrival] - big_m * (1 - travels_matrix[k, exit, arrival]) <= service_matrix[k, arrival],
                                     f'Exit_Time_{k}_{exit}_{arrival}')
    # Remoção da Diagonal
    model.add_constraint(model.sum(travels_matrix[k, i, i] for k in range(necessary_vehicles) for i in city_data.index) == 0)

def operate_cycle(model, routes, travels, k, option: str = "cut", tempo_preparo: int = 0, iteracao: int = 0, distancia: list = [[]]):
    """
    Função para realizar uma operação em cima dos ciclos enviados.
    Args:
        model: Modelo de otimização.
        routes: Dicionário com as rotas dos veículos.
        travels: Variáveis de decisão de viagens.
        k: Índice do veículo.
        option: Opção para definir o tipo de saída (corte ou string).
        tempo_preparo: Tempo de preparo do veículo.
        iteracao: Iteração atual.
        distancia: Matriz de distâncias entre os pontos.
    Returns:
        string: String formatada com a rota do veículo.
    """

    while(len(routes[k])>0):
        if option == "cut":
            cut = LinearExpr(model) #Expressão Linear do Subciclo atual
            count = 0
            size = 0
        
        first_node = list(routes[k].keys())[0]
        actual_node = routes[k].pop(first_node)

        if option == "cut":
            cut += travels[k,int(first_node),int(actual_node)]
        elif option == "string":
            string = f"Veículo {k} Início [{tempo_preparo+1800*iteracao}s] |Rota: 0"
            tempo_final = distancia[first_node][actual_node]

        while(actual_node != first_node):
            next_node = routes[k].pop(actual_node)           

            if option == "cut": 
                # Percorre o subciclo e o adiciona ao#
                # conjunto de subciclos proíbidos.#
                cut += travels[k,int(actual_node),int(next_node)]
                size+=1
            elif option == "string":	
                tempo_final += distancia[actual_node][next_node]
                string+=" -> "+str(actual_node)
            actual_node = next_node
            

        if option == "cut":
            count+=1
            model.add_constraint(cut<=size,"SubCycleCut_"+str(count))
        elif option == "string":
            string += " -> 0"
            string += f"| Fim [{tempo_preparo+tempo_final+1800*iteracao}s]\n"
            return string
def build_model(model, model_data: dict):

    travels_matrix, service_matrix, capacity_matrix = build_vars(model, model_data)
    build_objective(model, travels_matrix, model_data)
    build_constraints(model, travels_matrix, service_matrix, capacity_matrix, model_data)

    return model, travels_matrix