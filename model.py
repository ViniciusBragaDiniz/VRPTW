def haversine(lat1, lon1, lat2, lon2):
    # Raio médio da Terra em metros
    r = 6371000  # Aproximadamente 6.371 quilômetros

    # Converte graus para radianos
    lat1 = math.radians(lat1)
    lon1 = math.radians(lon1)
    lat2 = math.radians(lat2)
    lon2 = math.radians(lon2)

    # Diferenças de latitude e longitude
    dlat = lat2 - lat1
    dlon = lon2 - lon1

    # Fórmula de Haversine
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    # Distância em metros
    distance = r * c

    return distance


 # Importação dos Dados
import pandas as pd
import math
from docplex.mp.model import Model
from docplex.mp.linear import LinearExpr
import time
from point_generation import gerar_pontos

depot = 0


tempo_preparo = 0
tempo_entrega = 3.5*3600

instancias = {}
for instancia in ["tec","grad",""]:
	instancias[instancia] = gerar_pontos(instancia)

output_file = open('saida_cvrptw.txt','w')
output_file.writelines(f"Horizonte de Tempo: {tempo_entrega-tempo_preparo} segundos\n\n")
for turno in ['manha','tarde']:

	output_file.writelines("##############################\n")
	output_file.writelines(f"####  Turno Atual: {turno}  ####\n")
	output_file.writelines("##############################\n\n")

	#Exportação de Nova_Iguacu_Setores_Censitarios.ipynb
	dados = pd.read_csv('pontos_de_onibus.csv',index_col=0)
	dados.reset_index(names='id',inplace=True) 
	
	#Linha que vai representar o CEFET no modelo
	cefet = {'lon':[-43.46242373123213],
		     'lat':[-22.704575111343242],
		     'demanda_manha':[0],
		     'demanda_tarde':[0],
		     'tempo_preparo':tempo_preparo,
		     'tempo_entrega':tempo_entrega,
		     'cd_municipio':'CEFET'}
         
	dados['tempo_preparo'] = tempo_preparo# 6 horas da manhã
	dados['tempo_entrega'] = tempo_entrega#8 horas da manhã
	#Inclui o CEFET como primeira Linha
	dados = pd.concat([pd.DataFrame.from_dict(cefet),dados],ignore_index=True)

	#Matriz de Distância
	distancia = [[0 for _ in range(len(dados))] for _ in range(len(dados))]


	comeco_horizonte = dados['tempo_preparo'][depot] #Quando o dia Começa
	fim_horizonte = dados['tempo_entrega'][depot]    #Quando o dia Termina

	#Divisões dos períodos
	divisoes_possiveis = (dados['tempo_entrega'] - dados['tempo_preparo'])/(1800)
	divisoes_possiveis = divisoes_possiveis.apply(lambda x: math.floor(x))
	divisoes_necessarias = (dados.groupby('cd_municipio').sum()['demanda_'+turno]/(c)).apply(lambda x: math.ceil(x))


	#Vamos ter uma iteracao a cada período de tempo
	dados['iteracao'] = 0
	dados.fillna(0,inplace=True)


	l = []
	
	#Só dividimos a demanda se for maior que a capacidade de um único ônibus
	demanda_minima = dados.groupby('cd_municipio').sum()['demanda_'+turno] <= c

	for i in range(1, len(dados)):
		cd_mun = dados['cd_municipio'][i] #código do municipio
		
		if divisoes_possiveis[i] <= 0 | demanda_minima[cd_mun]:
		    continue #previne erros e divisões desnecessárias
		
		divisoes_viaveis = min(divisoes_possiveis[i],divisoes_necessarias[cd_mun])
	    #Demanda dividida pelo número de periodos
		demanda_particionada = dados.loc[i]['demanda_'+turno] / divisoes_viaveis
		dados.loc[i,'demanda_'+turno] = math.ceil(demanda_particionada)
		
		for iteracao in range(1,divisoes_viaveis):
		    linha = dados.loc[i].copy()
		    linha['demanda_'+turno] = max(math.floor(demanda_particionada),1) #Esse máx é pra evitar erros devido a demanda aleatoria
		    linha['tempo_preparo'] += 1800*iteracao
		    linha['iteracao'] = int(iteracao)
		    l.append(pd.DataFrame(linha).T)

	#Adiciona as iterações pelo 
	dados = pd.concat([dados,pd.concat(l,ignore_index=True)],ignore_index=True).sort_values(['iteracao'])
	print('#'*16)
	print(turno)
	print('#'*16)
	for iteracao in range(dados['iteracao'].max()):

		s = f"|Iteração{iteracao}, Horário de Saída: {tempo_preparo+1800*iteracao}|"
		output_file.writelines("_"*len(s)+"\n")
		output_file.writelines(s+"\n")
		output_file.writelines("|"+"_"*(len(s)-2)+"|\n\n")	
		
		for cd_municipio in dados['cd_municipio'].unique():
			
			if cd_municipio == 'CEFET':
				continue
			
			output_file.writelines(cidades[str(cd_municipio)]+"\n")
			
			print("#"*8)
			print("Iteração "+str(iteracao),"Município "+str(cidades[str(cd_municipio)]))
			dados_municipio = dados[dados['iteracao'] == iteracao]
			
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
			v = math.ceil(dados_municipio['demanda_'+turno].sum()/c) #Número de veículos = demanda dividada por capacidade
			
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

			capacity = {(k,i): model.integer_var(lb=0,ub=c,name=f'clients_at_{i}_with_{k}') for k in range(v) for i in range(n)}


			###################
			# Função Objetiva #
			###################
			model.minimize(model.sum(travels[k,i,j]*distancia[i][j] for i in range(n) for j in range(n) for k in range(v)))

			#Respeitar Capacidade
			for k in range(v):
				consumed_capacity = model.sum(capacity[k,i] for i in range(n))
				model.add_constraint(consumed_capacity <= c, 'Capacity_Vehicle_'+str(k))

			#Atender o cliente i é obrigatório
			for i in range(1,n):
				demand_met = model.sum(capacity[k,i] for k in range(v))
				model.add_constraint(demand_met == dados_municipio.loc[i,'demanda_'+turno],'Visit_Client_'+str(i))


			#Para pegar clientes é preciso visitar o ponto
			for k in range(v):
				for i in range(n):
					#c aqui funciona como big M
					visit_i = model.sum(c*travels[k,i,j] for j in range(n))
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
