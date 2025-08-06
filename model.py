import pandas as pd
from docplex.mp.model import Model
import time
import math
import gc
from point_generation import gerar_pontos
from aux_functions import build_routes, calculate_distances
from build_model import build_model, operate_cycle
import re
depot = 0

tempo_limite =  3600 #30 minutos
tempo_preparo = 0
tempo_entrega = 4*3600
fatia_tempo = 1800 #30 minutos
instancias = {}

pular_instancias = pd.read_csv('Dados/pular_instancias.csv',sep=";")
for tipo_de_rota in ["ENTRADA"]:
	for instancia in ["tec","grad","full"]:
		try:
			instancias[instancia] = pd.read_csv(f'Dados/pontos_de_onibus_{instancia}_{tipo_de_rota}.csv')
		except FileNotFoundError:
			instancias[instancia] = gerar_pontos(instancia)


	capacity = 50 #Capacidade do ônibus5

	solucoes_resumo = []
	solucoes_detalhe = []
	for instancia in instancias:
		output_file = open(f'output/text/saida_cvrptw_{instancia}_{tipo_de_rota}.txt','w')
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
						'dia':dia,
						'centroid_id':0}
			
			dados_dia = instancias[instancia].copy()
			dados_dia = dados_dia[dados_dia['dia'] == dia].reset_index(drop=True)
			for turno in ['tarde','noite','fim']:
				output_file.writelines(f"Horizonte de Tempo: {tempo_entrega-tempo_preparo} segundos\n\n")
				output_file.writelines("##############################\n")
				output_file.writelines(f"####  Turno Atual: {turno}  ####\n")
				output_file.writelines("##############################\n\n")

				#Lê os dados do dia atual
				dados_turno = dados_dia.copy()
				dados_turno = dados_turno[dados_turno['demanda_'+turno] > 0].reset_index(drop=True)

				if len(dados_turno) == 0:
					continue #Se não tem demanda, pula a iteração

				dados_turno['tempo_preparo'] = tempo_preparo # 6 horas da manhã
				dados_turno['tempo_entrega'] = tempo_entrega # 8 horas da manhã

				comeco_horizonte = dados_turno['tempo_preparo'][depot] # Quando o dia Começa
				fim_horizonte = dados_turno['tempo_entrega'][depot]    # Quando o dia Termina

				#dados_turno = data_prep(turno, dados_turno, capacity, fatia_tempo)
				dados_turno['iteracao'] = 0
				for cd_municipio in dados_turno['cd_municipio'].unique():
					if f"{tipo_de_rota},{instancia},{dia},{turno},{cd_municipio}" in pular_instancias.values:
						print(f"Pulando a instância {tipo_de_rota},{instancia},{dia},{turno},{cd_municipio}")
						continue
					#Filtra os dados do modelo para obter o munícipio atual
					dados_municipio = dados_turno[dados_turno['cd_municipio'] == cd_municipio].copy()
					dados_municipio = dados_municipio[dados_municipio['demanda_'+turno] > 0].reset_index(drop=True)
					centroids = dados_municipio.drop_duplicates(subset=['lat','lon'])[['lat','lon']]
					centroids = centroids.reset_index(names='centroid_id')
					dados_municipio = dados_municipio.merge(centroids, on=['lat','lon'], how='left')
					dados_municipio['centroid_id'] += 1 #Desloca o id em 1 pois iremos inserir o cefet como ponto 0
					dados_municipio.sort_values(by=['iteracao','centroid_id'])

					for iteracao in dados_municipio['iteracao'].unique():
						s = f"|Iteração{iteracao}, Horário de Saída: {tempo_preparo+fatia_tempo*iteracao}|"
						output_file.writelines("_"*len(s)+"\n")
						output_file.writelines(s+"\n")
						output_file.writelines("|"+"_"*(len(s)-2)+"|\n\n")
						output_file.writelines(cd_municipio+"\n")
						
						print("#"*8)
						print("Iteração "+str(iteracao),"Município "+str(cd_municipio))

						#Inclui o CEFET como primeira Linha
						cefet['iteracao'] = iteracao
						cefet['tempo_preparo'] = tempo_preparo + fatia_tempo*iteracao
						dados_iteracao = pd.concat([pd.DataFrame.from_dict(cefet),dados_municipio],ignore_index=True)
						dados_iteracao = dados_iteracao[dados_iteracao['iteracao'] == iteracao]
						dados_iteracao = dados_iteracao.set_index('centroid_id')
						dados_iteracao = dados_iteracao.sort_index() #Previne que haja um embaralhamento nos índices
						del dados_municipio
						gc.collect()
						########################
						#Parâmetros Calculáveis#
						########################

						#Calcula a distância entre os pontos
						distance_matrix, big_m = calculate_distances(dados_iteracao, cd_municipio, iteracao, fatia_tempo)
						num_spots = len(dados_iteracao) #Número de Pontos de Ônibus
						necessary_vehicles = math.ceil(dados_iteracao['demanda_'+turno].sum()/capacity) #Número de veículos = demanda dividada por capacidade
						
						if num_spots == 0: #Se N == 0 é porque não tem mais demanda
							print("Não tem demanda nessa iteração")
							output_file.writelines("Não tem demanda nessa iteração\n\n")
							continue

						output_file.writelines(f"Veículos Disponíveis {necessary_vehicles}, Pontos de Ônibus com Demanda {num_spots}\n\n")

						#Criação do modelo
						model = Model("vrptw")
						model.time_limit = tempo_limite # 10 minutos de execução do modelo no máximo
						print(dia, turno, instancia, necessary_vehicles,num_spots)
						
						model_data = {
							'data': dados_iteracao,
							'num_spots': num_spots,
							'necessary_vehicles': necessary_vehicles,
							'capacity': capacity,
							'iteracao': iteracao,
							'fatia_tempo': fatia_tempo,
							'turno': turno,
							'distancia': distance_matrix,
							'big_m': big_m,
							'depot': depot,
						}
						model, travels = build_model(model, model_data)

						start = time.time() #Tempo de ínicio
						subcicle = True     #Condição de parada
						#Assumindo que existe subciclos, nós...

						# Create a new solution object for warm start
						warm_start_solution = None
						while subcicle == True: 
								
							if warm_start_solution is not None:
								# Add the warm start to the model
								model.add_mip_start(warm_start_solution)

							#Solução VRP - Dicionário Desordenado
							_Solution = model.solve(log_output=False).as_dict()
							tempo_exec = time.time()-start
							routes = build_routes(_Solution, necessary_vehicles)
							summ = 0 # Condição de parada

							model.time_limit = max(tempo_limite - tempo_exec, 1) # Atualiza o tempo limite do modelo

							warm_start_solution = model.new_solution()
							for k in range(necessary_vehicles):

								# Percorre a rota do veículo k como
								# uma lista encadeada
								if len(routes[k]) > 0:

									actual_node = routes[k].pop(0)
									warm_start_solution.add_var_value(travels[k, 0, actual_node], 1) # 1 = True
									while actual_node !=0:
										previous_node = actual_node
										actual_node = routes[k].pop(actual_node)
										warm_start_solution.add_var_value(travels[k, previous_node, actual_node], 1) # 1 = True

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
									detailed_solution_dict = {'instancia': instancia,
											'dia': dia,
											'turno': turno,
											'cd_municipio': cd_municipio,
											'iteracao': iteracao,
											'num_pontos': len(routes[k]),
											'id_veiculo': k
											}
									string = operate_cycle(model, routes, travels, k, option="string", tempo_preparo=tempo_preparo, iteracao=iteracao, distancia=distance_matrix)
									detailed_solution_dict['tempo_viagem'] =float(re.findall(r'\d+\.?\d*', string.split("|")[-1])[0])
									solucoes_detalhe.append(detailed_solution_dict)

									output_file.writelines(string)
									print(string)

							elif tempo_exec > tempo_limite:
								output_file.writelines("Solução não encontrada no limite de tempo definido\n")
								break
						solution_dict = {'instancia': instancia,
											'dia': dia,
											'turno': turno,
											'cd_municipio': cd_municipio,
											'iteracao': iteracao,
											'num_pontos': num_spots,
											'num_veiculos': necessary_vehicles,
											'tempo_exec': tempo_exec,
											'objective_value': model.objective_value,
											}

						solucoes_resumo.append(solution_dict)
						output_file.writelines("Custo da Função Objetiva: "+str(model.objective_value)+"\n")
						output_file.writelines("Tempo Total de Execução: "+str(tempo_exec)+"\n")
						output_file.writelines("\n\n")
						print("Custo da Função Objetiva",model.objective_value)
						print("Tempo Total de Execução", tempo_exec)
					solutions_df = pd.DataFrame(solucoes_resumo)
					solutions_df.to_csv(f'output/csv/solucao_cvrptw_{instancia}_{tipo_de_rota}.csv', index=False)

					solutions_detailed_df = pd.DataFrame(solucoes_detalhe)
					solutions_detailed_df.to_csv(f'output/csv/solucao_completa_cvrptw_{instancia}_{tipo_de_rota}.csv', index=False)

					del model
					gc.collect()  # Coleta de lixo para liberar memória
		output_file.close()
