import pandas as pd

solucao_entrada = pd.read_csv('output/csv/solucao_completa_cvrptw_full_ENTRADA.csv')
solucao_entrada['tipo_de_rota'] = 'ENTRADA'
solucao_saida = pd.read_csv('output/csv/solucao_completa_cvrptw_full_SAIDA.csv')
solucao_saida['tipo_de_rota'] = 'SAIDA'

solucao_completa = pd.concat([solucao_entrada, solucao_saida], ignore_index=True)
solucao_ajustada = solucao_completa.groupby(by=['tipo_de_rota','instancia','dia','turno','cd_municipio'],as_index=False)[['id_veiculo','tempo_viagem']].agg({"id_veiculo":["nunique"],"tempo_viagem":["sum"]})
solucao_ajustada['tempo_total'] = solucao_ajustada['tempo_viagem']<4*3600
for idx,row in solucao_ajustada.iterrows():
    if solucao_ajustada.loc[idx,'tempo_total'].values[0]:
        solucao_ajustada.loc[idx,'id_veiculo'] = 1
solucao_ajustada.to_csv("output/csv/solucao_ajustada.csv",index=False)