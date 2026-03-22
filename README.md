# VRPTW — Vehicle Routing Problem with Time Windows

Implementation of a Mixed-Integer Linear Programming (MILP) model for the
Vehicle Routing Problem with Time Windows (VRPTW), applied to school bus
transportation for CEFET/RJ students.

## Project Structure

```
VRPTW/
├── run_pipeline.py                  # Orchestrator — main entry point
├── requirements.txt                 # Python dependencies
├── secrets                          # Google Maps API key (DO NOT version!)
│
├── data/                            # Data processing (Python package + files)
│   ├── __init__.py
│   ├── preprocessing.py             #   Geocoding and student data processing
│   ├── point_generation.py          #   K-means + elbow method
│   ├── raw/                         #   Raw input data (student CSVs)
│   ├── processed/                   #   Processed / intermediate data
│   └── output/
│       ├── csv/                     #   Results in CSV format
│       └── text/                    #   Route logs in text format
│
├── vrptw/                           # Optimization model (core package)
│   ├── __init__.py
│   ├── config.py                    #   Centralized parameters (change here!)
│   ├── model_builder.py             #   MILP orchestration (build_model)
│   ├── solver.py                    #   Solving loop + subtour elimination
│   ├── postprocessing.py            #   Trip re-sequencing / vehicle minimization
│   ├── validation.py                #   Input & solution feasibility checks
│   ├── utils.py                     #   Haversine, distance matrix, routes
│   │
│   ├── variables/                   #   Decision variable definitions
│   │   ├── __init__.py              #     EXECUTION_ORDER registry
│   │   ├── travels.py               #     x[k,i,j] — arc variables
│   │   ├── service.py               #     s[k,i]   — service start times
│   │   └── load.py                  #     q[k,i]   — vehicle loads
│   │
│   └── constraints/                 #   Constraint definitions
│       ├── __init__.py              #     EXECUTION_ORDER registry
│       ├── capacity.py              #     Vehicle capacity limit
│       ├── demand.py                #     Client demand satisfaction
│       ├── visit_required.py        #     Load ↔ travel linking
│       ├── depot.py                 #     Depot departure
│       ├── flow_conservation.py     #     In-flow = out-flow
│       ├── single_pass.py           #     At most one visit per node
│       ├── time_windows.py          #     Big-M time-window bounds
│       └── no_self_loops.py         #     Safety guard (i ≠ j)
│
├── tests/                           # Test suite (pytest)
│   ├── conftest.py                  #   Shared fixtures (trivial, small, infeasible)
│   ├── test_model_builder.py        #   Model sanity + variable/constraint registry
│   ├── test_validation.py           #   Input & solution validation
│   ├── test_utils.py                #   Haversine, distances, route extraction
│   ├── test_postprocessing.py       #   Partition generation
│   └── test_point_generation.py     #   Elbow detection
│
├── src/                             # Auxiliary scripts (individual steps)
│   ├── 01_preprocess_data.py
│   ├── 02_generate_points.py
│   ├── 03_solve_vrptw.py
│   └── 04_resequence_trips.py
│
└── imgs/                            # Generated charts (elbow method)
```

## Architecture

The model builder (`model_builder.py`) uses a **pluggable registry** pattern
for both variables and constraints. Each group lives in its own file inside
`vrptw/variables/` or `vrptw/constraints/`, and an `EXECUTION_ORDER` list in
the respective `__init__.py` controls the creation/addition sequence.

At build time, `model_builder.py` loops through the registries:

```
VARIABLE_ORDER loop  →  variables dict  →  CONSTRAINT_ORDER loop
```

All variable dictionaries are collected into a single `dict` and forwarded to
every constraint function via `**kwargs`, so each function picks exactly the
variable groups it needs.

### Adding a new variable group

1. Create `vrptw/variables/my_vars.py`:

```python
def create_my_vars(model, *, model_data, **kwargs):
    my_var = { ... }
    return {"my_var": my_var}
```

2. Import it in `vrptw/variables/__init__.py` and append to `EXECUTION_ORDER`.

### Adding a new constraint

1. Create `vrptw/constraints/my_constraint.py`:

```python
def add_my_constraint(model, *, travels, model_data, **kwargs):
    ...
```

2. Import it in `vrptw/constraints/__init__.py` and append to `EXECUTION_ORDER`.

No changes to `model_builder.py` are needed in either case.

## Prerequisites

- **Python 3.10+**
- **IBM ILOG CPLEX** (optimization solver) — required by `docplex`
- **Google Maps API** key (for geocoding in Step 1 only)

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
| `MIP_GAP` | Acceptable MIP relative gap | 0.00 |
| `SOLVER_THREADS` | CPLEX parallel threads | 4 |
| `SOLVER_LOG_OUTPUT` | Print CPLEX log to stdout | True |
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

# LP relaxation — compute lower bounds for all scenarios
python run_pipeline.py --skip-preprocess --skip-points --relax
```

Alternatively, each step can be run individually via `src/`:

```bash
python src/01_preprocess_data.py
python src/02_generate_points.py --filter tec --shift ENTRY
python src/03_solve_vrptw.py
python src/03_solve_vrptw.py --relax   # LP relaxation only
python src/04_resequence_trips.py
```

### LP relaxation mode

Passing `--relax` relaxes all binary and integer variables to continuous,
producing a linear program whose optimal value is a **lower bound** on the
MIP objective. This is useful for:

- Estimating solution quality (comparing MIP objective vs. LP bound).
- Fast feasibility screening of large instances.
- Sensitivity analysis without the cost of integer solving.

Relaxation mode automatically skips post-processing (step 4) since there
are no integer routes to re-sequence. Output files are prefixed with
`relaxed_` so they never overwrite regular solutions.

## Mathematical Formulation

The MILP model follows the classical VRPTW formulation:

- **Decision variables:**
  - `x[k,i,j]` ∈ {0,1} — vehicle *k* travels from node *i* to node *j*
  - `s[k,i]` ∈ R — service start time at node *i* by vehicle *k*
  - `q[k,i]` ∈ Z — load served at node *i* by vehicle *k*

- **Objective function:** minimize total travel time (sum of `x[k,i,j] * t[i,j]`)

- **Constraints:**

  | # | Constraint | Description |
  |---|-----------|-------------|
  | 1 | Capacity | Total load per vehicle ≤ capacity |
  | 2 | Demand | Each client's demand is fully served |
  | 3 | Visit required | A node must be visited to be served |
  | 4 | Depot departure | Vehicles depart from the depot |
  | 5 | Flow conservation | Vehicles that enter a node must leave it |
  | 6 | Single pass | Each vehicle visits each node at most once |
  | 7 | Time windows | Big-M linearization of arrival-time implications |
  | 8 | No self-loops | Safety guard (`i ≠ j`, redundant with sparse variables) |

  Subtour elimination is handled via iterative **cutting planes** added
  during the solving loop.

## Testing

Run the test suite with `pytest`:

```bash
pytest tests/ -v
```

Tests that require the CPLEX runtime are automatically skipped when it is
not available. All other tests (validation, utilities, registry structure)
run without a solver.

## Output

- `data/output/csv/solution_cvrptw_<instance>_<type>.csv` — summary per scenario
- `data/output/csv/detailed_solution_cvrptw_<instance>_<type>.csv` — details per route
- `data/output/csv/solution_adjusted.csv` — solution with minimized vehicles
- `data/output/text/solution_cvrptw_<instance>_<type>.txt` — textual route log

## Author

Vinícius Braga Diniz — contato.vbd@gmail.com
