#!/usr/bin/env python3
"""
loss_viz.py — Analyse du paysage de la fonction de loss VRPPD.

Usage
-----
    python loss_viz.py --data vrppd_data.json

Options
-------
    --data        Chemin vers le JSON d'entrée   (défaut : vrppd_data.json)
    --output      HTML de sortie                 (défaut : loss_analysis.html)
    --grid N      Résolution de la grille, N∈[3..8]  (défaut : 5)
    --time-limit  Secondes CBC par run           (défaut : 60)
    --cache       Fichier .pkl pour sauvegarder / recharger les runs

Visualisations générées (HTML Plotly auto-contenu)
---------------------------------------------------
    1) Surface 3D  alpha_time × alpha_dist → Loss   (alpha_load fixé)
    2) Surface 3D  alpha_dist × alpha_load → Loss   (alpha_time fixé)
    3) Carte de sensibilité  |∂L/∂αᵢ| via différences finies centrées
    4) Heatmap de stabilité  std(Loss) locale sur chaque cellule
"""

from __future__ import annotations

import sys
import json
import pickle
import time
import traceback
import argparse
from pathlib import Path
from itertools import product

import re

import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

import pulp

# ── Import depuis le package solver (même dossier que ce fichier) ─────────────
_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

from solver.problem        import build_problem, TimeMargin   # noqa: E402
from solver.lip_solver     import (                           # noqa: E402
    build_pulp_problem,
    solve_with_progress,
    make_result_from_pulp_result,
)
from solver.loss_functions import MixedUsedTotalDistAndTime   # noqa: E402

# ── Constantes ────────────────────────────────────────────────────────────────
DEF_GRID        = 5      # points par axe
DEF_TIME_LIMIT  = 100     # secondes CBC par run
ALPHA_LOAD_FIX  = 0.20   # alpha_load fixé pour le graphe 1
ALPHA_TIME_FIX  = 0.50   # alpha_time fixé pour le graphe 2
REF_ALPHA       = (0.5, 0.3, 0.2)   # (alpha_time, alpha_dist, alpha_load)
FD_STEP         = 0.10   # pas ε pour les différences finies

PARAM_LABELS = {
    "alpha_time": "α_time",
    "alpha_dist": "α_dist",
    "alpha_load": "α_load",
}

# ─────────────────────────────────────────────────────────────────────────────
# Run unique
# ─────────────────────────────────────────────────────────────────────────────

def single_run(
    data: dict,
    at: float,
    ad: float,
    al: float,
    time_limit: int,
) -> dict | None:
    """
    Lance le solveur avec (alpha_time=at, alpha_dist=ad, alpha_load=al).

    Renvoie un dict :
        obj            – valeur de l'objectif PuLP (loss normalisée)
        total_dist_km  – distance totale parcourue (km)
        max_time_min   – durée max d'un véhicule actif (min)
        n_vehicles     – nombre de véhicules utilisés
    ou None si infaisable / erreur.
    """
    try:
        loss_fn = MixedUsedTotalDistAndTime(
            alpha_time=at,
            alpha_distance=ad,
            alpha_load=al,
        )
        problem = build_problem(data, loss_fn, TimeMargin(), recall_api=False)
        lp, edges = build_pulp_problem(problem, verbose=False)
        solve_with_progress(lp, problem, edges, verbose=False, time_limit=time_limit)

        obj = pulp.value(lp.objective)
        if obj is None:
            return None  # aucune solution trouvée dans le délai

        result     = make_result_from_pulp_result(lp, problem)
        total_dist = 0.0
        max_time   = 0.0
        n_veh      = 0

        for plate, traj in result.data.items():
            dep_t = result.get_depot_departure_time(plate)
            arr_t = result.get_depot_arrival_time(plate)
            if dep_t is not None and arr_t is not None:
                max_time = max(max_time, arr_t - dep_t)
                n_veh   += 1
            # distances: edges departure_nodes[i] → arrival_nodes[i]
            for dn, an in zip(traj.departure_nodes, traj.arrival_nodes):
                total_dist += problem.oriented_edges.distances_km.get(
                    (dn.id, an.id), 0.0
                )

        return dict(
            obj=float(obj),
            total_dist_km=total_dist,
            max_time_min=max_time,
            n_vehicles=n_veh,
        )

    except Exception:
        print("  [EXCEPTION]")
        traceback.print_exc()
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Grille 2-D avec cache
# ─────────────────────────────────────────────────────────────────────────────

def run_grid(
    data: dict,
    alpha_vals: np.ndarray,
    time_limit: int,
    cache: dict,
    mode: str,          # 'plot1' | 'plot2'
) -> tuple[np.ndarray, np.ndarray]:
    """
    Parcourt une grille N×N et renvoie deux tableaux (N,N) :
        Z_obj   – valeur de l'objectif
        Z_dist  – distance totale (km)

    Convention Plotly : z[i, j] correspond à (x[j], y[i]).
    ├─ mode='plot1' → x=alpha_time, y=alpha_dist   (alpha_load fixé)
    └─ mode='plot2' → x=alpha_dist, y=alpha_load   (alpha_time fixé)
    """
    N     = len(alpha_vals)
    Z_obj  = np.full((N, N), np.nan)
    Z_dist = np.full((N, N), np.nan)
    total  = N * N
    idx    = 0

    for i, ay in enumerate(alpha_vals):   # y-axis
        for j, ax in enumerate(alpha_vals):  # x-axis
            idx += 1
            if mode == "plot1":
                at, ad, al = float(ax), float(ay), ALPHA_LOAD_FIX
                label = f"α_t={at:.2f}  α_d={ad:.2f}  α_l={al:.2f}"
            else:
                at, ad, al = ALPHA_TIME_FIX, float(ax), float(ay)
                label = f"α_t={at:.2f}  α_d={ad:.2f}  α_l={al:.2f}"

            key = (round(at, 4), round(ad, 4), round(al, 4))

            if key in cache:
                res = cache[key]
            else:
                print(
                    f"  [{idx:>3}/{total}]  {label} ... ",
                    end="", flush=True,
                )
                t0  = time.perf_counter()
                res = single_run(data, at, ad, al, time_limit)
                dt  = time.perf_counter() - t0
                if res:
                    print(f"obj={res['obj']:.4f}  dist={res['total_dist_km']:.1f}km  ({dt:.1f}s)")
                else:
                    print(f"INFAISABLE  ({dt:.1f}s)")
                cache[key] = res

            if res is not None:
                Z_obj [i, j] = res["obj"]
                Z_dist[i, j] = res["total_dist_km"]

    return Z_obj, Z_dist


# ─────────────────────────────────────────────────────────────────────────────
# Sensibilité  ∂L/∂αᵢ  —  différences finies centrées
# ─────────────────────────────────────────────────────────────────────────────

def compute_sensitivity(
    data: dict,
    ref: tuple[float, float, float],
    eps: float,
    time_limit: int,
    cache: dict,
) -> dict[str, float]:
    """
    Calcule |∂L/∂αᵢ| en (alpha_time, alpha_dist, alpha_load) = ref,
    via différences finies centrées d'amplitude eps.

    Renvoie {param_name: gradient_value} (valeur signée).
    """
    at0, ad0, al0 = ref
    params = [
        ("alpha_time", at0, ad0, al0, 0),
        ("alpha_dist", at0, ad0, al0, 1),
        ("alpha_load", at0, ad0, al0, 2),
    ]
    grads: dict[str, float] = {}

    for name, *triplet_base, dim_idx in params:
        results: dict[str, float | None] = {}
        for sign, tag in [(+1, "hi"), (-1, "lo")]:
            t = list(ref)
            t[dim_idx] = float(np.clip(ref[dim_idx] + sign * eps, 0.0, 1.0))
            key = tuple(round(v, 4) for v in t)

            if key not in cache:
                print(
                    f"  [sens {name:>12s} {tag}]  "
                    f"α_t={t[0]:.2f}  α_d={t[1]:.2f}  α_l={t[2]:.2f} ... ",
                    end="", flush=True,
                )
                t0  = time.perf_counter()
                res = single_run(data, t[0], t[1], t[2], time_limit)
                dt  = time.perf_counter() - t0
                print(f"{'obj='+f'{res[\"obj\"]:.4f}' if res else 'FAIL'}  ({dt:.1f}s)")
                cache[key] = res

            res = cache[key]
            results[tag] = res["obj"] if res else None

        lo_v, hi_v = results["lo"], results["hi"]
        if lo_v is not None and hi_v is not None:
            # Use actual step (may be smaller near boundaries)
            t_lo = list(ref); t_lo[dim_idx] = float(np.clip(ref[dim_idx] - eps, 0.0, 1.0))
            t_hi = list(ref); t_hi[dim_idx] = float(np.clip(ref[dim_idx] + eps, 0.0, 1.0))
            actual_step = t_hi[dim_idx] - t_lo[dim_idx]
            grads[name] = (hi_v - lo_v) / (actual_step if actual_step > 0 else eps)
        else:
            grads[name] = float("nan")

    return grads


# ─────────────────────────────────────────────────────────────────────────────
# Heatmap de stabilité : std locale 3×3
# ─────────────────────────────────────────────────────────────────────────────

def compute_stability(Z: np.ndarray) -> np.ndarray:
    """
    Pour chaque cellule (i,j), calcule l'écart-type de Z dans le voisinage 3×3.
    Valeur élevée → la loss varie fortement quand les alphas varient légèrement.
    """
    N = Z.shape[0]
    S = np.full_like(Z, np.nan)
    for i in range(N):
        for j in range(N):
            patch = [
                Z[ni, nj]
                for di in (-1, 0, 1)
                for dj in (-1, 0, 1)
                if 0 <= (ni := i + di) < N and 0 <= (nj := j + dj) < N
                and not np.isnan(Z[ni, nj])
            ]
            if len(patch) > 1:
                S[i, j] = float(np.std(patch, ddof=0))
    return S


# ─────────────────────────────────────────────────────────────────────────────
# Construction HTML
# ─────────────────────────────────────────────────────────────────────────────

_DARK_BG   = "#0f172a"
_CARD_BG   = "#1e293b"
_BORDER    = "#334155"
_TEXT      = "#e2e8f0"
_SUBTEXT   = "#94a3b8"

_LAYOUT_BASE = dict(
    paper_bgcolor=_CARD_BG,
    plot_bgcolor=_CARD_BG,
    font=dict(color=_TEXT, family="Inter, Arial, sans-serif", size=12),
    margin=dict(l=20, r=20, t=60, b=20),
)

_SCENE_BASE = dict(
    paper_bgcolor=_CARD_BG,
    scene=dict(
        bgcolor=_CARD_BG,
        xaxis=dict(gridcolor=_BORDER, zerolinecolor=_BORDER),
        yaxis=dict(gridcolor=_BORDER, zerolinecolor=_BORDER),
        zaxis=dict(gridcolor=_BORDER, zerolinecolor=_BORDER),
    ),
)


def _fig_to_div(fig: go.Figure, div_id: str) -> str:
    return fig.to_html(
        full_html=False,
        include_plotlyjs=False,
        div_id=div_id,
        config=dict(responsive=True, displayModeBar=True),
    )


def build_html(
    alpha_vals: np.ndarray,
    Z1_obj:   np.ndarray,
    Z1_dist:  np.ndarray,
    Z2_obj:   np.ndarray,
    Z2_dist:  np.ndarray,
    grads:    dict[str, float],
    Z_stab1:  np.ndarray,
    Z_stab2:  np.ndarray,
    data_info: str,
    n_runs:    int,
    ref:       tuple,
) -> str:
    """Assemble les quatre figures en un HTML autonome."""
    avr = [round(float(v), 3) for v in alpha_vals]

    # ── Figure 1 : Surface 3D  alpha_time × alpha_dist ──────────────────────
    fig1 = go.Figure()
    fig1.add_trace(go.Surface(
        x=avr, y=avr, z=Z1_obj,
        name="Loss",
        colorscale="Viridis",
        colorbar=dict(title="Loss", titleside="right", x=1.02),
        hovertemplate=(
            "α_time=%{x:.2f}<br>"
            "α_dist=%{y:.2f}<br>"
            "Loss=%{z:.4f}<extra></extra>"
        ),
    ))
    fig1.update_layout(
        **_LAYOUT_BASE,
        **_SCENE_BASE,
        title=dict(
            text=f"Surface 3D — α_time × α_dist → Loss"
                 f"<br><sup>α_load fixé = {ALPHA_LOAD_FIX}</sup>",
            x=0.5,
        ),
        scene=dict(
            **_SCENE_BASE["scene"],
            xaxis_title="alpha_time",
            yaxis_title="alpha_dist",
            zaxis_title="Loss",
        ),
        height=520,
    )

    # ── Figure 2 : Surface 3D  alpha_dist × alpha_load ──────────────────────
    fig2 = go.Figure()
    fig2.add_trace(go.Surface(
        x=avr, y=avr, z=Z2_obj,
        name="Loss",
        colorscale="Cividis",
        colorbar=dict(title="Loss", titleside="right", x=1.02),
        hovertemplate=(
            "α_dist=%{x:.2f}<br>"
            "α_load=%{y:.2f}<br>"
            "Loss=%{z:.4f}<extra></extra>"
        ),
    ))
    fig2.update_layout(
        **_LAYOUT_BASE,
        **_SCENE_BASE,
        title=dict(
            text=f"Surface 3D — α_dist × α_load → Loss"
                 f"<br><sup>α_time fixé = {ALPHA_TIME_FIX}</sup>",
            x=0.5,
        ),
        scene=dict(
            **_SCENE_BASE["scene"],
            xaxis_title="alpha_dist",
            yaxis_title="alpha_load",
            zaxis_title="Loss",
        ),
        height=520,
    )

    # ── Figure 3 : Sensibilité  |∂L/∂αᵢ| ────────────────────────────────────
    valid   = {k: v for k, v in grads.items() if not np.isnan(v)}
    names3  = [PARAM_LABELS[k] for k in valid]
    raw_g   = list(valid.values())
    abs_g   = [abs(v) for v in raw_g]
    colors3 = ["#f97316" if v > 0 else "#38bdf8" for v in raw_g]
    signs3  = [f"{'↑' if v > 0 else '↓'} {v:+.4f}" for v in raw_g]

    fig3 = go.Figure()
    fig3.add_trace(go.Bar(
        x=names3,
        y=abs_g,
        marker_color=colors3,
        marker_line=dict(width=0),
        text=signs3,
        textposition="outside",
        hovertemplate="%{x}<br>|∂L/∂θ| = %{y:.4f}<extra></extra>",
    ))
    fig3.update_layout(
        **_LAYOUT_BASE,
        title=dict(
            text=(
                "Carte de sensibilité — |∂L/∂αᵢ|"
                f"<br><sup>Ref = "
                f"(α_t={ref[0]}, α_d={ref[1]}, α_l={ref[2]})  "
                f"ε = {FD_STEP}   "
                "🟠 gradient positif  🔵 gradient négatif</sup>"
            ),
            x=0.5,
        ),
        yaxis=dict(
            title="Indice de sensibilité |∂L/∂αᵢ|",
            gridcolor=_BORDER,
        ),
        xaxis=dict(title="Paramètre"),
        showlegend=False,
        height=420,
    )

    # ── Figure 4 : Heatmaps de stabilité ─────────────────────────────────────
    fig4 = make_subplots(
        rows=1, cols=2,
        subplot_titles=[
            f"Stabilité : α_time × α_dist  (α_load={ALPHA_LOAD_FIX})",
            f"Stabilité : α_dist × α_load  (α_time={ALPHA_TIME_FIX})",
        ],
        horizontal_spacing=0.12,
    )
    heat_kw = dict(
        colorscale="YlOrRd",
        showscale=True,
        hoverongaps=False,
        zmin=0,
    )
    fig4.add_trace(go.Heatmap(
        x=avr, y=avr, z=Z_stab1,
        colorbar=dict(title="std(Loss)", x=0.44, len=0.9),
        hovertemplate="α_time=%{y:.2f}<br>α_dist=%{x:.2f}<br>std=%{z:.4f}<extra></extra>",
        **heat_kw,
    ), row=1, col=1)
    fig4.add_trace(go.Heatmap(
        x=avr, y=avr, z=Z_stab2,
        colorbar=dict(title="std(Loss)", x=1.0, len=0.9),
        hovertemplate="α_dist=%{y:.2f}<br>α_load=%{x:.2f}<br>std=%{z:.4f}<extra></extra>",
        **heat_kw,
    ), row=1, col=2)
    fig4.update_xaxes(title_text="alpha_time", gridcolor=_BORDER, row=1, col=1)
    fig4.update_yaxes(title_text="alpha_dist", gridcolor=_BORDER, row=1, col=1)
    fig4.update_xaxes(title_text="alpha_dist", gridcolor=_BORDER, row=1, col=2)
    fig4.update_yaxes(title_text="alpha_load", gridcolor=_BORDER, row=1, col=2)
    fig4.update_layout(
        **_LAYOUT_BASE,
        title=dict(
            text="Heatmap de Stabilité — std locale de la Loss dans le voisinage 3×3",
            x=0.5,
        ),
        height=440,
    )
    # Apply dark background to subplot annotations
    for ann in fig4.layout.annotations:
        ann.font = dict(color=_TEXT)

    # ── Combiner en HTML ──────────────────────────────────────────────────────
    # Récupère l'URL CDN exacte du plotly.js embarqué dans le package installé
    try:
        _h = go.Figure().to_html(full_html=True, include_plotlyjs="cdn")
        _m = re.search(r'src="([^"]+plotly[^"]+)"', _h)
        cdn = _m.group(1) if _m else "https://cdn.plot.ly/plotly-3.4.0.min.js"
    except Exception:
        cdn = "https://cdn.plot.ly/plotly-3.4.0.min.js"

    html = f"""\
<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>VRPPD — Analyse de la Loss</title>
  <script src="{cdn}"></script>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: 'Inter', Arial, sans-serif;
      background: {_DARK_BG};
      color: {_TEXT};
      min-height: 100vh;
    }}
    header {{
      background: {_CARD_BG};
      border-bottom: 1px solid {_BORDER};
      padding: 18px 32px;
      display: flex;
      align-items: center;
      gap: 16px;
    }}
    header .logo {{
      font-size: 1.5rem;
      font-weight: 800;
      background: linear-gradient(135deg, #6366f1, #38bdf8);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
    }}
    header .meta {{ font-size: 0.82rem; color: {_SUBTEXT}; margin-top: 2px; }}
    header .meta b {{ color: {_TEXT}; }}
    .grid {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 16px;
      padding: 20px;
    }}
    .card {{
      background: {_CARD_BG};
      border: 1px solid {_BORDER};
      border-radius: 12px;
      overflow: hidden;
    }}
    .card.full {{ grid-column: span 2; }}
    .card .inner {{ padding: 4px; }}
    @media (max-width: 900px) {{
      .grid {{ grid-template-columns: 1fr; }}
      .card.full {{ grid-column: span 1; }}
    }}
  </style>
</head>
<body>
  <header>
    <div>
      <div class="logo">VRPPD · Analyse de Loss</div>
      <div class="meta">
        <b>{data_info}</b> &nbsp;·&nbsp;
        Modèle : <b>MixedUsedTotalDistAndTime</b> &nbsp;·&nbsp;
        <b>{n_runs}</b> runs réussis &nbsp;·&nbsp;
        Grille : <b>{len(alpha_vals)}×{len(alpha_vals)}</b>
      </div>
    </div>
  </header>

  <div class="grid">
    <div class="card"><div class="inner">{_fig_to_div(fig1, 'fig1')}</div></div>
    <div class="card"><div class="inner">{_fig_to_div(fig2, 'fig2')}</div></div>
    <div class="card"><div class="inner">{_fig_to_div(fig3, 'fig3')}</div></div>
    <div class="card full"><div class="inner">{_fig_to_div(fig4, 'fig4')}</div></div>
  </div>
</body>
</html>"""
    return html


# ─────────────────────────────────────────────────────────────────────────────
# Point d'entrée
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--data",        default="vrppd_data.json", help="JSON d'entrée")
    parser.add_argument("--output",      default="loss_analysis.html", help="HTML de sortie")
    parser.add_argument("--grid",        type=int, default=DEF_GRID,        help="Résolution par axe")
    parser.add_argument("--time-limit",  type=int, default=DEF_TIME_LIMIT,  dest="time_limit",
                        help="Secondes CBC par run")
    parser.add_argument("--cache",       default=None, help=".pkl cache pour éviter de relancer tous les runs")
    args = parser.parse_args()

    # ── Chargement des données ────────────────────────────────────────────────
    data_path = Path(args.data)
    if not data_path.exists():
        parser.error(f"Fichier introuvable : {data_path}")
    with open(data_path, encoding="utf-8") as fh:
        data = json.load(fh)

    n_venues   = sum(1 for loc in data.get("locations", []) if loc.get("id", -1) != 0)
    n_vehicles = sum(1 for v in data.get("vehicles", []) if v.get("is_available", 0))
    data_info  = f"{n_venues} lieux · {n_vehicles} véhicules disponibles"

    total_est  = 2 * args.grid ** 2 + 6   # grilles + sensibilité
    print(f"\n{'═'*62}")
    print(f"  VRPPD · Analyse du paysage de Loss")
    print(f"  {data_info}")
    print(f"  Grille : {args.grid}×{args.grid} · Temps limite : {args.time_limit}s/run")
    print(f"  Runs estimés : ~{total_est}  (max {total_est * args.time_limit}s si aucun cache)")
    print(f"{'═'*62}\n")

    # ── Cache ─────────────────────────────────────────────────────────────────
    cache: dict = {}
    if args.cache:
        cache_path = Path(args.cache)
        if cache_path.exists():
            with open(cache_path, "rb") as fh:
                cache = pickle.load(fh)
            print(f"[cache] {len(cache)} résultats chargés depuis {cache_path}\n")

    alpha_vals = np.linspace(0.0, 1.0, args.grid)

    # ── Grille 1 : alpha_time (x) × alpha_dist (y) ───────────────────────────
    print("── Grille 1 : alpha_time × alpha_dist ─────────────────────────────")
    Z1_obj, Z1_dist = run_grid(data, alpha_vals, args.time_limit, cache, "plot1")

    # ── Grille 2 : alpha_dist (x) × alpha_load (y) ───────────────────────────
    print("\n── Grille 2 : alpha_dist × alpha_load ─────────────────────────────")
    Z2_obj, Z2_dist = run_grid(data, alpha_vals, args.time_limit, cache, "plot2")

    # ── Sensibilité ───────────────────────────────────────────────────────────
    print(f"\n── Sensibilité au point de référence {REF_ALPHA} ────────────────")
    grads = compute_sensitivity(data, REF_ALPHA, FD_STEP, args.time_limit, cache)
    for name, g in grads.items():
        if not np.isnan(g):
            print(f"   ∂L/∂{name:<12s} = {g:+.4f}   |∂L/∂θᵢ| = {abs(g):.4f}")
        else:
            print(f"   ∂L/∂{name:<12s} = N/A (run infaisable)")

    # ── Stabilité ─────────────────────────────────────────────────────────────
    Z_stab1 = compute_stability(Z1_obj)
    Z_stab2 = compute_stability(Z2_obj)

    # ── Sauvegarde du cache ───────────────────────────────────────────────────
    if args.cache:
        with open(Path(args.cache), "wb") as fh:
            pickle.dump(cache, fh)
        print(f"\n[cache] {len(cache)} résultats sauvegardés → {args.cache}")

    # ── Génération HTML ───────────────────────────────────────────────────────
    n_ok  = sum(1 for v in cache.values() if v is not None)
    html  = build_html(
        alpha_vals, Z1_obj, Z1_dist, Z2_obj, Z2_dist,
        grads, Z_stab1, Z_stab2,
        data_info, n_ok, REF_ALPHA,
    )
    out = Path(args.output)
    out.write_text(html, encoding="utf-8")
    print(f"\n✓  HTML généré → {out.resolve()}")
    print(f"   Ouvrez ce fichier dans un navigateur pour voir les visualisations.\n")


if __name__ == "__main__":
    main()
