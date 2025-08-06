import pandas as pd

def gerar_particoes(lista):
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