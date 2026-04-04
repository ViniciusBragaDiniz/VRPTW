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

#: Processed / intermediate data (SHIFT_PROCESSED.csv, etc.).
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

#: Acceptable MIP relative gap (0.02 = 2%).
#: The solver stops early when the gap between the best integer solution and
#: the best relaxation bound is within this tolerance.
MIP_GAP: float = 0.00

#: Number of threads CPLEX may use for parallel branch-and-bound.
#: Matches the physical core count of the host (i5-10600K, 6C/12T).
#: Using physical cores avoids the extra memory pressure of hyperthreads.
SOLVER_THREADS: int = 6

#: Whether the CPLEX engine log is written to stdout during the solve.
SOLVER_LOG_OUTPUT: bool = True

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
DEPOT_LAT: float = -22.704575111343242
DEPOT_LON: float = -43.46242373123213

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
WEEKDAYS: list[str] = ["MON", "TUE", "WED", "THU", "FRI", "SAT"]

#: Shifts to process for each day.
SHIFTS: list[str] = ["AFTERNOON", "NIGHT", "LATE"]

#: Route types (trip direction).
ROUTE_TYPES: list[str] = ["ENTRY", "EXIT"]

# ---------------------------------------------------------------------------
# Memory safeguards
# ---------------------------------------------------------------------------

#: CPLEX working memory limit (MB).  When branch-and-bound node storage
#: exceeds this threshold CPLEX spills data to disk according to the
#: ``SOLVER_NODE_FILE_STRATEGY`` setting.
SOLVER_WORK_MEM: int = 8 * 1024

#: Maximum tree memory (MB).  Once the total search-tree size (RAM + disk)
#: reaches this limit, CPLEX stops and returns the best solution found so far.
SOLVER_TREE_MEM_LIMIT: int = 16 * 1024

#: Node file strategy (``model.parameters.mip.strategy.file``).
#: 0 = automatic, 1 = in-memory only, 2 = compressed on disk, 3 = on disk.
SOLVER_NODE_FILE_STRATEGY: int = 2

#: When ``True`` CPLEX trades some solving speed for a smaller memory
#: footprint (``model.parameters.emphasis.memory = 1``).
SOLVER_MEMORY_EMPHASIS: bool = True

#: Process RSS limit (MB).  Before building a new model the solver checks
#: the current resident set size and skips the scenario if it exceeds this
#: threshold to prevent the OS from killing the process.
PROCESS_MEMORY_LIMIT_MB: int = 11 * 1024

# ---------------------------------------------------------------------------
# Maximum work hours per vehicle (post-processing)
# ---------------------------------------------------------------------------

#: Maximum work time per vehicle in seconds (4 hours).
MAX_VEHICLE_WORK_TIME: int = 4 * 3600
