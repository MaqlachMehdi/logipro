# VRPPD Solver — Architecture & Extension Guide

## Overview

```
vrppd_data.json
      │
      ▼
build_problem()  →  Problem
                        │
                        ▼
              build_pulp_problem()  →  pulp_problem  ──► .solve()
                                                              │
                                                              ▼
                                           make_result_from_pulp_result()
                                                              │
                                                              ▼
                                                           Result
                                                              │
                                                              ▼
                                                       render_html()  →  solution.html
```

---

## Core data structures

### `Problem` (`solver/problem.py`)
Domain model: nodes, edges, vehicles, constraints parameters.

| Field | Type | Description |
|---|---|---|
| `deposit_node` | `DepositNode` | The depot |
| `delivery_nodes` | `list[DeliveryNode]` | Drop-off nodes (one per venue) |
| `recovery_nodes` | `list[RecoveryNode]` | Pick-up nodes (one per venue) |
| `oriented_edges` | `OrientedEdges` | Distance (km) and travel time (min) for all pairs |
| `vehicles_dict` | `dict[plate, Vehicle]` | Fleet |
| `loss_params` | `LossParams` | Objective weights |
| `time_margin` | `TimeMargin` | Safety margins around concert times |

### `Result` (`solver/solver.py`)
The output of a solved optimisation run.

| Field | Type | Description |
|---|---|---|
| `data` | `dict[plate, Trajectory]` | One trajectory per active vehicle |
| `problem` | `Problem` | Reference to the domain problem |
| `pulp_problem` | `pulp.LpProblem` | Solved PuLP model (for status, objective) |

### `Trajectory` (`models/trajectories.py`)
The ordered route of one vehicle.

| Field | Type | Description |
|---|---|---|
| `vehicle_id` | `str` | Vehicle plate |
| `departure_nodes` | `list[Node]` | Node left at each step — first entry is always the depot |
| `arrival_nodes` | `list[Node]` | Node arrived at each step — last entry is the depot |

The ordered sequence of visited nodes is:
```
departure_nodes[0]  +  arrival_nodes
= [depot, stop_1, stop_2, ..., stop_k, depot]
```

Each `(departure_nodes[i], arrival_nodes[i])` pair describes one edge:
```
Departure from <departure_nodes[i]>  ──►  Arrival at <arrival_nodes[i]>
```

---

## Node types (`models/graph.py`)

| Class | `get_id_for_pulp()` | Meaning |
|---|---|---|
| `DepositNode` | `"0"` | The depot |
| `DeliveryNode` | `"<id>-D"` | Drop-off instruments before concert |
| `RecoveryNode` | `"<id>-R"` | Pick-up instruments after concert |

`DeliveryNode` and `RecoveryNode` share the same integer `id` (= venue id) but have distinct PuLP identifiers so they are treated as separate stops.

---

## How to add new data to `Trajectory`

All enrichments live in `Trajectory` and are consumed by `render_html` via `getattr`.
This means **the visualizer never needs to change its signature** — it picks up new fields automatically.

### Example: add arrival times

**1. Compute the values** in `make_result_from_pulp_result` (solver.py):

```python
# after building the trajectory
arrival_times = [
    int(pulp.value(times_arrival[node.get_id_for_pulp(), plate]))
    for node in trajectory.arrival_nodes
]
trajectory.arrival_times = arrival_times      # attach directly
```

**2. Declare the field** in `Trajectory` (models/trajectories.py):

```python
@dataclass
class Trajectory:
    vehicle_id:      str
    arrival_nodes:   list[Node]
    departure_nodes: list[Node]
    arrival_times:   list[int] | None = None   # minutes since midnight
```

**3. Surface it in the HTML popup** (visualize.py, inside the marker loop):

`render_html` already reads `getattr(trajectory, "arrival_times", None)` — just add it to the popup string when it is not `None`.

### Same pattern for other future fields

| Field | Type | Notes |
|---|---|---|
| `departure_times` | `list[int]` | minutes, aligned with `departure_nodes` |
| `load_at_arrival` | `list[float]` | m³ on board upon arrival at each node |
| `wait_times` | `list[int]` | minutes waiting at each node for the time window |

---

## Visualizer (`visualize.py`)

```python
render_html(result, data, output_path)
```

| Parameter | Required | Description |
|---|---|---|
| `result` | yes | Solved `Result` object |
| `data` | no (pass `None`) | Raw JSON dict — used only for venue names & addresses |
| `output_path` | yes | Path to write `.html` |

The function reads `solve_status` and `objective_value` directly from `result.pulp_problem` when not provided explicitly.
