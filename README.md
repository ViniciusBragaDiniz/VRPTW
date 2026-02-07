# VRPTW — Roteamento de Veículos com Janelas de Tempo

Implementação de um modelo de Programação Linear Inteira Mista (PLIM) para o
Problema de Roteamento de Veículos com Janelas de Tempo (VRPTW), aplicado ao
transporte escolar de alunos do CEFET/RJ.

## Estrutura do Projeto

```
VRPTW/
├── run_pipeline.py              # Orquestrador — ponto de entrada principal
├── data/                        # Tratamento de dados (pacote Python + arquivos)
│   ├── __init__.py
│   ├── preprocessing.py         #   Geocodificação e tratamento de alunos
│   ├── point_generation.py      #   K-means + método do cotovelo
│   ├── raw/                     #   Dados brutos de entrada (CSVs de alunos)
│   └── processed/               #   Dados tratados (turno_resumo.csv, etc.)
├── vrptw/                       # Modelo de otimização
│   ├── __init__.py
│   ├── config.py                #   Parâmetros centralizados (altere aqui!)
│   ├── model_builder.py         #   Formulação PLIM (variáveis, restrições)
│   ├── solver.py                #   Loop de resolução + corte de subciclos
│   ├── postprocessing.py        #   Re-sequenciamento de viagens
│   └── utils.py                 #   Haversine, distâncias, rotas
├── src/                         # Scripts auxiliares (etapas individuais)
│   ├── 01_preprocess_data.py
│   ├── 02_generate_points.py
│   ├── 03_solve_vrptw.py
│   └── 04_resequence_trips.py
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

Todos os parâmetros configuráveis estão centralizados em `vrptw/config.py`:

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

Use o orquestrador `run_pipeline.py` na raiz do projeto:

```bash
# Pipeline completo (etapas 1 → 2 → 3 → 4)
python run_pipeline.py

# Pular a geocodificação (dados já processados)
python run_pipeline.py --skip-preprocess

# Pular etapas 1 e 2 (pontos já gerados)
python run_pipeline.py --skip-preprocess --skip-points

# Executar apenas o pós-processamento
python run_pipeline.py --only-postprocess
```

Alternativamente, cada etapa pode ser executada individualmente via `src/`:

```bash
python src/01_preprocess_data.py
python src/02_generate_points.py --filter tec --shift ENTRADA
python src/03_solve_vrptw.py
python src/04_resequence_trips.py
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
