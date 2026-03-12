"""
VRPPD solution visualizer — generates a self-contained HTML file.

Uses Leaflet.js + leaflet-polylinedecorator (CDN, no extra pip install).

Usage
-----
    from visualize import render_html
    render_html(result, data, "solution.html")

The only required inputs are a solved `Result` object and the raw `data` dict
(vrppd_data.json) for venue names / addresses.
Future enrichments (times, volumes, loads) are read directly from the
`Trajectory` objects inside `result` — see README.md for extension guidelines.
"""

import json

from solver.models.graph import DepositNode, DeliveryNode, RecoveryNode

# One color per vehicle (cycles if more than 8 vehicles)
_VEHICLE_COLORS = [
    "#e41a1c", "#377eb8", "#4daf4a", "#984ea3",
    "#ff7f00", "#a65628", "#f781bf", "#999999",
]



# ──────────────────────────────────────────────────────────────────────────────
# Private helpers
# ──────────────────────────────────────────────────────────────────────────────

def _hhmm(minutes: int) -> str:
    return f"{int(minutes) // 60:02d}h{int(minutes) % 60:02d}"


def _node_label(node, data: dict | None) -> str:
    if isinstance(node, DepositNode):
        return "Depot"
    if data:
        loc = next((l for l in data["locations"] if l["id"] == node.id), None)
        venue_name = loc["name"] if loc else f"#{node.id}"
    else:
        venue_name = f"#{node.id}"
    kind = "Delivery" if isinstance(node, DeliveryNode) else "Recovery"
    return f"{venue_name} — {kind}"


def _node_address(node, data: dict | None) -> str:
    if data is None:
        return ""
    ref_id = 0 if isinstance(node, DepositNode) else node.id
    loc = next((l for l in data["locations"] if l["id"] == ref_id), None)
    return loc["address"] if loc else ""


def _node_latlng(node) -> tuple[float, float] | None:
    """Return (lat, lon) with a small offset for RecoveryNodes so they don't
    stack exactly on top of the corresponding DeliveryNode."""
    if node.gps_coordinates is None:
        return None
    lat, lon = node.gps_coordinates
    if isinstance(node, RecoveryNode):
        lat += 0.0003
        lon += 0.0003
    return lat, lon


def _trajectory_ordered_nodes(trajectory) -> list:
    """
    Full ordered node list:  departure_nodes[0]  +  arrival_nodes
    = [depot, stop_1, ..., stop_k, depot]
    """
    return [trajectory.departure_nodes[0]] + list(trajectory.arrival_nodes)


def _get_load_time_data(result) -> tuple[dict, dict, dict, dict, dict]:
    """
    Get load and time data from Result object.
    Falls back to empty dicts if data is not available.

    Returns:
        loads_at_arrival: dict[(node_id, vehicle_id)] -> float
        times_arrival: dict[(node_id, vehicle_id)] -> float
        time_departure_depot: dict[vehicle_id] -> float
        time_arrival_depot: dict[vehicle_id] -> float
        loads_departure_depot: dict[vehicle_id] -> float
    """
    return (
        result.loads_at_arrival or {},
        result.times_arrival or {},
        result.time_departure_depot or {},
        result.time_arrival_depot or {},
        result.loads_departure_depot or {},
    )


def _build_vehicle_routes(result, color_map: dict, data: dict | None) -> list[dict]:
    """
    Build a list of vehicle-route dicts that will be JSON-serialised into the
    HTML.  Each dict carries the per-segment coordinate pairs so the JS can
    draw independent Bézier arcs with arrows.
    """
    problem = result.problem
    routes  = []

    # Get load/time data from Result
    loads_at_arrival, times_arrival, time_departure_depot, time_arrival_depot, loads_departure_depot = _get_load_time_data(result)

    for i, (plate, trajectory) in enumerate(result.data.items()):
        ordered = _trajectory_ordered_nodes(trajectory)
        if len(ordered) < 2:
            continue

        vehicle = problem.vehicles_dict[plate]

        segments: list[dict] = []
        for seg_idx, (node_a, node_b) in enumerate(zip(ordered[:-1], ordered[1:])):
            ll_a = _node_latlng(node_a)
            ll_b = _node_latlng(node_b)
            if ll_a is None or ll_b is None:
                continue

            # Get node labels
            from_label = _node_label(node_a, data)
            to_label = _node_label(node_b, data)

            # Use get_id_for_pulp() for lookups (includes -D/-R suffix for delivery/recovery)
            node_b_key = node_b.get_id_for_pulp()
            node_a_key = node_a.get_id_for_pulp()

            # Distance and travel time for this edge
            dist_km = problem.oriented_edges.distances_km.get((node_a.id, node_b.id))
            travel_time = problem.oriented_edges.travel_times_min.get((node_a.id, node_b.id))

            # === POST-PROCESS: Compute loads and times ===

            # Get arrival time at destination node B
            if isinstance(node_b, DepositNode):
                arrival_time_b = time_arrival_depot.get(plate)
            else:
                arrival_time_b = times_arrival.get((node_b_key, plate))

            # Compute departure time from A = arrival_time_at_B - travel_time
            if arrival_time_b is not None and travel_time is not None:
                departure_time_a = arrival_time_b - travel_time
            else:
                departure_time_a = None

            # Delta at nodes (volume change: + = pickup, - = dropoff)
            delta_at_a = -(node_a.required_volume or 0.0) if not isinstance(node_a, DepositNode) else 0.0
            delta_at_b = -(node_b.required_volume or 0.0) if not isinstance(node_b, DepositNode) else 0.0

            # Compute transported load (what's on truck during travel A→B)
            # Method: use load_at_arrival at B, which equals transported load (before operation at B)
            # For depot destination: compute from last node (load after operation)
            if isinstance(node_b, DepositNode):
                # Going TO depot: transported = load_at_arrival[A] - A.required_volume (load after op at A)
                load_at_arrival_a = loads_at_arrival.get((node_a_key, plate))
                if load_at_arrival_a is not None:
                    transported_load = load_at_arrival_a - (node_a.required_volume or 0.0)
                else:
                    transported_load = None
            elif isinstance(node_a, DepositNode):
                # Coming FROM depot: transported = load_at_arrival[B] (what arrives at B)
                transported_load = loads_at_arrival.get((node_b_key, plate))
            else:
                # Normal edge: transported = load_at_arrival[B]
                transported_load = loads_at_arrival.get((node_b_key, plate))

            segments.append({
                "coords": [list(ll_a), list(ll_b)],
                "from": from_label,
                "to": to_label,
                "transported_load": transported_load,
                "delta_at_departure": delta_at_a,
                "delta_at_arrival": delta_at_b,
                "departure_time": departure_time_a,
                "arrival_time": arrival_time_b,
                "distance_km": dist_km,
                "travel_time_min": travel_time,
                "step": seg_idx + 1,
            })

        if not segments:
            continue

        routes.append({
            "plate":     plate,
            "color":     color_map[plate],
            "capacity":  vehicle.max_volume,
            "segments":  segments,
        })

    return routes


# ──────────────────────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────────────────────

def render_html(
    result,
    data:            dict | None,
    output_path:     str,
    solve_status:    str        = "",
    objective_value: float | None = None,
) -> None:
    """
    Generate a self-contained HTML file visualizing the VRPPD solution.

    Parameters
    ----------
    result          : a solved Result object (solver.solver.Result)
    data            : raw dict loaded from vrppd_data.json (names/addresses);
                      pass None to skip venue labels
    output_path     : path to write the .html file
    solve_status    : e.g. "Optimal" (auto-read from result if omitted)
    objective_value : objective value (auto-read from result if omitted)

    Extension points (picked up automatically when present on Trajectory):
        arrival_times   : list[int]   — arrival time in minutes at each node
        load_at_arrival : list[float] — vehicle load (m³) upon arrival
    """
    import pulp

    problem  = result.problem
    vehicles = list(problem.vehicles_dict.values())
    color_map = {
        v.id: _VEHICLE_COLORS[i % len(_VEHICLE_COLORS)]
        for i, v in enumerate(vehicles)
    }

    if objective_value is None:
        objective_value = pulp.value(result.pulp_problem.objective)
    if not solve_status:
        solve_status = pulp.LpStatus[result.pulp_problem.status]

    # Map centre
    all_lats = [n.gps_coordinates[0] for n in problem.all_nodes if n.gps_coordinates]
    all_lons = [n.gps_coordinates[1] for n in problem.all_nodes if n.gps_coordinates]
    center_lat = sum(all_lats) / len(all_lats)
    center_lon = sum(all_lons) / len(all_lons)

    # ── Route data → JSON for the JS renderer ─────────────────────────────────
    vehicle_routes = _build_vehicle_routes(result, color_map, data)
    vehicle_routes_json = json.dumps(vehicle_routes, separators=(",", ":"))
    active_vehicle_count = len(vehicle_routes)

    # ── Legend HTML ───────────────────────────────────────────────────────────
    legend_rows_html = ""
    for route in vehicle_routes:
        plate   = route["plate"]
        color   = route["color"]
        vehicle = problem.vehicles_dict[plate]
        trajectory = result.data[plate]
        ordered    = _trajectory_ordered_nodes(trajectory)
        stop_names = " → ".join(_node_label(n, data) for n in ordered)
        edge_count = len(trajectory.arrival_nodes)
        legend_rows_html += (
            f'<div class="legend-item">'
            f'<span class="swatch" style="background:{color}"></span>'
            f'<div>'
            f'<b>{plate}</b>&nbsp;'
            f'<small style="color:#666">cap. {vehicle.max_volume}\u202fm³'
            f' · {edge_count} stops</small>'
            f'<br><small class="route-seq">{stop_names}</small>'
            f'</div></div>'
        )

    # ── Get load/time values for node popups ──────────────────────────────────
    loads_at_arrival, times_arrival, time_departure_depot, time_arrival_depot, loads_departure_depot = _get_load_time_data(result)

    # Build a mapping: node_id -> list of visit info dicts
    node_visit_info: dict[str, list] = {}
    for plate, trajectory in result.data.items():
        ordered = _trajectory_ordered_nodes(trajectory)
        veh_color = color_map.get(plate, "#999")
        for idx, node in enumerate(ordered):
            # Use get_id_for_pulp() for lookups (includes -D/-R suffix)
            node_key = node.get_id_for_pulp()

            if isinstance(node, DepositNode):
                if idx == 0:
                    # Departure from depot
                    arr_time = time_departure_depot.get(plate)
                    load = loads_departure_depot.get(plate)
                    visit_type = "Departure"
                else:
                    # Return to depot
                    arr_time = time_arrival_depot.get(plate)
                    load = loads_at_arrival.get((node_key, plate))
                    visit_type = "Return"
            else:
                arr_time = times_arrival.get((node_key, plate))
                load = loads_at_arrival.get((node_key, plate))
                visit_type = "Visit"

            if node.id not in node_visit_info:
                node_visit_info[node.id] = []
            node_visit_info[node.id].append({
                "plate": plate,
                "arrival_time": arr_time,
                "load": load,
                "color": veh_color,
                "visit_type": visit_type,
                "step": idx,
            })

    # ── Markers JS ────────────────────────────────────────────────────────────
    markers_js_lines: list[str] = []

    for node in problem.all_nodes:
        ll = _node_latlng(node)
        if ll is None:
            continue
        lat, lon = ll

        if isinstance(node, DepositNode):
            radius, fill_color, stroke_color = 13, "#333", "#fff"
            node_type = "Depot"
        elif isinstance(node, DeliveryNode):
            radius, fill_color, stroke_color = 10, "#1a7abf", "#0a4a7f"
            node_type = "Delivery (drop-off)"
        else:
            radius, fill_color, stroke_color = 10, "#c0392b", "#7f0000"
            node_type = "Recovery (pick-up)"

        tw     = node.time_window
        tw_str = f"{_hhmm(tw.start_minutes)} – {_hhmm(tw.end_minutes)}" if tw else "—"
        vol_str = (
            f"{node.required_volume:+.2f}\u202fm³"
            if node.required_volume is not None else "—"
        )
        service_time = getattr(node, "required_time", None)
        service_str = f"{int(service_time)} min" if service_time else "—"

        label   = _node_label(node, data)
        address = _node_address(node, data)

        # Build vehicle visit section
        visits = node_visit_info.get(node.id, [])
        visit_html = ""
        if visits:
            visit_html = "<hr style='margin:6px 0'><b>Vehicle visits:</b><br>"
            for v in visits:
                time_str = _hhmm(int(v['arrival_time'])) if v['arrival_time'] is not None else "—"
                load_str = f"{v['load']:.2f}\u202fm³" if v['load'] is not None else "—"
                visit_html += (
                    f"<div style='margin:3px 0;padding:3px 6px;background:#f5f5f5;border-left:3px solid {v['color']};border-radius:2px'>"
                    f"<b style='color:{v['color']}'>{v['plate']}</b> ({v['visit_type']})<br>"
                    f"<small>Arrival: {time_str} · Load: {load_str}</small>"
                    f"</div>"
                )

        popup_html = (
            f"<div style='font-size:13px;min-width:220px'>"
            f"<b style='font-size:15px'>{label}</b><br>"
            f"<i style='color:#666'>{address}</i><hr style='margin:4px 0'>"
            f"<b>Type:</b> {node_type}<br>"
            f"<b>Time window:</b> {tw_str}<br>"
            f"<b>Volume Δ:</b> {vol_str}<br>"
            f"<b>Service time:</b> {service_str}<br>"
            f"<b>GPS:</b> {lat:.5f}, {lon:.5f}"
            f"{visit_html}"
            f"</div>"
        )
        markers_js_lines.append(
            f'L.circleMarker([{lat},{lon}],'
            f'{{radius:{radius},color:"{stroke_color}",weight:2,'
            f'fillColor:"{fill_color}",fillOpacity:0.9}})'
            f'.bindPopup({json.dumps(popup_html)}).addTo(map);'
        )

    markers_js = "\n    ".join(markers_js_lines)

    # ── Stats bar ─────────────────────────────────────────────────────────────
    obj_str    = f"{objective_value:.3f}" if objective_value is not None else "—"
    stats_html = (
        f'<div id="stats">'
        f'<b>Status:</b> {solve_status}&emsp;'
        f'<b>Objective:</b> {obj_str}&emsp;'
        f'<b>Active vehicles:</b> {active_vehicle_count} / {len(vehicles)}'
        f'</div>'
    )

    # ── Assemble HTML ─────────────────────────────────────────────────────────
    html = f"""\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>VRPPD Solution</title>
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <script src="https://unpkg.com/leaflet-polylinedecorator@1.6.0/dist/leaflet.polylineDecorator.js"></script>
  <style>
    * {{ margin:0; padding:0; box-sizing:border-box; }}
    body {{ font-family:system-ui,sans-serif; background:#f0f0f0; }}
    #map {{ width:100vw; height:100vh; }}
    #legend {{
      position:absolute; top:80px; right:12px; z-index:1000;
      background:white; border-radius:10px; padding:14px 18px;
      box-shadow:0 3px 12px rgba(0,0,0,.25); max-width:310px;
      max-height:calc(100vh - 120px); overflow-y:auto;
    }}
    #legend h3 {{ font-size:14px; color:#333; margin-bottom:10px;
                  border-bottom:1px solid #eee; padding-bottom:6px; }}
    .legend-item {{ display:flex; align-items:flex-start; margin-bottom:10px;
                    gap:10px; font-size:12px; }}
    .swatch {{ flex-shrink:0; width:22px; height:5px; border-radius:3px; margin-top:6px; }}
    .route-seq {{ color:#888; word-break:break-word; }}
    .node-legend {{ border-top:1px solid #eee; margin-top:8px; padding-top:8px; }}
    .dot {{ display:inline-block; width:12px; height:12px; border-radius:50%;
            margin-right:6px; vertical-align:middle; }}
    #stats {{
      position:absolute; bottom:22px; left:50%; transform:translateX(-50%);
      z-index:1000; background:white; border-radius:8px; padding:8px 20px;
      box-shadow:0 2px 10px rgba(0,0,0,.2); font-size:13px; white-space:nowrap;
    }}
    .route-tooltip {{
      background:rgba(30,30,30,.92); color:white;
      border:none; border-radius:6px; font-size:12px; padding:8px 12px;
      box-shadow:0 3px 10px rgba(0,0,0,.4);
      line-height:1.5;
    }}
    .route-tooltip hr {{ border:none; border-top:1px solid #555; }}
    .leaflet-tooltip-top.route-tooltip::before {{ border-top-color:rgba(30,30,30,.92); }}
  </style>
</head>
<body>
<div id="map"></div>

<div id="legend">
  <h3>Vehicles &amp; Routes</h3>
  {legend_rows_html or '<i style="font-size:12px;color:#999">No active routes found.</i>'}
  <div class="node-legend">
    <h3 style="margin-top:6px">Node types</h3>
    <div style="font-size:12px;line-height:2">
      <span class="dot" style="background:#333;border:2px solid #fff;box-shadow:0 0 0 1px #333"></span>Depot<br>
      <span class="dot" style="background:#1a7abf"></span>Delivery — drop-off before concert<br>
      <span class="dot" style="background:#c0392b"></span>Recovery — pick-up after concert
    </div>
  </div>
</div>

{stats_html}

<script>
  // ── Map init ──────────────────────────────────────────────────────────────
  var map = L.map('map').setView([{center_lat}, {center_lon}], 12);
  L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
  }}).addTo(map);

  // ── Wiggly path generator with Bézier + sinusoidal oscillation ────────────
  // Creates a curved, oscillating path between p1 and p2 for visual separation.
  // style object: offset, curv, freq, amp, phase
  function wavyPath(p1, p2, style, nPts) {{
    var dLat = p2[0] - p1[0];
    var dLon = p2[1] - p1[1];
    var len  = Math.sqrt(dLat * dLat + dLon * dLon);
    if (len < 1e-10) return [p1, p2];

    // Perpendicular unit vector
    var perpLat = -dLon / len;
    var perpLon =  dLat / len;

    // Apply base perpendicular offset to endpoints
    var p1Off = [p1[0] + perpLat * style.offset, p1[1] + perpLon * style.offset];
    var p2Off = [p2[0] + perpLat * style.offset, p2[1] + perpLon * style.offset];

    // Bézier control point at midpoint + curvature
    var midLat = (p1Off[0] + p2Off[0]) / 2 + perpLat * style.curv;
    var midLon = (p1Off[1] + p2Off[1]) / 2 + perpLon * style.curv;

    var pts = [];
    for (var i = 0; i <= nPts; i++) {{
      var t = i / nPts;
      var s = 1 - t;

      // Quadratic Bézier base position
      var baseLat = s*s*p1Off[0] + 2*s*t*midLat + t*t*p2Off[0];
      var baseLon = s*s*p1Off[1] + 2*s*t*midLon + t*t*p2Off[1];

      // Sinusoidal oscillation (tapers at endpoints)
      var envelope = Math.sin(Math.PI * t);  // 0 at ends, 1 at middle
      var wave = style.amp * envelope * Math.sin(style.freq * t * 2 * Math.PI + style.phase);

      pts.push([
        baseLat + perpLat * wave,
        baseLon + perpLon * wave
      ]);
    }}
    return pts;
  }}

  // ── Random style generator ───────────────────────────────────────────────
  function randomEdgeStyle() {{
    return {{
      offset: (Math.random() - 0.5) * 0.002,        // perpendicular shift: ±0.001
      curv:   (Math.random() - 0.5) * 0.04,         // Bézier bulge: ±0.02 (gentler curves)
      freq:   0.5 + Math.random() * 1.5,            // oscillation frequency: 0.5-2 cycles (slower)
      amp:    0.0001 + Math.random() * 0.0004,      // oscillation amplitude: subtle
      phase:  Math.random() * 2 * Math.PI           // random phase offset
    }};
  }}

  // ── Helper to format time ──────────────────────────────────────────────────
  function formatTime(minutes) {{
    if (minutes === null || minutes === undefined) return '—';
    var h = Math.floor(minutes / 60);
    var m = Math.round(minutes % 60);
    return ('0' + h).slice(-2) + 'h' + ('0' + m).slice(-2);
  }}

  // ── Helper to format load ────────────────────────────────────────────────
  function formatLoad(load, capacity) {{
    if (load === null || load === undefined) return '—';
    var pct = capacity > 0 ? Math.round(100 * load / capacity) : 0;
    return load.toFixed(2) + ' m³ (' + pct + '%)';
  }}

  // ── Helper to format load variation ─────────────────────────────────────
  function formatDelta(delta) {{
    if (delta === null || delta === undefined || Math.abs(delta) < 0.001) return '—';
    if (delta > 0) {{
      return '<span style="color:#4CAF50">▲ +' + delta.toFixed(2) + ' m³</span> (pickup)';
    }} else {{
      return '<span style="color:#2196F3">▼ ' + delta.toFixed(2) + ' m³</span> (dropoff)';
    }}
  }}

  // ── Draw routes ───────────────────────────────────────────────────────────
  var vehicleRoutes = {vehicle_routes_json};

  vehicleRoutes.forEach(function(route) {{
    route.segments.forEach(function(seg) {{
      var style = randomEdgeStyle();
      var pts = wavyPath(seg.coords[0], seg.coords[1], style, 64);

      // Build rich tooltip
      var tooltipHtml = '<div style="min-width:260px">' +
        '<b style="font-size:13px;color:' + route.color + '">' + route.plate + '</b>' +
        ' <span style="color:#aaa">Step ' + seg.step + '</span>' +
        '<hr style="margin:4px 0;border-color:#555">' +
        '<b>From:</b> ' + seg.from + '<br>' +
        '<span style="margin-left:12px;color:#aaa">Δ ' + formatDelta(seg.delta_at_departure) + '</span><br>' +
        '<b>To:</b> ' + seg.to + '<br>' +
        '<span style="margin-left:12px;color:#aaa">Δ ' + formatDelta(seg.delta_at_arrival) + '</span>' +
        '<hr style="margin:4px 0;border-color:#555">' +
        '<b>🚚 Transported:</b> ' + formatLoad(seg.transported_load, route.capacity) + '<br>' +
        '<hr style="margin:4px 0;border-color:#555">' +
        '<b>Departure:</b> ' + formatTime(seg.departure_time) + '<br>' +
        '<b>Arrival:</b> ' + formatTime(seg.arrival_time) + '<br>' +
        '<b>Travel:</b> ' + (seg.travel_time_min !== null ? Math.round(seg.travel_time_min) + ' min' : '—') +
        ' · ' + (seg.distance_km !== null ? seg.distance_km.toFixed(1) + ' km' : '—') +
        '</div>';

      var line = L.polyline(pts, {{
        color:   route.color,
        weight:  8,
        opacity: 0.85
      }}).bindTooltip(tooltipHtml, {{sticky: true, className: 'route-tooltip'}})
        .addTo(map);

      // Arrow at midpoint of the arc
      L.polylineDecorator(line, {{
        patterns: [{{
          offset:  '50%',
          repeat:  0,
          symbol:  L.Symbol.arrowHead({{
            pixelSize:   20,
            polygon:     false,
            pathOptions: {{
              stroke:  true,
              color:   route.color,
              weight:  4,
              opacity: 1
            }}
          }})
        }}]
      }}).addTo(map);
    }});
  }});

  // ── Node markers ─────────────────────────────────────────────────────────
  {markers_js}
</script>
</body>
</html>
"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Visualization saved to: {output_path}")
