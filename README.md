# InTheFlow

> Logistics optimization platform for live event touring — solving the Vehicle Routing Problem with Pickup and Delivery (VRPPD) for touring crews managing equipment across multiple concert venues.

**Live:** [intheflow.site](https://intheflow.site)

---

## Overview

InTheFlow automates the logistics planning for concert touring: given a set of venues, a gear inventory per venue, and a fleet of vehicles, it computes the optimal delivery and recovery schedule that minimizes travel time, distance, or vehicle count depending on the operator's priority.

The core challenge is a **VRPPD with time windows** — an NP-hard combinatorial optimization problem. The solver reformulates it as a **Mixed Integer Linear Program (MILP)** and delegates to a branch-and-bound CBC solver, augmented with a greedy warm-start heuristic to significantly reduce solve time.

---

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│                        Nginx (HTTPS)                      │
│              TLS termination · reverse proxy              │
└────────────────────┬─────────────────┬───────────────────┘
                     │                 │
              /static files      /api/* proxy
                     │                 │
          ┌──────────┴──┐    ┌─────────┴──────────┐
          │  React SPA  │    │   Express (Node.js) │
          │   (Nginx)   │    │     + SQLite DB      │
          └─────────────┘    └─────────┬────────────┘
                                       │ stdin/stdout JSON
                             ┌─────────┴────────────┐
                             │    Python Solver      │
                             │  PuLP · CBC · OSRM   │
                             └──────────────────────┘
```

All services run in Docker containers orchestrated with Docker Compose. The solver is invoked as a subprocess by the Node.js backend — decoupled by design to allow independent scaling and language-level isolation.

---

## Tech Stack

### Frontend — `frontend/`

| Technology | Role |
|---|---|
| **React 19** | UI framework with hooks-based state management |
| **TypeScript** | Full static typing across the entire frontend |
| **Vite 7** | Build tooling with HMR and optimized production bundles |
| **Tailwind CSS v4** | Utility-first styling with JIT compilation |
| **Leaflet** + leaflet-polylinedecorator | Interactive map with animated route overlays |
| **Lucide React** | Icon system |
| **ExcelJS / xlsx** | Client-side export to Excel |

**State management** is intentional `useReducer` at the App level — no external store. The data flow is unidirectional: API calls sync to SQLite on every mutation, localStorage serves only as a migration bridge.

**PDF generation** is done entirely client-side: solution data is serialized into a self-contained HTML document, opened in a new tab, and printed via `window.print()`. This avoids any server-side Chrome dependency and works across PC, Android, and iOS Safari.

---

### Backend — `backend/`

| Technology | Role |
|---|---|
| **Node.js** + **Express** | REST API server |
| **SQLite** (file-based) | Persistent storage for spots, vehicles, gears |
| **cookie-parser** | Cookie-based session handling (multi-user isolation) |
| **Nominatim** (OpenStreetMap) | Address geocoding — zero API cost |
| **Nginx** | Static file serving + HTTPS termination + API proxy |
| **Let's Encrypt** (Certbot) | Automated TLS certificate management |

**No ORM.** Queries are written with prepared statements directly against `better-sqlite3` for predictable performance and zero abstraction overhead.

The backend acts as a **data orchestrator**: on optimization requests, it reads the full problem state from SQLite, serializes it to JSON, and pipes it to the Python solver subprocess. Results come back as JSON on stdout and are persisted + returned to the client.

**Multi-user isolation** is achieved via a UUID stored in an HTTP cookie — no accounts, no passwords. Each user's data is partitioned in SQLite by `user_id`.

---

### Solver — `backend/solver/`

The solver is a standalone Python module invoked in `--api` mode. It reads a JSON problem definition from stdin and writes a JSON solution to stdout.

| Technology | Role |
|---|---|
| **Python 3.11+** | Solver runtime |
| **PuLP** | MILP modelling layer (problem declaration, variable/constraint DSL) |
| **CBC** (via PuLP) | Open-source branch-and-bound MILP solver |
| **OSRM** | Real road distance and travel time matrix (Open Source Routing Machine) |

#### Problem Formulation

The VRPPD is modelled as a binary edge-selection program:

- **Decision variables** `e[i,j,v] ∈ {0,1}` — vehicle `v` traverses edge `(i→j)`
- **Continuous variables** — arrival times and load levels at each node
- **Constraints** — flow conservation, time windows, capacity, pickup-before-delivery precedence, depot return
- **Warm start** — a greedy nearest-neighbour heuristic initializes the solver with a feasible solution, dramatically reducing the branch-and-bound tree

#### Objective Function

The objective is a **weighted normalized sum** of three terms:

```
min  α_time     × (max_vehicle_active_time / T_ref)
   + α_distance × (total_km / D_ref)
   + α_load     × (Σ km × capacity^(2/3) / normalization)
```

The `α_load` term uses a sublinear capacity weighting (`capacity^(2/3)`) that acts as a proxy for vehicle economy: it penalizes routing large partially-loaded vehicles, encouraging the solver to consolidate loads and use fewer trucks.

Four presets expose this to the user:

| Mode | α_time | α_distance | α_load | Intent |
|---|---|---|---|---|
| Équilibré | 0.4 | 0.3 | 0.3 | General purpose |
| Économie véhicules | 0.3 | 0.3 | 0.5 | Minimize fleet usage |
| Rapidité | 0.5 | 0.3 | 0.2 | Minimize makespan |
| Distance min | 0.3 | 0.5 | 0.2 | Minimize total km |

All three terms are normalized against problem-specific reference values (Frobenius norm of the distance matrix, ideal min-max time) so the α weights are **dimensionless and stable** across problem sizes.

#### OSRM Integration

Travel times and distances are fetched from a public OSRM instance using real road geometry — not Euclidean approximations. Results are cached to avoid redundant API calls across solver runs.

---

## Infrastructure

```
VPS (Ubuntu 22.04)
├── Docker Compose
│   ├── frontend  (nginx:alpine)  → :80, :443
│   └── backend   (node:22-slim)  → internal :5000
├── /etc/letsencrypt/             → mounted read-only into frontend container
└── backend/data/logipro.db       → mounted as bind volume (persisted on host)
```

**Deployment** is git-based: `git push` to the main branch, then `docker compose up -d --build` on the VPS rebuilds only the changed layers. The SQLite database is excluded from version control via `git update-index --skip-worktree` and persists across deploys via a Docker bind mount.

---

## Local Development

**Prerequisites:** Node.js 20+, Python 3.11+, Docker

```bash
# Frontend
cd frontend
npm install
npm run dev          # Vite dev server on :5173

# Backend
cd backend
npm install
node server.js       # Express on :5000

# Solver (standalone test)
cd backend/solver
python -m venv .venv && .venv/bin/pip install -r requirements.txt
echo '{"locations":[...],"vehicles":[...],"config":"equilibre"}' | python VRPPD.py --api
```

---

## Key Design Decisions

**Subprocess architecture for the solver** — Python was chosen for the solver for its scientific ecosystem (PuLP, NumPy). Rather than embedding a Python runtime in Node.js or using a message queue, the solver runs as a subprocess. This keeps the two runtimes cleanly separated, makes the solver independently testable, and avoids native addon complexity.

**SQLite over Postgres** — The workload is single-writer, read-heavy, and the data volume is small. SQLite eliminates infrastructure complexity (no connection pooling, no separate process) with zero performance cost at this scale. The database is a single file that travels with the application.

**No authentication system** — Users are identified by a UUID cookie. This deliberately trades security for frictionless onboarding. The trade-off is acceptable for a B2B tool used by small touring crews who share a single link.

**Client-side PDF** — Avoids the operational complexity of running Chrome (Puppeteer) inside a Docker container. The browser already has a PDF renderer; the server-side Puppeteer approach was an unnecessary dependency.
