#!/usr/bin/env python
# coding: utf-8

# In[1]:


import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import numpy as np
import math
import requests
from time import sleep


# In[2]:


import pandas as pd
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter


# In[3]:


from googlemaps import Client as GoogleMaps
import googlemaps
import gmaps


# In[4]:


gmaps = googlemaps.Client(key='AIzaSyBJ-Ql1VTbkMWEEHvYTj-iTeMz4WxALyJg')


# In[5]:


def build_address(row):
    address = []
    for value in row:
        if (value != "") and (isinstance(value,str)):
            address.append(value)
    address.append("Rio de Janeiro")
    address.append("Brasil")
    return ", ".join(address)   


# ## Médio

# In[6]:


df_tec = pd.read_csv("Dados/turno_medio.csv")


# In[7]:


df_medio = pd.read_csv('Dados/info_medio.csv')


# In[8]:


ceps_rj = df_medio["CEP"].apply(lambda x: str(x)[0] == '2')
print(f"CEPS Inválidos {len(df_medio) - sum(ceps_rj)}")
df_medio = df_medio.loc[ceps_rj].reset_index(drop=True)


# In[9]:


df_medio['CURSO'] = df_medio['CURSO'].str.replace('CURSO TÉCNICO DE ','')
df_medio['CURSO'] = df_medio['CURSO'].str.replace(' INTEGRADO AO ENSINO MÉDIO','')


# In[10]:


if "COMPLEMENTO" not in df_medio.columns:
    df_medio["COMPLEMENTO"] = ""
else:
    df_medio["COMPLEMENTO"].fillna("",inplace=True)
if "LOGRADOURO" not in df_medio.columns:
    df_medio["LOGRADOURO"] = ""
else:
    df_medio["LOGRADOURO"].fillna("",inplace=True)


# In[11]:


empty_idx = df_medio[df_medio["LOGRADOURO"] == ""].index
for idx in empty_idx:
    CEP = df_medio.loc[idx, "CEP"]
    # CEP a ser consultado (remova traços, se necessário)
    url = f"https://viacep.com.br/ws/{CEP}/json/"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            dados = response.json()
            df_medio.loc[idx,"LOGRADOURO"] = dados.get("logradouro")
            df_medio.loc[idx,"COMPLEMENTO"] = dados.get("complemento")
        else:
            print(idx,"Erro ao consultar o CEP")
    except Exception as e:
        print("Erro ao consultar o CEP ",str(e))
    sleep(0.5)


# In[12]:


#Faz o georreferenciamento dos endereços dos alunos
df_medio["ENDERECO_COMPLETO"] = df_medio[["LOGRADOURO","BAIRRO","CIDADE","CEP","COMPLEMENTO"]].apply(lambda x: build_address(x),axis=1)


if "LONGITUDE" not in df_medio.columns:
    df_medio["LONGITUDE"] = 0
else:
    df_medio["LONGITUDE"].fillna(0,inplace=True)
    
if "LATITUDE" not in df_medio.columns:
    df_medio["LATITUDE"] = 0
else:
    df_medio["LATITUDE"].fillna(0,inplace=True)

empty_idx = df_medio[df_medio['LATITUDE'] == 0].index

line = 0
for address in df_medio["ENDERECO_COMPLETO"]:
    
    if line not in empty_idx:
        continue
        
    geocode_result = gmaps.geocode(address)
    df_medio.loc[line,'LATITUDE'] = geocode_result[0]['geometry']['location'] ['lat']
    df_medio.loc[line, 'LONGITUDE'] = geocode_result[0]['geometry']['location']['lng']
    line +=1
    if line%10 == 0:
        print(line)


# In[13]:


df_medio.to_csv("Dados/info_medio.csv",index=False)


# In[14]:


df_medio['id_aluno'] = 'tec_'+df_medio.index.astype(str)


# In[15]:


df_medio = pd.merge(df_medio,df_tec,'left',['CURSO','PERÍODO_ATUAL'])


# ## Graduação

# In[16]:


#Leitura dos dados de turno para cada curso
df_emec = pd.read_csv("Dados/turno_emec.csv")
df_epro = pd.read_csv("Dados/turno_epro.csv")
df_enca = pd.read_csv("Dados/turno_enca.csv")
df_grad = pd.concat([df_emec,df_epro,df_enca], ignore_index=True)


# In[17]:


de_para_saida = {'manhã':'tarde','tarde':'noite','noite':'fim'}
df_grad['TURNO_SAIDA'] = df_grad['TURNO'].map(de_para_saida)


# In[18]:


df_grad.to_excel('Dados/df_grad.xlsx')


# In[19]:


df_graduacao = pd.read_csv('Dados/info_graduacao.csv')

df_graduacao['CURSO'] = df_graduacao['CURSO'].str.replace('CURSO DE ','')

if "COMPLEMENTO" not in df_graduacao.columns:
    df_graduacao["COMPLEMENTO"] = ""
else:
    df_graduacao["COMPLEMENTO"].fillna("",inplace=True)
    
if "LOGRADOURO" not in df_graduacao.columns:
    df_graduacao["LOGRADOURO"] = ""
else:
    df_graduacao["LOGRADOURO"].fillna("",inplace=True)


# In[20]:


ceps_rj = df_graduacao["CEP"].apply(lambda x: str(x)[0] == '2')
print(f"CEPS Inválidos {len(df_graduacao) - sum(ceps_rj)}")
df_graduacao = df_graduacao.loc[ceps_rj].reset_index(drop=True)


# In[21]:


empty_idx = df_graduacao[df_graduacao["LOGRADOURO"] == ""].index

for idx in empty_idx:
    CEP = df_graduacao.loc[idx, "CEP"]
    # CEP a ser consultado (remova traços, se necessário)
    url = f"https://viacep.com.br/ws/{CEP}/json/"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            dados = response.json()
            df_graduacao.loc[idx,"LOGRADOURO"] = dados.get("logradouro")
            df_graduacao.loc[idx,"COMPLEMENTO"] = dados.get("complemento")
        else:
            print(idx, "Erro ao consultar o CEP")
    except Exception as e:
        print("Erro ao consultar o CEP ",str(e))
    sleep(0.5)
df_graduacao.to_excel('Dados/lista_graduacao.xlsx',index=False)


# In[22]:


#Faz o georreferenciamento dos endereços dos alunos
df_graduacao["ENDERECO_COMPLETO"] = df_graduacao[["LOGRADOURO","BAIRRO","CIDADE","CEP","COMPLEMENTO"]].apply(lambda x: build_address(x),axis=1)


if "LONGITUDE" not in df_graduacao.columns:
    df_graduacao["LONGITUDE"] = 0
else:
    df_graduacao["LONGITUDE"].fillna(0,inplace=True)
    
if "LATITUDE" not in df_graduacao.columns:
    df_graduacao["LATITUDE"] = 0
else:
    df_graduacao["LATITUDE"].fillna(0,inplace=True)

empty_idx = df_graduacao[df_graduacao['LATITUDE'] == 0].index


# In[23]:


empty_idx


# In[24]:


line = 0
for address in df_graduacao["ENDERECO_COMPLETO"]:
    
    if line not in empty_idx:
        continue
        
    geocode_result = gmaps.geocode(address)
    df_graduacao.loc[line,'LATITUDE'] = geocode_result[0]['geometry']['location'] ['lat']
    df_graduacao.loc[line, 'LONGITUDE'] = geocode_result[0]['geometry']['location']['lng']
    line +=1
    if line%10 == 0:
        print(line)


# In[25]:


df_graduacao.to_csv("Dados/info_graduacao.csv",index=False)


# In[26]:


df_graduacao['id_aluno'] = 'grad_'+df_graduacao.index.astype(str)


# In[27]:


df_graduacao = pd.merge(df_graduacao,df_grad,'left',['CURSO','PERÍODO_ATUAL'])


# ## Agrupamento Geral

# In[28]:


import unicodedata

def remover_acentos(texto):
    #Normaliza o texto para a forma de decomposição
    texto_normalizado = unicodedata.normalize('NFD',texto)
    #Filtra os caracteres, removendo os acentuados
    texto_sem_acento = ''.join(c for c in texto_normalizado if unicodedata.category(c) != "Mn")
    return texto_sem_acento


# In[29]:


df_alunos = pd.concat([df_medio,df_graduacao],ignore_index=True)


# In[30]:


df_alunos['CIDADE'] = df_alunos['CIDADE'].apply(lambda x: remover_acentos(x).title())
df_alunos['BAIRRO'] = df_alunos['BAIRRO'].apply(lambda x: remover_acentos(x).title())


# In[31]:


df_alunos.to_csv("Dados/info_alunos.csv",index=False)


# In[32]:


df_medio


# In[ ]:




