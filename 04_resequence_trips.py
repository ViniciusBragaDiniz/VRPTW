"""Módulo de pós-processamento para minimização de veículos em rotas de VRPTW.

Este script é projetado para ser executado após a geração de uma solução inicial
para o Problema de Roteamento de Veículos com Janelas de Tempo (VRPTW) por um
modelo principal (ex: `model.py`). Sua principal finalidade é otimizar o número
de veículos utilizados, focando em viagens que foram atribuídas a múltiplos
veículos.

O algoritmo funciona da seguinte maneira:
1.  Carrega as soluções de rotas de entrada e saída, que contêm informações
    detalhadas sobre cada parada, veículo atribuído e tempos de viagem.
2.  Identifica "viagens" únicas, definidas por uma combinação de tipo (entrada/saída),
    instância, dia, turno e município.
3.  Para cada viagem que utiliza mais de um veículo, o script tenta encontrar
    uma nova combinação de rotas (um "re-sequenciamento") que possa ser
    atendida por um número menor de veículos.
4.  Isso é feito gerando todas as partições matemáticas possíveis do conjunto
    de tempos de viagem das rotas originais daquela viagem. Cada subconjunto
    em uma partição representa uma nova rota consolidada para um único veículo.
5.  Cada partição é então validada contra uma restrição de tempo de trabalho
    (neste caso, 4 horas por veículo). A primeira partição válida encontrada
    que utiliza o menor número de veículos (ou seja, o menor número de
    subconjuntos) é adotada.
6.  A solução final, com o número de veículos ajustado, é salva em um novo
    arquivo CSV.

Exemplo de uso:
    Este script é tipicamente executado como um processo autônomo após a
    execução do modelo principal de roteamento.

    $ python minimizar_veiculos.py

@author: Vinícius Braga Diniz (contato.vbd@gmail.com)
"""
import pandas as pd

def gerar_particoes(lista: list) -> list:
    """Gera recursivamente todas as partições possíveis de uma lista.

    Uma partição de um conjunto é uma forma de agrupá-lo em subconjuntos não vazios,
    de tal forma que cada elemento do conjunto original pertença a exatamente um
    desses subconjuntos. Esta função implementa um algoritmo recursivo clássico
    para encontrar todas essas partições.

    O processo funciona da seguinte forma:
    - O caso base é uma lista com um único elemento, cuja única partição é a
      própria lista dentro de outra lista (ex: `[[elemento]]`).
    - Para listas maiores, o primeiro elemento é separado, e as partições do
      restante da lista são geradas recursivamente. Em seguida, o primeiro
      elemento é combinado com essas partições de duas maneiras:
      1. Adicionando-o a cada um dos subconjuntos existentes em cada partição.
      2. Criando um novo subconjunto contendo apenas ele e adicionando-o a
         cada partição.

    Args:
        lista (List[Any]): A lista de elementos a ser particionada. Os elementos
            podem ser de qualquer tipo.

    Returns:
        List[List[List[Any]]]: Uma lista contendo todas as partições possíveis.
            Cada partição é uma lista de subconjuntos, onde cada subconjunto
            é também uma lista.
            Exemplo: para `[1, 2]`, o retorno seria `[[[2, 1]], [[1], [2]]]`.
    """
    if len(lista) == 1:
        return [[lista]]  # Apenas uma partição possível para uma lista de tamanho 1

    resultado = []
    primeiro_elemento = lista[0]
    for particao in gerar_particoes(lista[1:]):  # Partições do restante da lista
        # Adicionar o primeiro elemento a cada subconjunto existente
        for i in range(len(particao)):
            nova_particao = [subconjunto[:] for subconjunto in particao]
            nova_particao[i].append(primeiro_elemento)
            resultado.append(nova_particao)
        # Criar uma nova partição onde o primeiro elemento é um subconjunto separado
        resultado.append([[primeiro_elemento]] + particao)
    return resultado

solucao_entrada = pd.read_csv('output/csv/solucao_completa_cvrptw_full_ENTRADA.csv')
solucao_entrada['tipo_de_rota'] = 'ENTRADA'
solucao_saida = pd.read_csv('output/csv/solucao_completa_cvrptw_full_SAIDA.csv')
solucao_saida['tipo_de_rota'] = 'SAIDA'

solucao_completa = pd.concat([solucao_entrada, solucao_saida], ignore_index=True)
solucao_ajustada = solucao_completa.groupby(by=['tipo_de_rota','instancia','dia','turno','cd_municipio'])[['id_veiculo','tempo_viagem']].agg({"id_veiculo":["nunique"],"tempo_viagem":["sum"]})

viagens = solucao_completa[["tipo_de_rota","instancia","dia","turno","cd_municipio"]].drop_duplicates()
solucao_completa = solucao_completa.set_index(["tipo_de_rota",'instancia','dia','turno','cd_municipio'])
for _, colunas in viagens.iterrows():
    viagem = solucao_completa.loc[tuple(colunas)]
    if viagem['id_veiculo'].nunique() == 1:
        continue

    # Gerar todas as partições únicas
    particoes = gerar_particoes(viagem['tempo_viagem'].to_list())

    # Exibir as partições
    for i, particao in enumerate(particoes, 1):
        valido = True
        for subparticao in particao:
            valido = valido & (sum(subparticao) <= 4*3600)
        if valido:
            solucao_ajustada.loc[tuple(colunas),'id_veiculo'] = len(particao)
            break

solucao_ajustada = solucao_ajustada.reset_index()
solucao_ajustada.to_csv("output/csv/solucao_ajustada.csv",index=False)