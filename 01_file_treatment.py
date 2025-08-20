"""
Este módulo é responsável pela etapa inicial de tratamento dos dados brutos
dos alunos dos cursos de nível médio e graduação. O processo consiste em
carregar as informações de diferentes fontes, consolidá-las, limpar os dados,
enriquecê-los com informações de endereço via API (ViaCEP) e, finalmente,
obter as coordenadas geográficas (latitude e longitude) de cada aluno
utilizando a API do Google Maps.

O fluxo de trabalho do script é o seguinte:
1.  Carrega os dados dos alunos (médio e graduação) de arquivos CSV.
2.  Unifica os dois conjuntos de dados em um único DataFrame.
3.  Realiza uma limpeza inicial, filtrando por CEPs válidos do estado do
    Rio de Janeiro e inicializando colunas que serão usadas posteriormente
    para evitar erros em reprocessamentos.
4.  Utiliza a API do ViaCEP para preencher informações de logradouro e
    complemento que estejam ausentes, com base no CEP do aluno.
5.  Constrói um endereço completo e padronizado para cada aluno.
6.  Envia o endereço completo para a API de Geocodificação do Google Maps
    para obter a latitude e a longitude. O script é otimizado para
    processar apenas os alunos que ainda não foram georreferenciados.
7.  Padroniza os nomes de cidades e bairros, removendo acentos e
    aplicando formatação de título.
8.  Mescla o DataFrame resultante com informações sobre os turnos de cada curso.
9.  Salva os dados processados, dividindo-os novamente em arquivos para
    nível médio e graduação, sobrescrevendo os originais.

Este pré-processamento é fundamental para a subsequente aplicação dos
algoritmos de roteamento de veículos, que dependem de coordenadas precisas
para a construção de matrizes de custo e otimização das rotas.

Exemplo de uso:
    A execução deste script é direta. Certifique-se de que os arquivos de
    entrada ('data/info_medio.csv', 'data/info_graduacao.csv',
    'dados_tratados/turno_resumo.csv') e o arquivo de segredos ('secrets')
    estejam no local correto e execute:

    $ python 01_file_treatment.py

@author: Vinícius Braga Diniz (contato.vbd@gmail.com)
"""

import pandas as pd
import requests
from time import sleep
import unicodedata
import pandas as pd
import googlemaps
import os

######################
# Funções auxiliares #
######################
def build_address(row):
    address = []
    for value in row:
        if (value != "") and (isinstance(value,str)):
            address.append(value)
    address.append("Rio de Janeiro")
    address.append("Brasil")
    return ", ".join(address)   

def remover_acentos(texto):
    #Normaliza o texto para a forma de decomposição
    texto_normalizado = unicodedata.normalize('NFD',texto)
    #Filtra os caracteres, removendo os acentuados
    texto_sem_acento = ''.join(c for c in texto_normalizado if unicodedata.category(c) != "Mn")
    return texto_sem_acento

###############################
# Configuração do Google Maps #
###############################
with open("secrets",'r') as f:
    lines = f.read().splitlines()

for line in lines:
    key, value = line.split("=")
    os.environ[key] = value

gmaps = googlemaps.Client(key=os.getenv("GOOGLEMAPS_APIKEY"))

###################################
# Tratamento dos dados dos alunos #
###################################

# Leitura dos dados de turno para cada curso
df_turno = pd.read_csv('dados_tratados/turno_resumo.csv', sep = ";")

df_medio = pd.read_csv('data/info_medio.csv')
df_medio['id_aluno'] = 'tec_'+df_medio.index.astype(str)

df_graduacao = pd.read_csv('data/info_graduacao.csv')
df_graduacao['id_aluno'] = 'grad_'+df_graduacao.index.astype(str)

df_alunos = pd.concat([df_medio,df_graduacao],ignore_index=True)

# Verifica por CEPS fora do Rio de Janeiro
ceps_rj = df_alunos["CEP"].apply(lambda x: str(x)[0] == '2')
print(f"CEPS Inválidos {len(df_alunos) - sum(ceps_rj)}")
df_alunos = df_alunos.loc[ceps_rj].reset_index(drop=True)

# As condições abaixo previnem que o georreferenciamento reprocesse
# os endereços que já foram processados anteriormente

if "COMPLEMENTO" not in df_alunos.columns:
    df_alunos["COMPLEMENTO"] = ""
else:
    df_alunos["COMPLEMENTO"] = df_alunos["COMPLEMENTO"].fillna("")

if "LOGRADOURO" not in df_alunos.columns:
    df_alunos["LOGRADOURO"] = ""
else:
    df_alunos["LOGRADOURO"] = df_alunos["LOGRADOURO"].fillna("")

if "LONGITUDE" not in df_alunos.columns:
    df_alunos["LONGITUDE"] = 0
else:
    df_alunos["LONGITUDE"] = df_alunos["LONGITUDE"].fillna(0)
    
if "LATITUDE" not in df_alunos.columns:
    df_alunos["LATITUDE"] = 0
else:
    df_alunos["LATITUDE"] = df_alunos["LATITUDE"].fillna(0)


################################################
# BUSCA INFORMAÇÕES ADICIONAIS A PARTIR DO CEP #
################################################
empty_idx = df_alunos.loc[df_alunos["LOGRADOURO"] == ""].index
ceps_nao_encontrados = 0

for idx in empty_idx:
    CEP = df_alunos.loc[idx, "CEP"]
    # CEP a ser consultado (remova traços, se necessário)
    url = f"https://viacep.com.br/ws/{CEP}/json/"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            dados = response.json()
            df_alunos.loc[idx,"LOGRADOURO"] = dados.get("logradouro")
            df_alunos.loc[idx,"COMPLEMENTO"] = dados.get("complemento")
        else:
            print(idx,"Erro ao consultar o CEP")
            ceps_nao_encontrados += 1
    except Exception as e:
        print("Erro ao consultar o CEP ",str(e))
        ceps_nao_encontrados += 1
    sleep(0.5)

print(f"CEPS não encontrados {ceps_nao_encontrados}")

#######################
# GEORREFERENCIAMENTO #
#######################
df_alunos["ENDERECO_COMPLETO"] = df_alunos[["LOGRADOURO","BAIRRO","CIDADE","CEP","COMPLEMENTO"]].apply(lambda x: build_address(x),axis=1)

# Lista de alunos sem geolocalização
empty_idx = df_alunos[df_alunos['LATITUDE'] == 0].index

line = 0
for address in df_alunos["ENDERECO_COMPLETO"]:
    
    if line not in empty_idx:
        line +=1
        continue
        
    geocode_result = gmaps.geocode(address)
    df_alunos.loc[line,'LATITUDE'] = geocode_result[0]['geometry']['location'] ['lat']
    df_alunos.loc[line, 'LONGITUDE'] = geocode_result[0]['geometry']['location']['lng']
    line +=1
    if line%10 == 0:
        print(line)

df_alunos['CIDADE'] = df_alunos['CIDADE'].apply(lambda x: remover_acentos(x).title())
df_alunos['BAIRRO'] = df_alunos['BAIRRO'].apply(lambda x: remover_acentos(x).title())

# Merge com a base de turnos
df_alunos = df_turno.merge(df_alunos,'left',on=['CURSO','PERÍODO_ATUAL'])
df_alunos.to_csv("data/info_alunos.csv",index=False)

# Sobrescreve o arquivo com os dados de alunos
df_medio = df_alunos.loc[df_alunos['id_aluno'].str.contains('tec')]
df_medio = df_medio.drop_duplicates(subset='id_aluno')
df_medio.to_csv('data/info_medio.csv',index=False)

df_graduacao = df_alunos.loc[df_alunos['id_aluno'].str.contains('grad')]
df_graduacao = df_graduacao.drop_duplicates(subset='id_aluno')
df_graduacao.to_csv('data/info_graduacao.csv',index=False)

