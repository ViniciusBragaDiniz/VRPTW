"""Este módulo é responsável pela geração de pontos de parada de ônibus.

Utilizando dados geográficos de alunos, este script aplica algoritmos de 
agrupamento para identificar locais ótimos que servirão como pontos de parada 
em um problema de roteamento de veículos. O processo consiste em duas etapas
principais:

1.  **Determinação do Número Ótimo de Clusters (k):** Para cada município com um 
    número suficiente de alunos, o script primeiro executa o algoritmo K-means 
    para uma gama de valores de `k`. A inércia (WCSS - Within-Cluster Sum of 
    Squares) de cada execução é registrada. Em seguida, a função `encontrar_cotovelo` 
    é usada para identificar o "ponto de cotovelo" na curva de inércia. Este ponto 
    representa um bom equilíbrio entre o número de clusters e a compactação 
    desses clusters, sendo escolhido como o número ideal de pontos de parada 
    para aquele município.

2.  **Geração dos Centroides e Cálculo de Demanda:** Com o número ótimo de 
    clusters (`k`) definido, o K-means é executado novamente para encontrar a 
    localização exata dos centroides (pontos de parada). Subsequentemente, 
    a demanda de alunos para cada ponto é calculada para cada dia da semana e 
    turno, com base nos dados de entrada.

O resultado final é um DataFrame do Pandas contendo as coordenadas geográficas 
de cada ponto de parada, o município ao qual pertence, o dia da semana e a 
demanda de alunos para os diferentes turnos, pronto para ser consumido pelo 
módulo de otimização de rotas.

Exemplo de Uso:
    Para gerar os pontos de parada para todos os alunos para o turno de saída:

    >>> from point_generation import gerar_pontos
    >>> df_pontos_onibus = gerar_pontos(alunos="full", turno="SAIDA")
    >>> print(df_pontos_onibus.head())

@author: Seu Nome (ou Nome da Equipe)
@date: 20/08/2025
"""

import pandas as pd
import numpy as np
from sklearn.cluster import k_means
import warnings
warnings.filterwarnings('ignore')
import matplotlib.pyplot as plt

def _exibir_grafico_cotovelo(
    k_valores: np.ndarray,
    inertias: np.ndarray,
    cotovelo_k: int,
    indice_cotovelo: int
) -> None:
    """Função auxiliar para exibir o gráfico do método do cotovelo.

    Esta função plota a curva de inércia (WCSS) em função do número de 
    clusters (k). Adicionalmente, desenha uma reta de referência conectando
    o primeiro e o último ponto da curva e uma linha perpendicular a esta 
    reta, passando pelo ponto identificado como o cotovelo, para ilustrar
    visualmente a seleção do `k` ótimo. O gráfico é salvo como uma imagem.

    Args:
        k_valores (np.ndarray): Um array contendo os valores de `k` (número
            de clusters) testados.
        inertias (np.ndarray): Um array contendo os valores de inércia (WCSS)
            correspondentes a cada valor em `k_valores`.
        cotovelo_k (int): O valor de `k` identificado como o cotovelo.
        indice_cotovelo (int): O índice do ponto de cotovelo nos arrays
            `k_valores` e `inertias`.
    """
    # Extrair as coordenadas do ponto do cotovelo
    inertias = inertias*10000
    # Extrair as coordenadas do ponto do cotovelo
    cotovelo_x = k_valores[indice_cotovelo]
    cotovelo_y = inertias[indice_cotovelo]

    #Definindo primeiro e último ponto da reta de referência
    x1, y1 = k_valores[0], inertias[0]
    x2, y2 = k_valores[-1], inertias[-1]

    # Definir o primeiro e último ponto para a reta de referência
    ponto_inicial = (x1, y1)
    ponto_final = (x2, y2)

    # Calcular a inclinação da reta de referência
    if x2 - x1 != 0:
        inclinacao_reta = (y2 - y1) / (x2 - x1)
    else:
        inclinacao_reta = np.inf  # Reta vertical

    # Calcular a inclinação da reta perpendicular (negativo do inverso)
    if inclinacao_reta != 0 and inclinacao_reta != np.inf:
        inclinacao_perpendicular = -1 / inclinacao_reta
    elif inclinacao_reta == 0:
        inclinacao_perpendicular = np.inf  # Perpendicular a uma reta horizontal é vertical
    else:
        inclinacao_perpendicular = 0     # Perpendicular a uma reta vertical é horizontal

    # Calcular um ponto para a reta perpendicular (usando o ponto do cotovelo)
    # A equação da reta é y - y1 = m(x - x1)
    # Para a perpendicular: y - cotovelo_y = inclinacao_perpendicular * (x - cotovelo_x)

    # Vamos definir um intervalo para a reta perpendicular para visualização
    intervalo_x = np.linspace(min(k_valores), max(k_valores), 100)
    if inclinacao_perpendicular != np.inf:
        reta_perpendicular_y = inclinacao_perpendicular * (intervalo_x - cotovelo_x) + cotovelo_y
    else:
        reta_perpendicular_y = np.linspace(min(inertias), max(inertias), 100)
        intervalo_x = np.full_like(reta_perpendicular_y, cotovelo_x)

    # Criar o gráfico
    plt.figure(figsize=(10, 6))

    # Plotar os pontos da curva de inércia
    plt.plot(k_valores, inertias, 'bo-', label='Curva de Inércia')

    # Plotar a reta entre o primeiro e o último ponto
    plt.plot([ponto_inicial[0], ponto_final[0]], [ponto_inicial[1], ponto_final[1]], 'r-', label='Reta de Referência')

    # Plotar o ponto do cotovelo com um marcador diferente
    plt.plot(cotovelo_x, cotovelo_y, 'go', markersize=10, label=f'Cotovelo (k={cotovelo_k})')

    # Plotar a reta perpendicular à reta de referência passando pelo cotovelo
    plt.plot(intervalo_x, reta_perpendicular_y, 'g--', label='Perpendicular no Cotovelo')

    # Adicionar rótulos e título
    plt.xlabel('Número de Clusters (k)')
    plt.ylabel('Inércia (WCSS) * 10^4')
    plt.legend(loc='center left')
    plt.grid(True)
    plt.xticks(k_valores)
    plt.legend(loc='lower center',ncol=4, fancybox=True, shadow=True, bbox_to_anchor=(0.5, -0.2))
    plt.tight_layout()

    # Ajustar os limites do eixo y para melhor visualização
    ax = plt.gca()
    ax.set_aspect('equal', 'box')
    amplitude_y = max(inertias) - min(inertias)
    ax.set_ylim(min(inertias) - 0.1 * amplitude_y, max(inertias) + 0.1 * amplitude_y)
    plt.savefig('imgs/ilustracao_cotovelo.png')

def encontrar_cotovelo(k_values, inertias, exibir_grafico=False):
    """Encontra o número ótimo de clusters (k) usando o método do cotovelo.

    Esta implementação do método do cotovelo (Kneedle) localiza o `k` ótimo
    identificando o ponto na curva de inércia que possui a maior distância
    perpendicular a uma reta traçada entre o primeiro e o último ponto da
    curva. Este ponto representa uma troca eficiente entre a redução da
    variância intra-cluster e o aumento da complexidade do modelo.

    Args:
        k_values (list | np.ndarray): Uma lista ou array com os valores de
            `k` (número de clusters) que foram testados.
        inertias (list | np.ndarray): Uma lista ou array com os valores de
            inércia (WCSS) correspondentes a cada valor de `k`.
        exibir_grafico (bool): Se `True`, gera e salva um gráfico que
            visualiza a curva de inércia e o ponto de cotovelo encontrado.
            O padrão é `False`.

    Returns:
        int: O valor de `k` considerado ótimo (o cotovelo).
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

    if exibir_grafico:
        _exibir_grafico_cotovelo(k_values, inertias, k_values[elbow_index], elbow_index)
        
    return k_values[elbow_index]

def gerar_pontos(alunos:str = "full", turno:str = "SAIDA"):
    """Gera pontos de parada de ônibus (centroides) a partir de dados dos alunos.

    A função orquestra o processo de criação de pontos de parada. Ela lê um
    arquivo CSV com informações dos alunos, incluindo suas coordenadas, e
    aplica o algoritmo K-means de forma iterativa por município. Para cada
    município, o número ideal de clusters é determinado pelo método do cotovelo.
    Em seguida, os centroides (pontos de parada) são gerados e a demanda de
    alunos para cada ponto é calculada para cada dia da semana e turno.
    Municípios com menos de 10 alunos são desconsiderados.

    Args:
        alunos (str): Identificador para filtrar os alunos. Se for "full",
            todos os alunos do arquivo de entrada são considerados. Caso
            contrário, pode ser uma substring para filtrar pelo `id_aluno`.
            O padrão é "full".
        turno (str): Especifica o turno a ser considerado para o cálculo da
            demanda, tipicamente "ENTRADA" ou "SAIDA". O valor é usado para
            selecionar as colunas de demanda correspondentes (ex: `TURNO_SAIDA`).
            O padrão é "SAIDA".

    Returns:
        pd.DataFrame: Um DataFrame contendo os pontos de ônibus gerados, com
            as seguintes colunas: 'lon', 'lat' (coordenadas), 'cd_municipio',
            'demanda_manha', 'demanda_tarde', 'demanda_noite', 'demanda_fim'
            e 'dia'.
    """
    print(alunos,turno)
    # Carrega o dataframe contendo informações dos alunos
    df_alunos = pd.read_csv("data/info_alunos.csv")
    # df_turno_correto = pd.read_csv("dados_tratados/turno_resumo.csv",sep = ';')
    # df_alunos = df_alunos.drop(columns=['TURNO_ENTRADA','TURNO_SAIDA'])
    # df_alunos = df_alunos.merge(df_turno_correto,'left',on=['CURSO','PERÍODO_ATUAL','DIA'])
    if alunos != "full":
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
        # Filtra o dataframe para conter apenas os alunos do município atual e remove duplicatas de alunos
        alunos_municipio = df_alunos[(df_alunos['CIDADE'] == cd_mun)].drop_duplicates(subset='id_aluno')
        # Verifica se o número de alunos no município é menor que 10

        if len(alunos_municipio) < 10:
            # Incrementa o contador de municípios desconsiderados
            municipios_desconsiderados += 1
            # Incrementa o contador de alunos desconsiderados
            alunos_desconsiderados += len(alunos_municipio)
            # Imprime uma mensagem indicando que o município foi pulado devido ao baixo número de alunos
            # print('Município:', cd_mun, "N Alunos:", len(alunos_municipio), "PULADO")
            # Pula para a próxima iteração do loop (próximo município)
            continue
        # Imprime o nome do município e o número de alunos considerados para este município
        print('Município:', cd_mun, "N Alunos:", len(alunos_municipio))

         # Inicializa uma lista vazia para armazenar os valores de WCSS (Within-Cluster Sum of Squares)
        wcss = []
        # Loop para calcular a inércia (WCSS) para diferentes números de clusters (k)
        for i in range(2,len(alunos_municipio)+1):
            # Aplica o algoritmo k-means para o número de clusters 'i' nas coordenadas de latitude e longitude dos alunos
            centroids, classes, inertia = k_means(alunos_municipio[['LATITUDE','LONGITUDE']],i, n_init=10) # Adicionado n_init para melhor convergência
            # Adiciona o valor da inércia à lista wcss
            wcss.append(inertia)

        # Chama a função para encontrar o número ótimo de clusters (o "cotovelo") usando os valores de k e as inércias
        optimal_k = encontrar_cotovelo(range(2,len(alunos_municipio)+1), wcss,False)

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
            demanda_manha = comp_df[(comp_df[f'TURNO_{turno}']=='manhã') & cond_dia].groupby('class').count()[f'TURNO_{turno}']
            demanda_tarde = comp_df[(comp_df[f'TURNO_{turno}']=='tarde') & cond_dia].groupby('class').count()[f'TURNO_{turno}']
            demanda_noite = comp_df[(comp_df[f'TURNO_{turno}']=='noite') & cond_dia].groupby('class').count()[f'TURNO_{turno}']
            demanda_fim = comp_df[(comp_df[f'TURNO_{turno}']=='fim') & cond_dia].groupby('class').count()[f'TURNO_{turno}']

            # Adiciona as informações de demanda (se houver) ao dataframe de centroids, usando o índice do cluster como chave
            centroids_df.loc[demanda_manha.index,'demanda_manha'] = demanda_manha
            centroids_df.loc[demanda_tarde.index,'demanda_tarde'] = demanda_tarde
            centroids_df.loc[demanda_noite.index,'demanda_noite'] = demanda_noite
            centroids_df.loc[demanda_fim.index,'demanda_fim'] = demanda_fim
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

    #pontos_de_onibus.to_csv(f"data/pontos_de_onibus_{alunos}_{turno}.csv",index=False)

    # Retorna o dataframe final de pontos de ônibus
    return pontos_de_onibus