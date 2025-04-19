import numpy as np
import pandas as pd
import plotly.express as px
from sklearn.cluster import k_means
import time as temporizador
import warnings
import matplotlib.pyplot as plt
import seaborn as sns
import math
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


df_alunos = pd.read_csv("Dados/info_alunos.csv")
#df_alunos = df_alunos[df_alunos['id_aluno'].str.contains('tec')] #Filtra apenas alunos do técnico
#df_alunos = df_alunos[df_alunos['id_aluno'].str.contains('grad')] #Filtra apenas alunos da graduação


municipios = df_alunos.CIDADE.unique()
dias_da_semana = df_alunos.DIA.unique()

# Iterar para cada município
fig = plt.Figure()
pontos_de_onibus = []

municipios_desconsiderados = 0
alunos_desconsiderados = 0

for cd_mun in municipios:
    start = temporizador.time()
    alunos_municipio = df_alunos[(df_alunos['CIDADE'] == cd_mun)].drop_duplicates(subset='id_aluno')
    if len(alunos_municipio) < 10:
        municipios_desconsiderados += 1
        alunos_desconsiderados += len(alunos_municipio)
        print('Município:', cd_mun, "N Alunos:", len(alunos_municipio), "PULADO")
        continue
    
    print('Município:', cd_mun, "N Alunos:", len(alunos_municipio))

    CLUSTERS = 20
    wcss = [] 
    for i in range(2,len(alunos_municipio)+1):
        centroids, classes, inertia = k_means(alunos_municipio[['LATITUDE','LONGITUDE']],i)
        wcss.append(inertia)
    optimal_k = encontrar_cotovelo(range(2,len(alunos_municipio)+1), wcss)
    
    centroids, classes, _ = k_means(alunos_municipio[['LATITUDE','LONGITUDE']],optimal_k)

    #alunos
    alunos_municipio['class'] = classes
    comp_df = df_alunos.merge(alunos_municipio[['id_aluno','class']],'left','id_aluno')
    for dia in dias_da_semana:
        print('#'*22)
        centroids_df = pd.DataFrame(centroids,columns=['lon','lat'])
        centroids_df['cd_municipio'] = cd_mun
        cond_dia = comp_df['DIA'] == dia
        
        demanda_manha = comp_df[(comp_df['TURNO']=='manhã') & cond_dia].groupby('class').count()['TURNO']
        demanda_tarde = comp_df[(comp_df['TURNO']=='tarde') & cond_dia].groupby('class').count()['TURNO']
        demanda_noite = comp_df[(comp_df['TURNO']=='noite') & cond_dia].groupby('class').count()['TURNO']
        
        centroids_df.loc[demanda_manha.index,'demanda_manha'] = demanda_manha
        centroids_df.loc[demanda_tarde.index,'demanda_tarde'] = demanda_tarde
        centroids_df.loc[demanda_noite.index,'demanda_noite'] = demanda_noite
        centroids_df['dia'] = dia
        
        centroids_df.fillna(0,inplace=True)
        pontos_de_onibus.append(centroids_df)

pontos_de_onibus = pd.concat(pontos_de_onibus,ignore_index=True)

print("Municipios Desconsiderados", municipios_desconsiderados)
print("Alunos Desconsiderados", alunos_desconsiderados)


#pontos_de_onibus.to_csv("Dados/pontos_de_onibus_tec.csv")
#pontos_de_onibus.to_csv("Dados/pontos_de_onibus_grad.csv")
pontos_de_onibus.to_csv("Dados/pontos_de_onibus.csv")

