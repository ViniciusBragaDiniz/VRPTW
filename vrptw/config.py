"""Configuração centralizada de parâmetros do modelo VRPTW.

Este módulo concentra todos os parâmetros configuráveis do projeto em um
único local, facilitando a reprodução de experimentos e a alteração de
cenários por outros pesquisadores. Alterar qualquer parâmetro aqui
reflete automaticamente em todos os módulos que o utilizam.

Exemplo de uso:
    >>> from vrptw.config import VEHICLE_CAPACITY, TIME_LIMIT
    >>> print(f"Capacidade: {VEHICLE_CAPACITY} passageiros")
    Capacidade: 50 passageiros
"""

from pathlib import Path

# ---------------------------------------------------------------------------
# Diretórios do projeto
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent

#: Diretório-base de dados (também é o pacote Python ``data``).
DATA_DIR = PROJECT_ROOT / "data"

#: Dados brutos de entrada (CSVs de alunos, instâncias, etc.).
DATA_RAW_DIR = DATA_DIR / "raw"

#: Dados tratados / intermediários (turno_resumo.csv, etc.).
DATA_PROCESSED_DIR = DATA_DIR / "processed"

OUTPUT_DIR = DATA_DIR / "output"
OUTPUT_CSV_DIR = OUTPUT_DIR / "csv"
OUTPUT_TEXT_DIR = OUTPUT_DIR / "text"
IMGS_DIR = PROJECT_ROOT / "imgs"

# ---------------------------------------------------------------------------
# Parâmetros do modelo de otimização
# ---------------------------------------------------------------------------

#: Capacidade máxima de cada veículo (número de passageiros).
VEHICLE_CAPACITY: int = 50

#: Limite de tempo para o solver CPLEX (segundos).
TIME_LIMIT: int = 3600

#: Início da janela de tempo (segundos a partir da meia-noite).
#: Exemplo: 0 = meia-noite.
EARLIEST_DEPARTURE: int = 0

#: Fim da janela de tempo (segundos a partir da meia-noite).
#: Exemplo: 4 * 3600 = 04:00 da manhã (horizonte de 4 horas).
LATEST_ARRIVAL: int = 4 * 3600

#: Duração de cada fatia de tempo para particionamento (segundos).
#: Exemplo: 1800 = 30 minutos.
TIME_SLOT_DURATION: int = 1800

#: Índice do nó-depósito (CEFET) no grafo de rotas.
DEPOT_INDEX: int = 0

# ---------------------------------------------------------------------------
# Coordenadas do depósito (CEFET)
# ---------------------------------------------------------------------------
DEPOT_LAT: float = -43.46242373123213
DEPOT_LON: float = -22.704575111343242

# ---------------------------------------------------------------------------
# Parâmetros de clusterização (geração de pontos de parada)
# ---------------------------------------------------------------------------

#: Número mínimo de alunos por município para gerar pontos de parada.
#: Municípios com menos alunos que esse limiar são desconsiderados.
MIN_STUDENTS_PER_MUNICIPALITY: int = 10

#: Número de inicializações do K-means para garantir convergência.
KMEANS_N_INIT: int = 10

# ---------------------------------------------------------------------------
# Velocidades médias por município (km/h)
# ---------------------------------------------------------------------------
#: Mapeamento de municípios para velocidades médias estimadas (km/h).
#: Utilizado no cálculo da matriz de tempos de viagem.
MUNICIPALITY_SPEED_KMH: dict[str, float] = {
    "Nova Iguacu": 20.0,
    "Mesquita": 20.0,
    "Nilopolis": 20.0,
    "Duque De Caxias": 30.0,
    "Belford Roxo": 30.0,
    "Sao Joao De Meriti": 30.0,
    "Queimados": 30.0,
    "Rio De Janeiro": 60.0,
    "Japeri": 60.0,
}

#: Velocidade padrão para municípios não listados acima (km/h).
DEFAULT_SPEED_KMH: float = 40.0

# ---------------------------------------------------------------------------
# Instâncias e cenários
# ---------------------------------------------------------------------------

#: Tipos de instância a processar.
INSTANCE_TYPES: list[str] = ["tec", "grad", "full"]

#: Dias da semana a processar.
WEEKDAYS: list[str] = ["seg", "ter", "qua", "qui", "sex", "sab"]

#: Turnos a processar para cada dia.
SHIFTS: list[str] = ["tarde", "noite", "fim"]

#: Tipos de rota (direção da viagem).
ROUTE_TYPES: list[str] = ["ENTRADA"]

# ---------------------------------------------------------------------------
# Limite de horas de trabalho por veículo (pós-processamento)
# ---------------------------------------------------------------------------

#: Jornada máxima por veículo em segundos (4 horas).
MAX_VEHICLE_WORK_TIME: int = 4 * 3600
