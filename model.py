import pandas as pd
from docplex.mp.model import Model
from docplex.mp.linear import LinearExpr
import time
import math

from point_generation import gerar_pontos
from aux_functions import haversine, data_prep, build_routes
from build_model import build_model, operate_cycle
depot = 0


tempo_preparo = 0
tempo_entrega = 3.5*3600
fatia_tempo = 1800 #30 minutos
instancias = {}
for instancia in ["tec","grad","full"]:
	try:
		instancias[instancia] = pd.read_csv(f'Dados/pontos_de_onibus_{instancia}.csv')
	except FileNotFoundError:
		instancias[instancia] = gerar_pontos(instancia)


capacity = 50 #Capacidade do ônibus

for instancia in instancias:

	for dia in ['seg','ter','qua','qui','sex','sab']:	

		#Linha que vai representar o CEFET no modelo
		cefet = {'lat':[-43.46242373123213],
					'lon':[-22.704575111343242],
					'demanda_manha':[0],
					'demanda_tarde':[0],
					'demanda_noite':[0],
					'tempo_preparo':tempo_preparo,
					'tempo_entrega':tempo_entrega,
					'cd_municipio':'CEFET',
					'dia':dia}
			
		for turno in ['manha','tarde', 'noite']:

			output_file = open(f'saida_cvrptw_{instancia}.txt','w')
			output_file.writelines(f"Horizonte de Tempo: {tempo_entrega-tempo_preparo} segundos\n\n")
			output_file.writelines("##############################\n")
			output_file.writelines(f"####  Turno Atual: {turno}  ####\n")
			output_file.writelines("##############################\n\n")

			#Lê os dados do dia atual 
			dados_modelo = instancias[instancia]
			dados_modelo = dados_modelo[dados_modelo['dia'] == dia].reset_index(drop=True)
			dados_modelo = dados_modelo[dados_modelo['demanda_'+turno] > 0].reset_index(drop=True)

			dados_modelo = dados_modelo.reset_index(names='id') 
				
			dados_modelo['tempo_preparo'] = tempo_preparo # 6 horas da manhã
			dados_modelo['tempo_entrega'] = tempo_entrega # 8 horas da manhã
			
			#Inclui o CEFET como primeira Linha
			dados_modelo = pd.concat([pd.DataFrame.from_dict(cefet),dados_modelo],ignore_index=True)

			#Matriz de Distância
			distancia = [[0 for _ in range(len(dados_modelo))] for _ in range(len(dados_modelo))]

			comeco_horizonte = dados_modelo['tempo_preparo'][depot] # Quando o dia Começa
			fim_horizonte = dados_modelo['tempo_entrega'][depot]    # Quando o dia Termina

			dados_modelo = data_prep(turno, dados_modelo, capacity)

			for cd_municipio in dados_modelo['cd_municipio'].unique():
				if cd_municipio != 'Rio De Janeiro':
					continue
				if cd_municipio == 'CEFET':
					continue

				for iteracao in range(dados_modelo['iteracao'].max()):

					s = f"|Iteração{iteracao}, Horário de Saída: {tempo_preparo+fatia_tempo*iteracao}|"
					output_file.writelines("_"*len(s)+"\n")
					output_file.writelines(s+"\n")
					output_file.writelines("|"+"_"*(len(s)-2)+"|\n\n")
					output_file.writelines(cd_municipio+"\n")
					
					print("#"*8)
					print("Iteração "+str(iteracao),"Município "+str(cd_municipio))
					dados_municipio = dados_modelo[dados_modelo['iteracao'] == iteracao]
					
					dados_municipio = dados_municipio[dados_municipio['cd_municipio'].isin([cd_municipio,'CEFET'])].reset_index(drop=True)
					
					big_m = -1 # Maior valor possível
					for i in range(len(dados_municipio)):
						for j in range(len(dados_municipio)):
							if i != j:
								#Distância em Metros
								distancia[i][j]=round(haversine(dados_municipio['lat'][i],dados_municipio['lon'][i],
																dados_municipio['lat'][j],dados_municipio['lon'][j]))
								#Assumindo Velocidade Média de 20 km/h se for Nova Iguaçu
								if cd_municipio == "Nova Iguaçu":
									distancia[i][j] = distancia[i][j]/(20/3.6) #Calculo do tempo em segundos
								else: #Para fora assume-se 60 km/h
									distancia[i][j] = distancia[i][j]/(60/3.6) #Calculo do tempo em segundos
								
								big_m = max(big_m,dados_municipio['tempo_entrega'][i]+distancia[i][j]-(dados_municipio['tempo_preparo'][i]+fatia_tempo*iteracao))
							else: 
								distancia[i][j]=float('inf')

					########################
					#Parâmetros Calculáveis#
					########################
					num_spots = len(dados_municipio) #Número de Pontos de Ônibus
					necessary_vehicles = math.ceil(dados_municipio['demanda_'+turno].sum()/capacity) #Número de veículos = demanda dividada por capacidade
					
					if num_spots == 0: #Se N == 0 é porque não tem mais demanda
						print("Não tem demanda nessa iteração")
						output_file.writelines("Não tem demanda nessa iteração\n\n")
						continue

					output_file.writelines(f"Veículos Disponíveis {necessary_vehicles}, Pontos de Ônibus com Demanda {num_spots}\n\n")

					#Criação do modelo
					model = Model("vrptw")
					print(dia, turno, instancia, necessary_vehicles,num_spots)

					model_data = {
						'data': dados_municipio,
						'num_spots': num_spots,
						'necessary_vehicles': necessary_vehicles,
						'capacity': capacity,
						'iteracao': iteracao,
						'fatia_tempo': fatia_tempo,
						'turno': turno,
						'distancia': distancia,
						'big_m': big_m,
						'depot': depot,
					}

					model, travels = build_model(model, model_data)

					start = time.time() #Tempo de ínicio
					subcicle = True     #Condição de parada
					#Assumindo que existe subciclos, nós...
					while subcicle == True: 

						#Solução VRP - Dicionário Desordenado
						_Solution = model.solve(log_output=False).as_dict()
						routes = build_routes(_Solution, necessary_vehicles)
						summ = 0 # Condição de parada

						for k in range(necessary_vehicles):

							# Percorre a rota do veículo k como
							# uma lista encadeada
							if len(routes[k]) > 0:

								actual_node = routes[k].pop(0)
								while actual_node !=0:
									actual_node = routes[k].pop(actual_node)

							# Número de nós restantes na rota
							summ += len(routes[k]) 
							
							# Se houver nós restantes na rota, significa que
							# existem subciclos na rota do veículo k.
							if len(routes[k]) >0:
								operate_cycle(model, routes, travels, k, option="cut")
									
						if summ == 0:
							subcicle = False
							routes = build_routes(_Solution, necessary_vehicles)

							output_file.writelines(f"Solução:\n")

							for k in range(necessary_vehicles):
								
								string = operate_cycle(model, routes, travels, k, option="string", tempo_preparo=tempo_preparo, iteracao=iteracao, distancia=distancia)
								output_file.writelines(string)
								print(string)
							
					tempo_exec = time.time()-start
					output_file.writelines("Custo da Função Objetiva: "+str(model.objective_value)+"\n")
					output_file.writelines("Tempo Total de Execução: "+str(tempo_exec)+"\n")
					output_file.writelines("\n\n")
					print("Custo da Função Objetiva",model.objective_value)
					print("Tempo Total de Execução", tempo_exec)
	output_file.close()
