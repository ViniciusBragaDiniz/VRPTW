import math
import pandas as pd
def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """ Calcula a distância entre dois pontos na superfície da Terra usando a fórmula de Haversine.
    Args:
        lat1 (float): Latitude do ponto 1 em graus.
        lon1 (float): Longitude do ponto 1 em graus.
        lat2 (float): Latitude do ponto 2 em graus.
        lon2 (float): Longitude do ponto 2 em graus.
    Returns:
        float: Distância entre os dois pontos em metros.
    """
    # Raio médio da Terra em metros
    r = 6371000  # Aproximadamente 6.371 quilômetros

    # Converte graus para radianos
    lat1 = math.radians(lat1)
    lon1 = math.radians(lon1)
    lat2 = math.radians(lat2)
    lon2 = math.radians(lon2)

    # Diferenças de latitude e longitude
    dlat = lat2 - lat1
    dlon = lon2 - lon1

    # Fórmula de Haversine
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    # Distância em metros
    distance = r * c

    return distance

def data_prep(turno: str, dados_modelo: pd.DataFrame, capacity: int) -> pd.DataFrame:
    """
    Prepara os dados para o modelo de otimização, dividindo a demanda em períodos menores. 
    Args:
        turo (str): Turno do dia (ex: 'manha', 'tarde', 'noite').
        dados_modelo (pd.DataFrame): DataFrame com os dados do modelo.
        capacity (int): Capacidade do veículo.
    Returns:
        pd.DataFrame: DataFrame preparado com a demanda dividida em períodos menores.
    """
    #Divisões dos períodos
    divisoes_possiveis = (dados_modelo['tempo_entrega'] - dados_modelo['tempo_preparo'])/(1800)
    divisoes_possiveis = divisoes_possiveis.apply(lambda x: math.floor(x))
    
    #Número de veículos necessários para atender uma demanda
    viagens_necessarias = (dados_modelo.groupby('cd_municipio').sum()['demanda_'+turno]/(capacity)).apply(lambda x: math.ceil(x))

    l = []
    
    #Só dividimos a demanda se for maior que a capacidade de um único ônibus
    demanda_minima = dados_modelo.groupby('cd_municipio').sum()['demanda_'+turno] <= capacity

    #Vamos ter uma iteracao a cada período de tempo
    dados_modelo['iteracao'] = 0
    dados_modelo.fillna(0,inplace=True)

    for i in range(1, len(dados_modelo)):
        cd_mun = dados_modelo['cd_municipio'][i] #código do municipio
        
        if divisoes_possiveis[i] <= 0 | demanda_minima[cd_mun]:
            continue #previne erros e divisões desnecessárias
        
        divisoes_viaveis = min(divisoes_possiveis[i],viagens_necessarias[cd_mun])
        #Demanda dividida pelo número de periodos
        demanda_particionada = math.floor(dados_modelo.loc[i]['demanda_'+turno] / divisoes_viaveis)
        dados_modelo.loc[i,'demanda_'+turno] = math.ceil(demanda_particionada)
        
        for iteracao in range(1,divisoes_viaveis):
            linha = dados_modelo.loc[i].copy()
            linha['demanda_'+turno] = max(demanda_particionada,1) #Esse máx é pra evitar erros devido a demanda aleatoria
            linha['tempo_preparo'] += 1800*iteracao
            linha['iteracao'] = int(iteracao)
            l.append(pd.DataFrame(linha).T)

    if len(l) == 0:
        return dados_modelo
    
    #Adiciona as iterações pelo 
    dados_modelo = pd.concat([dados_modelo,pd.concat(l,ignore_index=True)],ignore_index=True).sort_values(['iteracao'])
    return dados_modelo

def build_routes(Solution: dict, necessary_vehicles: int) -> dict:
    #Rota percorrida por cada veículo
    routes = {x:{} for x in range(necessary_vehicles)}  
    
    for i in Solution:
        # Se não for variável de rota ou se o valor for menor que 0.001
        # (ou seja, não foi alocada rota) não adiciona ao dicionário
        if i.name[0] != "t" or Solution[i] < 0.001:
            continue

        aux = i.name.split("_")[1:] #<- ["k","i","j"]
        routes[int(aux[0])][int(aux[1])]=int(aux[2])
        
    return routes