import pandas as pd
from docplex.mp.model import Model
from docplex.mp.linear import LinearExpr
import time
import math

from point_generation import gerar_pontos
from aux_functions import haversine, data_prep
depot = 0


tempo_preparo = 0
tempo_entrega = 3.5*3600

instancias = {}
for instancia in ["tec","grad","full"]:
	try:
		instancias[instancia] = pd.read_csv(f'Dados/pontos_de_onibus_{instancia}.csv')
	except FileNotFoundError:
		instancias[instancia] = gerar_pontos(instancia)


capacity = 50 #Capacidade do ônibus
for dia in ['seg','ter','qua','qui','sex','sab']:

	#Linha que vai representar o CEFET no modelo
	cefet = {'lon':[-43.46242373123213],
				'lat':[-22.704575111343242],
				'demanda_manha':[0],
				'demanda_tarde':[0],
				'demanda_noite':[0],
				'tempo_preparo':tempo_preparo,
				'tempo_entrega':tempo_entrega,
				'cd_municipio':'CEFET',
				'dia':dia}
	
	for turno in ['manha','tarde', 'noite']:

		for instancia in instancias:

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

			for iteracao in range(dados_modelo['iteracao'].max()):

				s = f"|Iteração{iteracao}, Horário de Saída: {tempo_preparo+1800*iteracao}|"
				output_file.writelines("_"*len(s)+"\n")
				output_file.writelines(s+"\n")
				output_file.writelines("|"+"_"*(len(s)-2)+"|\n\n")	
				
				for cd_municipio in dados_modelo['cd_municipio'].unique():
					
					if cd_municipio == 'CEFET':
						continue
					
					output_file.writelines(cidades[str(cd_municipio)]+"\n")
					
					print("#"*8)
					print("Iteração "+str(iteracao),"Município "+str(cidades[str(cd_municipio)]))
					dados_municipio = dados_modelo[dados_modelo['iteracao'] == iteracao]
					
					dados_municipio = dados_municipio[dados_municipio['cd_municipio'].isin([cd_municipio,'CEFET'])].reset_index(drop=True)
					
					M = -1
					for i in range(len(dados_municipio)):
						for j in range(len(dados_municipio)):
							if i != j:
								#Distância em Metros
								distancia[i][j]=round(haversine(dados_municipio['lat'][i],dados_municipio['lon'][i],
																dados_municipio['lat'][j],dados_municipio['lon'][j]))
								#Assumindo Velocidade Média de 20 km/h se for Nova Iguaçu
								if cd_municipio == 3303500:
									distancia[i][j] = distancia[i][j]/(20/3.6) #Calculo do tempo em segundos
								else: #Para fora assume-se 60 km/h
									distancia[i][j] = distancia[i][j]/(60/3.6) #Calculo do tempo em segundos
								
								M = max(M,dados_municipio['tempo_entrega'][i]+distancia[i][j]-(dados_municipio['tempo_preparo'][i]+1800*iteracao))
							else: 
								distancia[i][j]=float('inf')
					#criação do modelo
					model = Model("vrptw")

					########################
					#Parâmetros Calculáveis#
					########################
					n = len(dados_municipio) #Número de Pontos de Ônibus
					v = math.ceil(dados_municipio['demanda_'+turno].sum()/capacity) #Número de veículos = demanda dividada por capacidade
					
					if n == 0: #Se N == 0 é porque não tem mais demanda
						print("Não tem demanda nessa iteração")
						output_file.writelines("Não tem demanda nessa iteração\n\n")
						continue
					print(v,n)
					output_file.writelines(f"Veículos Disponíveis {v}, Pontos de Ônibus com Demanda {n}\n\n")
					#############
					# Variáveis #
					#############
					travels = model.binary_var_cube(v,n,n,'travel')#matriz tridimensional k*v²

					service = {(k,i): model.continuous_var(
					lb=dados_municipio['tempo_preparo'][i]+1800*iteracao,
						ub=dados_municipio['tempo_entrega'][i],name=f'service_start_{k}_{i}') 
						for k in range(v) for i in range(n)}#momento em que o serviço começa no cliente i

					capacity = {(k,i): model.integer_var(lb=0,ub=capacity,name=f'clients_at_{i}_with_{k}') for k in range(v) for i in range(n)}


					###################
					# Função Objetiva #
					###################
					model.minimize(model.sum(travels[k,i,j]*distancia[i][j] for i in range(n) for j in range(n) for k in range(v)))

					#Respeitar Capacidade
					for k in range(v):
						consumed_capacity = model.sum(capacity[k,i] for i in range(n))
						model.add_constraint(consumed_capacity <= capacity, 'Capacity_Vehicle_'+str(k))

					#Atender o cliente i é obrigatório
					for i in range(1,n):
						demand_met = model.sum(capacity[k,i] for k in range(v))
						model.add_constraint(demand_met == dados_municipio.loc[i,'demanda_'+turno],'Visit_Client_'+str(i))


					#Para pegar clientes é preciso visitar o ponto
					for k in range(v):
						for i in range(n):
							#c aqui funciona como big M
							visit_i = model.sum(capacity*travels[k,i,j] for j in range(n))
							model.add_constraint(visit_i - capacity[k,i] >= 0, f"Visit_Client_{i}_Vehicle_{k}")

					#Saída a Partir do Depósito
					for k in range(v):
						model.add_constraint(
							model.sum((n*n)*travels[k,depot,j]
								for j in range(1,n)) - 
									model.sum(travels[k,i,j] 
										for i in range(1,n) 
											for j in range(1,n)) >= 0,
									'Exit_Depot_Vehicle_'+str(k))

					#Conservação de Fluxo
					for k in range(v):
						for i in range(n):
							model.add_constraint(
								model.sum(travels[k,i,j]-travels[k,j,i]
										for j in range(n)) == 0,
											f'Flux_Conservation_Vehicle_{k}_Node_{i}')

					#Passagem Única de Fluxo
					for k in range(v):
						for i in range(n):
							model.add_constraint(
								model.sum(travels[k,i,j]
										for j in range(n)) <= 1,
											f'Unique_Passage_Vehicle_{k}_Node_{i}')

					#Tempo de Saida
					for k in range(v):
						for i in range(n):
							for j in range(i+1,n):
								model.add_constraint(service[k,i]+distancia[i][j]-M*(1-travels[k,i,j]) <= service[k,j],
													f'Exit_Time_{k}_{i}_{j}')
					#Remoção da Diagonal
					model.add_constraint(model.sum(travels[k,i,i] for k in range(v) for i in range(n))==0);
					#model.export_as_lp('model.txt')

					start = time.time() #Tempo de ínicio
					subcicle = True     #Condição de parada
					#Assumindo que existe subciclos, nós...
					while subcicle == True:
						#Rota percorrida por cada veículo
						routes = {x:{} for x in range(v)}    

						#Solução VRP - Dicionário Desordenado
						_Solution = model.solve(log_output=False).as_dict()

						for i in _Solution:
							if i.name[0] != "t" or _Solution[i] < 0.001:
								continue

							aux = i.name.split("_")[1:] #<- ["k","i","j"]
							routes[int(aux[0])][int(aux[1])]=int(aux[2])
							
						count = 0 #Contador para as eliminações de subciclo
						summ = 0 #Condição de parada

						for k in range(v):
							if len(routes[k]) > 0:
								actual_node = routes[k].pop(0)
								while actual_node !=0:
									actual_node = routes[k].pop(actual_node)
								summ += len(routes[k])
								
								if len(routes[k]) >0:
									while(len(routes[k])>0):
										cut = LinearExpr(model) #Expressão Linear do Subciclo atual

								first_node = list(routes[k].keys())[0]
								actual_node = routes[k].pop(first_node)
								cut += travels[k,int(first_node),int(actual_node)]
								size = 0

								while(actual_node != first_node):
									next_node = routes[k].pop(actual_node)                 #Percorre o subciclo e o adiciona ao#
									cut += travels[k,int(actual_node),int(next_node)]#conjunto de subciclos proíbidos.#
									actual_node = next_node
									size+=1
								count+=1
								model.add_constraint(cut<=size,"SubCycleCut_"+str(count))
										
							if summ == 0:
								subcicle = False
								#Rota percorrida por cada veículo
								routes = {x:{} for x in range(v)}    
								#Solução VRP - Dicionário Desordenado
								_Solution = model.solve(log_output=True).as_dict()
								
								output_file.writelines(f"Solução:\n")
								print(_Solution)
								for i in _Solution:
									if i.name[0] != "t" or _Solution[i] < 0.001:
										continue

									aux = i.name.split("_")[1:] #<- ["k","i","j"]
									routes[int(aux[0])][int(aux[1])]=int(aux[2])
								for k in range(v):
									tempo_final = 0
									string = f"Veículo {k} Início [{tempo_preparo+1800*iteracao}s] |Rota: 0"
									while(len(routes[k])>0):
										print(routes[k])
										first_node = 0
										actual_node = routes[k].pop(first_node)
										string+=" -> "+str(actual_node)
										
										tempo_final += distancia[first_node][actual_node]
										while(actual_node != first_node):
											next_node = routes[k].pop(actual_node)
											tempo_final+=distancia[actual_node][next_node]
											actual_node = next_node
											string+=" -> "+str(actual_node)
									string += f"| Fim [{tempo_preparo+tempo_final+1800*iteracao}s]\n"
									output_file.writelines(string)
									print(string)
							
					tempo_exec = time.time()-start
					output_file.writelines("Custo da Função Objetiva: "+str(model.objective_value)+"\n")
					output_file.writelines("Tempo Total de Execução: "+str(tempo_exec)+"\n")
					output_file.writelines("\n\n")
					print("Custo da Função Objetiva",model.objective_value)
					print("Tempo Total de Execução", tempo_exec)
	output_file.close()
