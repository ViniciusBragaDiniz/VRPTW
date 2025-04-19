import pandas as pd
import numpy as np
from sklearn.cluster import k_means
import time as temporizador
import warnings
warnings.filterwarnings('ignore')



def encontrar_cotovelo(k_values, inertias):
    """
    Dada uma lista (ou vetor) de valores de k e os respectivos valores de inércia,
    essa função retorna o número ótimo de clusters (o cotovelo), o índice correspondente
    e um vetor com as distâncias de cada ponto à reta que conecta o primeiro e o último ponto.

    Parâmetros:
        k_values (array-like): Lista com os valores de k testados (ex.: [1, 2, ...])
        inertias (array-like): Lista com os valores de inércia obtidos para cada k.

    Retorna:
        optimal_k (int/float): Valor de k correspondente ao "cotovelo".
        elbow_index (int): Índice do ponto de cotovelo na lista.
        distances (np.array): Array com as distâncias de cada ponto à reta.
    """
    # Converter entradas para arrays NumPy
    k_values = np.array(k_values)
    inertias = np.array(inertias)

    # Definir o primeiro e último ponto da curva
    x1, y1 = k_values[0], inertias[0]
    x2, y2 = k_values[-1], inertias[-1]

    # Vetor que representa a reta entre o primeiro e o último ponto
    linha_vec = np.array([x2 - x1, y2 - y1])
    norma_linha = np.linalg.norm(linha_vec)
    linha_unit = linha_vec / norma_linha

    # Para cada ponto (xi, yi), calcular o vetor desde o primeiro ponto
    pontos = np.vstack((k_values, inertias)).T
    vetor_inicio = pontos - np.array([x1, y1])

    # Projeção dos vetores na direção da linha unitária
    proj_scalars = np.dot(vetor_inicio, linha_unit)
    proj = np.outer(proj_scalars, linha_unit)

    # Vetores perpendiculares à reta
    diff = vetor_inicio - proj
    # Distâncias de cada ponto à reta
    distances = np.linalg.norm(diff, axis=1)

    # Encontrar o índice do ponto com a maior distância (este é o cotovelo)
    elbow_index = np.argmax(distances)
    optimal_k = k_values[elbow_index]

    return elbow_index


def gerar_pontos(alunos:str = ""):
    """
    Função para gerar pontos de ônibus com base em dados de alunos e suas localizações.
    A função lê um arquivo CSV contendo informações dos alunos, filtra os dados com base
    em um identificador de aluno (ou uma lista de alunos), e aplica o algoritmo k-means
    para identificar clusters de alunos em diferentes municípios e dias da semana.
    Os pontos de ônibus são gerados com base na localização dos alunos e na demanda
    por transporte em diferentes turnos (manhã, tarde, noite).
    Os resultados são salvos em um arquivo CSV.
    Parâmetros:
        alunos (str): Identificador de aluno ou lista de alunos a serem considerados.
                      Se vazio, considera todos os alunos.
    Retorna:
        pontos_de_onibus (DataFrame): DataFrame contendo os pontos de ônibus gerados,
                                       com informações sobre localização, demanda e dia da semana.
    """
    # Carrega o dataframe contendo informações dos alunos
    df_alunos = pd.read_csv("Dados/info_alunos.csv")

    filter_condition = df_alunos['id_aluno'].str.contains(alunos)
    df_alunos = df_alunos[filter_condition]


    # Obtém a lista única de municípios presentes no dataframe
    municipios = df_alunos.CIDADE.unique()
    # Obtém a lista única dos dias da semana em que há registros
    dias_da_semana = df_alunos.DIA.unique()


    # Inicializa uma lista vazia para armazenar os dataframes de pontos de ônibus para cada município e dia
    pontos_de_onibus = []

    # Inicializa contadores para municípios e alunos desconsiderados devido ao baixo número de alunos
    municipios_desconsiderados = 0
    alunos_desconsiderados = 0

    # Loop que itera sobre cada município único na lista de municípios
    for cd_mun in municipios:
        # Marca o tempo de início do processamento para cada município
        start = temporizador.time()
        # Filtra o dataframe para conter apenas os alunos do município atual e remove duplicatas de alunos
        alunos_municipio = df_alunos[(df_alunos['CIDADE'] == cd_mun)].drop_duplicates(subset='id_aluno')
        # Verifica se o número de alunos no município é menor que 10
        if len(alunos_municipio) < 10:
            # Incrementa o contador de municípios desconsiderados
            municipios_desconsiderados += 1
            # Incrementa o contador de alunos desconsiderados
            alunos_desconsiderados += len(alunos_municipio)
            # Imprime uma mensagem indicando que o município foi pulado devido ao baixo número de alunos
            print('Município:', cd_mun, "N Alunos:", len(alunos_municipio), "PULADO")
            # Pula para a próxima iteração do loop (próximo município)
            continue

        # Imprime o nome do município e o número de alunos considerados para este município
        print('Município:', cd_mun, "N Alunos:", len(alunos_municipio))

        # Define o número máximo de clusters a serem testados (pode ser ajustado)
        CLUSTERS = 20
        # Inicializa uma lista vazia para armazenar os valores de WCSS (Within-Cluster Sum of Squares)
        wcss = []
        # Loop para calcular a inércia (WCSS) para diferentes números de clusters (k)
        for i in range(2,len(alunos_municipio)+1):
            # Aplica o algoritmo k-means para o número de clusters 'i' nas coordenadas de latitude e longitude dos alunos
            centroids, classes, inertia = k_means(alunos_municipio[['LATITUDE','LONGITUDE']],i, n_init=10) # Adicionado n_init para melhor convergência
            # Adiciona o valor da inércia à lista wcss
            wcss.append(inertia)
        # Chama a função para encontrar o número ótimo de clusters (o "cotovelo") usando os valores de k e as inércias
        optimal_k = encontrar_cotovelo(range(2,len(alunos_municipio)+1), wcss)

        # Aplica o algoritmo k-means com o número ótimo de clusters encontrado
        centroids, classes, _ = k_means(alunos_municipio[['LATITUDE','LONGITUDE']],optimal_k, n_init=10) # Adicionado n_init para consistência

        # Adiciona a atribuição de classe (cluster) ao dataframe de alunos do município
        alunos_municipio['class'] = classes
        # Mescla o dataframe principal de alunos com as classes dos alunos do município para adicionar a informação de classe aos registros correspondentes
        comp_df = df_alunos.merge(alunos_municipio[['id_aluno','class']],'left','id_aluno')
        # Loop que itera sobre cada dia da semana único
        for dia in dias_da_semana:
            # Imprime uma linha separadora para melhor visualização no console
            print('#'*22)
            # Cria um dataframe de centroids com as coordenadas dos centroides e o código do município
            centroids_df = pd.DataFrame(centroids,columns=['lon','lat'])
            centroids_df['cd_municipio'] = cd_mun
            # Define a condição para filtrar o dataframe pelo dia da semana atual
            cond_dia = comp_df['DIA'] == dia

            # Calcula a demanda por turno (manhã, tarde, noite) para cada cluster no dia atual
            demanda_manha = comp_df[(comp_df['TURNO']=='manhã') & cond_dia].groupby('class').count()['TURNO']
            demanda_tarde = comp_df[(comp_df['TURNO']=='tarde') & cond_dia].groupby('class').count()['TURNO']
            demanda_noite = comp_df[(comp_df['TURNO']=='noite') & cond_dia].groupby('class').count()['TURNO']

            # Adiciona as informações de demanda (se houver) ao dataframe de centroids, usando o índice do cluster como chave
            centroids_df.loc[demanda_manha.index,'demanda_manha'] = demanda_manha
            centroids_df.loc[demanda_tarde.index,'demanda_tarde'] = demanda_tarde
            centroids_df.loc[demanda_noite.index,'demanda_noite'] = demanda_noite
            # Adiciona o dia da semana ao dataframe de centroids
            centroids_df['dia'] = dia

            # Preenche quaisquer valores NaN (resultantes de clusters sem demanda em algum turno) com 0
            centroids_df.fillna(0,inplace=True)
            # Adiciona o dataframe de centroids (que representa os potenciais pontos de ônibus para o município e dia) à lista de pontos de ônibus
            pontos_de_onibus.append(centroids_df)

    # Concatena todos os dataframes de pontos de ônibus na lista em um único dataframe
    pontos_de_onibus = pd.concat(pontos_de_onibus,ignore_index=True)

    # Imprime o número total de municípios desconsiderados
    print("Municipios Desconsiderados", municipios_desconsiderados)
    # Imprime o número total de alunos desconsiderados
    print("Alunos Desconsiderados", alunos_desconsiderados)


    # Retorna o dataframe final de pontos de ônibus
    return pontos_de_onibus