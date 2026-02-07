# VRPTW — Roteamento de Veículos com Janelas de Tempo

Implementação de um modelo de Programação Linear Inteira Mista (PLIM) para o
Problema de Roteamento de Veículos com Janelas de Tempo (VRPTW), aplicado ao
transporte escolar de alunos do CEFET/RJ.

## Estrutura do Projeto

```
VRPTW/
├── config.py                    # Parâmetros centralizados (altere aqui!)
├── 01_preprocess_data.py        # Etapa 1: pré-processamento de dados
├── 02_generate_points.py        # Etapa 2: geração de pontos de parada
├── 03_solve_vrptw.py            # Etapa 3: resolução do modelo
├── 04_resequence_trips.py       # Etapa 4: minimização de veículos
├── vrptw/                       # Pacote com a lógica principal
│   ├── __init__.py
│   ├── preprocessing.py         #   Tratamento e geocodificação de dados
│   ├── point_generation.py      #   K-means + método do cotovelo
│   ├── model_builder.py         #   Formulação PLIM (variáveis, restrições)
│   ├── solver.py                #   Loop de resolução + corte de subciclos
│   ├── postprocessing.py        #   Re-sequenciamento de viagens
│   └── utils.py                 #   Haversine, distâncias, rotas
├── data/                        # Dados de entrada (CSVs de alunos)
├── dados_tratados/              # Dados intermediários (turno_resumo.csv)
├── output/
│   ├── csv/                     # Resultados em formato CSV
│   └── text/                    # Logs de rotas em texto
├── imgs/                        # Gráficos gerados (método do cotovelo)
├── requirements.txt             # Dependências Python
└── secrets                      # Chave da API Google Maps (NÃO versionar!)
```

## Pré-requisitos

- **Python 3.10+**
- **IBM ILOG CPLEX** (solver de otimização) — necessário para o `docplex`
- Chave da **API Google Maps** (para georreferenciamento na Etapa 1)

## Instalação

```bash
# Clonar o repositório
git clone <url-do-repositorio>
cd VRPTW

# Criar ambiente virtual (recomendado)
python -m venv .venv
source .venv/bin/activate   # Linux/macOS
# .venv\Scripts\activate    # Windows

# Instalar dependências
pip install -r requirements.txt
```

## Configuração

### Arquivo `secrets`

Crie um arquivo `secrets` na raiz do projeto (apenas para a Etapa 1):

```
GOOGLEMAPS_APIKEY=sua_chave_aqui
```

> **Atenção:** este arquivo está no `.gitignore` e **não deve** ser versionado.

### Parâmetros do modelo

Todos os parâmetros configuráveis estão centralizados em `config.py`:

| Parâmetro | Descrição | Padrão |
|-----------|-----------|--------|
| `VEHICLE_CAPACITY` | Capacidade do veículo (passageiros) | 50 |
| `TIME_LIMIT` | Limite de tempo do solver (segundos) | 3600 |
| `EARLIEST_DEPARTURE` | Início da janela de tempo (s) | 0 |
| `LATEST_ARRIVAL` | Fim da janela de tempo (s) | 14400 |
| `TIME_SLOT_DURATION` | Fatia de tempo (s) | 1800 |
| `MIN_STUDENTS_PER_MUNICIPALITY` | Mín. alunos por município | 10 |
| `MUNICIPALITY_SPEED_KMH` | Velocidades por município (km/h) | ver config.py |

## Execução

O pipeline é composto por 4 etapas sequenciais:

```bash
# Etapa 1 — Pré-processamento (geocodificação)
python 01_preprocess_data.py

# Etapa 2 — Geração de pontos de parada
python 02_generate_points.py
python 02_generate_points.py --filter tec --shift ENTRADA  # opções

# Etapa 3 — Resolução do modelo VRPTW
python 03_solve_vrptw.py

# Etapa 4 — Minimização de veículos (pós-processamento)
python 04_resequence_trips.py
```

## Formulação Matemática

O modelo PLIM segue a formulação clássica do VRPTW:

- **Variáveis de decisão:**
  - `x[k,i,j]` ∈ {0,1} — veículo *k* viaja do nó *i* ao nó *j*
  - `s[k,i]` ∈ ℝ — instante de início do serviço no nó *i*
  - `q[k,i]` ∈ ℤ — carga atendida no nó *i* pelo veículo *k*

- **Função objetivo:** minimizar a distância total percorrida

- **Restrições:** capacidade, atendimento obrigatório, conservação de fluxo,
  janelas de tempo (Big-M), passagem única, eliminação de subciclos (planos de corte)

## Saída

- `output/csv/solucao_cvrptw_<instancia>_<tipo>.csv` — resumo por cenário
- `output/csv/solucao_completa_cvrptw_<instancia>_<tipo>.csv` — detalhes por rota
- `output/csv/solucao_ajustada.csv` — solução com veículos minimizados
- `output/text/saida_cvrptw_<instancia>_<tipo>.txt` — log textual das rotas

## Autor

Vinícius Braga Diniz — contato.vbd@gmail.com
