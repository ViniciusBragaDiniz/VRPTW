"""Centralized configuration of VRPTW model parameters.

This module concentrates all configurable project parameters in a single
location, facilitating experiment reproducibility and scenario changes
by other researchers. Changing any parameter here is automatically
reflected in all modules that use it.

Usage example:
    >>> from vrptw.config import VEHICLE_CAPACITY, TIME_LIMIT
    >>> print(f"Capacity: {VEHICLE_CAPACITY} passengers")
    Capacity: 50 passengers
"""

from pathlib import Path

# ---------------------------------------------------------------------------
# Project directories
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent

#: Base data directory (also the ``data`` Python package).
DATA_DIR = PROJECT_ROOT / "data"

#: Raw input data (student CSVs, instances, etc.).
DATA_RAW_DIR = DATA_DIR / "raw"

#: Processed / intermediate data (turno_resumo.csv, etc.).
DATA_PROCESSED_DIR = DATA_DIR / "processed"

OUTPUT_DIR = DATA_DIR / "output"
OUTPUT_CSV_DIR = OUTPUT_DIR / "csv"
OUTPUT_TEXT_DIR = OUTPUT_DIR / "text"
IMGS_DIR = PROJECT_ROOT / "imgs"

# ---------------------------------------------------------------------------
# Optimization model parameters
# ---------------------------------------------------------------------------

#: Maximum vehicle capacity (number of passengers).
VEHICLE_CAPACITY: int = 50

#: CPLEX solver time limit (seconds).
TIME_LIMIT: int = 3600

#: Time window start (seconds from midnight).
#: Example: 0 = midnight.
EARLIEST_DEPARTURE: int = 0

#: Time window end (seconds from midnight).
#: Example: 4 * 3600 = 04:00 AM (4-hour horizon).
LATEST_ARRIVAL: int = 4 * 3600

#: Duration of each time slot for partitioning (seconds).
#: Example: 1800 = 30 minutes.
TIME_SLOT_DURATION: int = 1800

#: Depot node index (CEFET) in the route graph.
DEPOT_INDEX: int = 0

# ---------------------------------------------------------------------------
# Depot coordinates (CEFET)
# ---------------------------------------------------------------------------
DEPOT_LAT: float = -43.46242373123213
DEPOT_LON: float = -22.704575111343242

# ---------------------------------------------------------------------------
# Clustering parameters (bus stop generation)
# ---------------------------------------------------------------------------

#: Minimum number of students per municipality to generate bus stops.
#: Municipalities with fewer students than this threshold are discarded.
MIN_STUDENTS_PER_MUNICIPALITY: int = 10

#: Number of K-means initializations to ensure convergence.
KMEANS_N_INIT: int = 10

# ---------------------------------------------------------------------------
# Average speeds per municipality (km/h)
# ---------------------------------------------------------------------------
#: Mapping of municipalities to estimated average speeds (km/h).
#: Used in travel time matrix calculation.
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

#: Default speed for municipalities not listed above (km/h).
DEFAULT_SPEED_KMH: float = 40.0

# ---------------------------------------------------------------------------
# Instances and scenarios
# ---------------------------------------------------------------------------

#: Instance types to process.
INSTANCE_TYPES: list[str] = ["tec", "grad", "full"]

#: Weekdays to process.
WEEKDAYS: list[str] = ["seg", "ter", "qua", "qui", "sex", "sab"]

#: Shifts to process for each day.
SHIFTS: list[str] = ["tarde", "noite", "fim"]

#: Route types (trip direction).
ROUTE_TYPES: list[str] = ["ENTRY"]

# ---------------------------------------------------------------------------
# Maximum work hours per vehicle (post-processing)
# ---------------------------------------------------------------------------

#: Maximum work time per vehicle in seconds (4 hours).
MAX_VEHICLE_WORK_TIME: int = 4 * 3600
