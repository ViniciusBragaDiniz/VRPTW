# VRPTW — Vehicle Routing Problem with Time Windows

Implementation of a Mixed-Integer Linear Programming (MILP) model for the
Vehicle Routing Problem with Time Windows (VRPTW), applied to school bus
transportation for CEFET/RJ students.

## Project Structure

```
VRPTW/
├── run_pipeline.py              # Orchestrator — main entry point
├── data/                        # Data processing (Python package + files)
│   ├── __init__.py
│   ├── preprocessing.py         #   Geocoding and student data processing
│   ├── point_generation.py      #   K-means + elbow method
│   ├── raw/                     #   Raw input data (student CSVs)
│   └── processed/               #   Processed data (turno_resumo.csv, etc.)
├── vrptw/                       # Optimization model
│   ├── __init__.py
│   ├── config.py                #   Centralized parameters (change here!)
│   ├── model_builder.py         #   MILP formulation (variables, constraints)
│   ├── solver.py                #   Solving loop + subtour cuts
│   ├── postprocessing.py        #   Trip re-sequencing
│   └── utils.py                 #   Haversine, distances, routes
├── src/                         # Auxiliary scripts (individual steps)
│   ├── 01_preprocess_data.py
│   ├── 02_generate_points.py
│   ├── 03_solve_vrptw.py
│   └── 04_resequence_trips.py
├── output/
│   ├── csv/                     # Results in CSV format
│   └── text/                    # Route logs in text format
├── imgs/                        # Generated charts (elbow method)
├── requirements.txt             # Python dependencies
└── secrets                      # Google Maps API key (DO NOT version!)
```

## Prerequisites

- **Python 3.10+**
- **IBM ILOG CPLEX** (optimization solver) — required by `docplex`
- **Google Maps API** key (for geocoding in Step 1)

## Installation

```bash
# Clone the repository
git clone <repository-url>
cd VRPTW

# Create a virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate   # Linux/macOS
# .venv\Scripts\activate    # Windows

# Install dependencies
pip install -r requirements.txt
```

## Configuration

### `secrets` file

Create a `secrets` file at the project root (only needed for Step 1):

```
GOOGLEMAPS_APIKEY=your_key_here
```

> **Warning:** this file is in `.gitignore` and **must not** be versioned.

### Model parameters

All configurable parameters are centralized in `vrptw/config.py`:

| Parameter | Description | Default |
|-----------|-------------|---------|
| `VEHICLE_CAPACITY` | Vehicle capacity (passengers) | 50 |
| `TIME_LIMIT` | Solver time limit (seconds) | 3600 |
| `EARLIEST_DEPARTURE` | Time window start (s) | 0 |
| `LATEST_ARRIVAL` | Time window end (s) | 14400 |
| `TIME_SLOT_DURATION` | Time slot duration (s) | 1800 |
| `MIN_STUDENTS_PER_MUNICIPALITY` | Min. students per municipality | 10 |
| `MUNICIPALITY_SPEED_KMH` | Speeds per municipality (km/h) | see config.py |

## Usage

Use the orchestrator `run_pipeline.py` at the project root:

```bash
# Full pipeline (steps 1 → 2 → 3 → 4)
python run_pipeline.py

# Skip geocoding (data already processed)
python run_pipeline.py --skip-preprocess

# Skip steps 1 and 2 (points already generated)
python run_pipeline.py --skip-preprocess --skip-points

# Run only post-processing
python run_pipeline.py --only-postprocess
```

Alternatively, each step can be run individually via `src/`:

```bash
python src/01_preprocess_data.py
python src/02_generate_points.py --filter tec --shift ENTRY
python src/03_solve_vrptw.py
python src/04_resequence_trips.py
```

## Mathematical Formulation

The MILP model follows the classical VRPTW formulation:

- **Decision variables:**
  - `x[k,i,j]` ∈ {0,1} — vehicle *k* travels from node *i* to node *j*
  - `s[k,i]` ∈ ℝ — service start time at node *i*
  - `q[k,i]` ∈ ℤ — load served at node *i* by vehicle *k*

- **Objective function:** minimize total travel distance

- **Constraints:** capacity, mandatory service, flow conservation,
  time windows (Big-M), single visit, subtour elimination (cutting planes)

## Output

- `output/csv/solution_cvrptw_<instance>_<type>.csv` — summary per scenario
- `output/csv/solution_completa_cvrptw_<instance>_<type>.csv` — details per route
- `output/csv/solution_adjusted.csv` — solution with minimized vehicles
- `output/text/solution_cvrptw_<instance>_<type>.txt` — textual route log

## Author

Vinícius Braga Diniz — contato.vbd@gmail.com
