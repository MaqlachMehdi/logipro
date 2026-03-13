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


def _get_concert_info(node_id: int, data: dict | None) -> dict | None:
    """
    Get concert information for a location.
    Returns dict with concert_start, concert_duration, setup_duration,
    teardown_duration, instruments, or None if not a concert venue.
    """
    if data is None:
        return None
    loc = next((l for l in data["locations"] if l["id"] == node_id), None)
    if loc is None or loc.get("concert_start_min") is None:
        return None

    # Parse instruments list
    instruments_str = loc.get("instruments", "")
    instruments_list = [i.strip() for i in instruments_str.split(",") if i.strip()] if instruments_str else []

    # Count instruments
    instrument_counts = {}
    for instr in instruments_list:
        instrument_counts[instr] = instrument_counts.get(instr, 0) + 1

    return {
        "concert_start": loc["concert_start_min"],
        "concert_duration": loc.get("concert_duration_min", 0),
        "setup_duration": loc.get("setup_duration_min", 0),
        "teardown_duration": loc.get("teardown_duration_min", 0),
        "instruments": instruments_list,
        "instrument_counts": instrument_counts,
        "venue_name": loc.get("name", f"#{node_id}"),
    }


def _build_concerts_data(data: dict | None) -> list[dict]:
    """
    Build a list of all concerts with their timing information.
    """
    if data is None:
        return []

    concerts = []
    for loc in data.get("locations", []):
        if loc.get("concert_start_min") is None or loc["id"] == 0:
            continue

        instruments_str = loc.get("instruments", "")
        instruments_list = [i.strip() for i in instruments_str.split(",") if i.strip()] if instruments_str else []
        instrument_counts = {}
        for instr in instruments_list:
            instrument_counts[instr] = instrument_counts.get(instr, 0) + 1

        concert_start = loc["concert_start_min"]
        setup_duration = loc.get("setup_duration_min", 0)
        concert_duration = loc.get("concert_duration_min", 0)
        teardown_duration = loc.get("teardown_duration_min", 0)

        concerts.append({
            "id": loc["id"],
            "name": loc.get("name", f"#{loc['id']}"),
            "address": loc.get("address", ""),
            "concert_start": concert_start,
            "concert_end": concert_start + concert_duration,
            "concert_duration": concert_duration,
            "setup_duration": setup_duration,
            "teardown_duration": teardown_duration,
            "delivery_deadline": concert_start - setup_duration,
            "recovery_earliest": concert_start + concert_duration,
            "instrument_counts": instrument_counts,
            "total_instruments": len(instruments_list),
            "lat": loc.get("lat"),
            "lon": loc.get("lon"),
        })

    # Sort by concert start time
    concerts.sort(key=lambda c: c["concert_start"])
    return concerts


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

def _build_roadmap_data(result, data: dict | None) -> list[dict]:
    """
    Build roadmap data for each vehicle with detailed stop information.
    """
    problem = result.problem
    loads_at_arrival, times_arrival, time_departure_depot, time_arrival_depot, loads_departure_depot = _get_load_time_data(result)

    roadmaps = []
    for plate, trajectory in result.data.items():
        vehicle = problem.vehicles_dict[plate]
        ordered = _trajectory_ordered_nodes(trajectory)

        stops = []
        total_distance = 0.0
        total_travel_time = 0.0

        for idx, node in enumerate(ordered):
            node_key = node.get_id_for_pulp()

            # Get arrival time
            if isinstance(node, DepositNode):
                if idx == 0:
                    arr_time = time_departure_depot.get(plate)
                    load = loads_departure_depot.get(plate)
                    action = "Departure"
                else:
                    arr_time = time_arrival_depot.get(plate)
                    load = loads_at_arrival.get((node_key, plate))
                    action = "Return"
            else:
                arr_time = times_arrival.get((node_key, plate))
                load = loads_at_arrival.get((node_key, plate))
                if isinstance(node, DeliveryNode):
                    action = "Delivery"
                else:
                    action = "Recovery"

            # Compute distance and travel time from previous node
            dist_from_prev = None
            travel_from_prev = None
            if idx > 0:
                prev_node = ordered[idx - 1]
                dist_from_prev = problem.oriented_edges.distances_km.get((prev_node.id, node.id))
                travel_from_prev = problem.oriented_edges.travel_times_min.get((prev_node.id, node.id))
                if dist_from_prev:
                    total_distance += dist_from_prev
                if travel_from_prev:
                    total_travel_time += travel_from_prev

            tw = node.time_window
            concert_info = _get_concert_info(node.id, data) if not isinstance(node, DepositNode) else None
            stops.append({
                "step": idx + 1,
                "label": _node_label(node, data),
                "address": _node_address(node, data),
                "action": action,
                "arrival_time": arr_time,
                "time_window_start": tw.start_minutes if tw else None,
                "time_window_end": tw.end_minutes if tw else None,
                "volume_delta": -(node.required_volume or 0.0) if not isinstance(node, DepositNode) else 0.0,
                "load_after": load,
                "service_time": getattr(node, "required_time", None),
                "distance_from_prev": dist_from_prev,
                "travel_time_from_prev": travel_from_prev,
                "gps": _node_latlng(node),
                "concert": concert_info,
            })

        roadmaps.append({
            "plate": plate,
            "capacity": vehicle.max_volume,
            "stops": stops,
            "total_distance": total_distance,
            "total_travel_time": total_travel_time,
            "stop_count": len(ordered) - 2,  # Exclude depot departure/return
        })

    return roadmaps


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

    # ── Roadmap data for printable sections ───────────────────────────────────
    roadmaps = _build_roadmap_data(result, data)
    roadmaps_json = json.dumps(roadmaps, separators=(",", ":"))

    # ── Concerts data ─────────────────────────────────────────────────────────
    concerts = _build_concerts_data(data)
    concerts_json = json.dumps(concerts, separators=(",", ":"))

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

    # ── Markers data for JS ───────────────────────────────────────────────────
    markers_data: list[dict] = []
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

        # Build concert info section
        concert_html = ""
        concert_info = _get_concert_info(node.id, data) if not isinstance(node, DepositNode) else None
        if concert_info:
            concert_start = _hhmm(concert_info["concert_start"])
            concert_end = _hhmm(concert_info["concert_start"] + concert_info["concert_duration"])
            setup_dur = concert_info["setup_duration"]
            teardown_dur = concert_info["teardown_duration"]
            instr_counts = concert_info["instrument_counts"]

            # Format instruments as compact list
            instr_html = ""
            if instr_counts:
                instr_items = [f"{count}x {name}" for name, count in sorted(instr_counts.items())]
                instr_html = f"<br><small style='color:#666'>{', '.join(instr_items)}</small>"

            concert_html = (
                f"<hr style='margin:6px 0'>"
                f"<div style='background:#fff3e0;padding:8px;border-radius:4px;margin:4px 0'>"
                f"<b style='color:#e65100'>Concert</b><br>"
                f"<b>Time:</b> {concert_start} – {concert_end}<br>"
                f"<b>Setup:</b> {setup_dur} min · <b>Teardown:</b> {teardown_dur} min"
                f"{instr_html}"
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
            f"{concert_html}"
            f"{visit_html}"
            f"</div>"
        )

        markers_data.append({
            "lat": lat,
            "lon": lon,
            "radius": radius,
            "fillColor": fill_color,
            "strokeColor": stroke_color,
            "nodeId": node.id,
            "popupHtml": popup_html,
        })

    markers_json = json.dumps(markers_data, separators=(",", ":"))

    # ── Summary stats ─────────────────────────────────────────────────────────
    obj_str = f"{objective_value:.3f}" if objective_value is not None else "—"
    total_stops = sum(r["stop_count"] for r in roadmaps)
    total_distance = sum(r["total_distance"] for r in roadmaps)
    total_time = sum(r["total_travel_time"] for r in roadmaps)

    # ── Vehicle tabs HTML ─────────────────────────────────────────────────────
    vehicle_tabs_html = ""
    for i, route in enumerate(vehicle_routes):
        plate = route["plate"]
        color = route["color"]
        vehicle_tabs_html += f'<button class="tab-btn vehicle-tab" data-vehicle="{i}" style="border-left:4px solid {color}">{plate}</button>\n'

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
    body {{ font-family:system-ui,sans-serif; background:#f5f5f5; }}

    /* Navigation */
    .nav-bar {{
      position:fixed; top:0; left:0; right:0; z-index:2000;
      background:linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
      padding:0 20px; height:56px;
      display:flex; align-items:center; gap:20px;
      box-shadow:0 2px 10px rgba(0,0,0,.3);
    }}
    .nav-title {{ color:white; font-size:18px; font-weight:600; margin-right:30px; }}
    .tab-btn {{
      background:transparent; border:none; color:rgba(255,255,255,.7);
      padding:16px 20px; font-size:14px; cursor:pointer; transition:all .2s;
      border-bottom:3px solid transparent;
    }}
    .tab-btn:hover {{ color:white; background:rgba(255,255,255,.1); }}
    .tab-btn.active {{ color:white; border-bottom-color:#4CAF50; background:rgba(255,255,255,.05); }}
    .vehicle-tab {{ padding:16px 16px; font-weight:500; }}

    /* Page containers */
    .page {{ display:none; padding-top:56px; min-height:100vh; }}
    .page.active {{ display:block; }}
    .vehicle-page.active {{ display:flex; }}

    /* Global Summary Page */
    .summary-page {{ padding:80px 40px 40px; max-width:1400px; margin:0 auto; }}
    .summary-header {{ margin-bottom:30px; }}
    .summary-header h1 {{ font-size:28px; color:#1a1a2e; margin-bottom:8px; }}
    .summary-header p {{ color:#666; font-size:14px; }}

    .stats-grid {{
      display:grid; grid-template-columns:repeat(auto-fit, minmax(200px, 1fr));
      gap:20px; margin-bottom:40px;
    }}
    .stat-card {{
      background:white; border-radius:12px; padding:24px;
      box-shadow:0 2px 8px rgba(0,0,0,.08);
    }}
    .stat-card .label {{ color:#888; font-size:12px; text-transform:uppercase; letter-spacing:.5px; }}
    .stat-card .value {{ font-size:32px; font-weight:700; color:#1a1a2e; margin-top:8px; }}
    .stat-card .unit {{ font-size:14px; color:#666; font-weight:400; }}
    .stat-card.status-optimal .value {{ color:#4CAF50; }}

    .vehicles-overview {{
      background:white; border-radius:12px; padding:24px;
      box-shadow:0 2px 8px rgba(0,0,0,.08);
    }}
    .vehicles-overview h2 {{ font-size:18px; color:#1a1a2e; margin-bottom:20px; }}
    .vehicle-row {{
      display:flex; align-items:center; gap:16px; padding:16px;
      border-bottom:1px solid #eee; cursor:pointer; transition:background .2s;
    }}
    .vehicle-row:hover {{ background:#f8f9fa; }}
    .vehicle-row:last-child {{ border-bottom:none; }}
    .vehicle-color {{ width:8px; height:40px; border-radius:4px; }}
    .vehicle-info {{ flex:1; }}
    .vehicle-info .plate {{ font-weight:600; font-size:16px; color:#1a1a2e; }}
    .vehicle-info .details {{ color:#888; font-size:13px; margin-top:4px; }}
    .vehicle-stats {{ display:flex; gap:24px; font-size:13px; color:#666; }}
    .vehicle-stats span {{ white-space:nowrap; }}

    /* Vehicle Page */
    .vehicle-page {{ display:flex; flex-direction:column; height:100vh; padding-top:56px; }}
    .vehicle-content {{ display:flex; flex:1; overflow:hidden; height:calc(100vh - 56px); }}

    .map-section {{ flex:1; position:relative; min-height:400px; }}
    .map-container {{ width:100%; height:100%; min-height:400px; }}

    .roadmap-section {{
      width:450px; background:white; overflow-y:auto;
      border-left:1px solid #e0e0e0; padding:24px;
    }}
    .roadmap-header {{
      display:flex; justify-content:space-between; align-items:center;
      margin-bottom:20px; padding-bottom:16px; border-bottom:1px solid #eee;
    }}
    .roadmap-header h2 {{ font-size:18px; color:#1a1a2e; }}
    .print-btn {{
      background:#1a1a2e; color:white; border:none; padding:8px 16px;
      border-radius:6px; font-size:13px; cursor:pointer; transition:background .2s;
    }}
    .print-btn:hover {{ background:#2d2d4a; }}

    .roadmap-stats {{
      display:grid; grid-template-columns:repeat(3, 1fr); gap:12px;
      margin-bottom:24px;
    }}
    .roadmap-stat {{
      background:#f8f9fa; border-radius:8px; padding:12px; text-align:center;
    }}
    .roadmap-stat .val {{ font-size:18px; font-weight:600; color:#1a1a2e; }}
    .roadmap-stat .lbl {{ font-size:11px; color:#888; text-transform:uppercase; margin-top:4px; }}

    .stop-list {{ }}
    .stop-item {{
      display:flex; gap:16px; padding:16px 0;
      border-bottom:1px solid #f0f0f0;
    }}
    .stop-item:last-child {{ border-bottom:none; }}
    .stop-number {{
      width:32px; height:32px; border-radius:50%; background:#1a1a2e;
      color:white; display:flex; align-items:center; justify-content:center;
      font-weight:600; font-size:14px; flex-shrink:0;
    }}
    .stop-number.delivery {{ background:#1a7abf; }}
    .stop-number.recovery {{ background:#c0392b; }}
    .stop-number.depot {{ background:#333; }}
    .stop-details {{ flex:1; }}
    .stop-name {{ font-weight:600; font-size:14px; color:#1a1a2e; }}
    .stop-address {{ color:#888; font-size:12px; margin-top:2px; }}
    .stop-meta {{
      display:flex; flex-wrap:wrap; gap:8px 16px; margin-top:8px;
      font-size:12px; color:#666;
    }}
    .stop-meta .tag {{
      background:#f0f0f0; padding:2px 8px; border-radius:4px;
    }}
    .stop-meta .time {{ color:#4CAF50; font-weight:500; }}
    .stop-meta .window {{ color:#888; }}
    .stop-meta .load {{ color:#1a7abf; }}
    .stop-meta .delta-positive {{ color:#4CAF50; }}
    .stop-meta .delta-negative {{ color:#c0392b; }}

    .travel-info {{
      display:flex; align-items:center; gap:8px; padding:8px 0 8px 40px;
      color:#aaa; font-size:11px;
    }}
    .travel-info::before {{
      content:''; width:2px; height:24px; background:#e0e0e0;
      position:absolute; margin-left:-25px;
    }}

    /* Print styles */
    @media print {{
      .nav-bar, .print-btn, .map-section {{ display:none !important; }}
      .page {{ display:block !important; page-break-after:always; padding:20px !important; }}
      .vehicle-page {{ height:auto; }}
      .vehicle-content {{ display:block; }}
      .roadmap-section {{ width:100%; border:none; padding:0; }}
      .summary-page {{ padding:20px; }}
      body {{ background:white; }}
    }}

    /* Route tooltip (for maps) */
    .route-tooltip {{
      background:rgba(30,30,30,.92); color:white;
      border:none; border-radius:6px; font-size:12px; padding:8px 12px;
      box-shadow:0 3px 10px rgba(0,0,0,.4); line-height:1.5;
    }}
    .route-tooltip hr {{ border:none; border-top:1px solid #555; }}
    .leaflet-tooltip-top.route-tooltip::before {{ border-top-color:rgba(30,30,30,.92); }}

    /* Concert Timeline */
    .concert-item {{
      display:flex; gap:16px; padding:16px;
      border-bottom:1px solid #eee; transition:background .2s;
    }}
    .concert-item:hover {{ background:#f8f9fa; }}
    .concert-item:last-child {{ border-bottom:none; }}
    .concert-time {{
      width:80px; flex-shrink:0; text-align:center;
      background:linear-gradient(135deg, #ff6b35 0%, #f7931e 100%);
      color:white; border-radius:8px; padding:12px 8px;
    }}
    .concert-time .start {{ font-size:18px; font-weight:700; }}
    .concert-time .end {{ font-size:12px; opacity:.8; margin-top:2px; }}
    .concert-details {{ flex:1; }}
    .concert-name {{ font-weight:600; font-size:16px; color:#1a1a2e; }}
    .concert-address {{ color:#888; font-size:12px; margin-top:2px; }}
    .concert-meta {{
      display:flex; flex-wrap:wrap; gap:8px 16px; margin-top:10px;
      font-size:12px;
    }}
    .concert-meta .badge {{
      background:#f0f0f0; padding:4px 10px; border-radius:12px; color:#666;
    }}
    .concert-meta .badge.setup {{ background:#e3f2fd; color:#1565c0; }}
    .concert-meta .badge.teardown {{ background:#fce4ec; color:#c62828; }}
    .concert-meta .badge.duration {{ background:#e8f5e9; color:#2e7d32; }}
    .concert-instruments {{
      margin-top:10px; padding:10px; background:#fafafa; border-radius:6px;
    }}
    .concert-instruments .title {{ font-size:11px; color:#888; text-transform:uppercase; margin-bottom:6px; }}
    .instrument-tags {{ display:flex; flex-wrap:wrap; gap:6px; }}
    .instrument-tag {{
      background:#e0e0e0; padding:3px 8px; border-radius:4px;
      font-size:11px; color:#555;
    }}

    /* Concert info in roadmap */
    .stop-concert {{
      background:#fff3e0; border-left:3px solid #ff6b35;
      padding:8px 12px; margin-top:8px; border-radius:0 6px 6px 0;
      font-size:12px;
    }}
    .stop-concert .concert-badge {{
      display:inline-block; background:#ff6b35; color:white;
      padding:2px 8px; border-radius:4px; font-size:10px;
      text-transform:uppercase; font-weight:600; margin-bottom:6px;
    }}
  </style>
</head>
<body>

<!-- Navigation Bar -->
<nav class="nav-bar">
  <span class="nav-title">VRPPD Solution</span>
  <button class="tab-btn active" data-page="summary">Summary</button>
  {vehicle_tabs_html}
</nav>

<!-- Page 1: Global Summary -->
<div id="page-summary" class="page summary-page active">
  <div class="summary-header">
    <h1>Solution Overview</h1>
    <p>Vehicle Routing Problem with Pickup and Delivery</p>
  </div>

  <div class="stats-grid">
    <div class="stat-card {'status-optimal' if solve_status == 'Optimal' else ''}">
      <div class="label">Status</div>
      <div class="value">{solve_status}</div>
    </div>
    <div class="stat-card">
      <div class="label">Objective</div>
      <div class="value">{obj_str}</div>
    </div>
    <div class="stat-card">
      <div class="label">Active Vehicles</div>
      <div class="value">{active_vehicle_count} <span class="unit">/ {len(vehicles)}</span></div>
    </div>
    <div class="stat-card">
      <div class="label">Total Stops</div>
      <div class="value">{total_stops}</div>
    </div>
    <div class="stat-card">
      <div class="label">Total Distance</div>
      <div class="value">{total_distance:.1f} <span class="unit">km</span></div>
    </div>
    <div class="stat-card">
      <div class="label">Total Travel Time</div>
      <div class="value">{total_time:.0f} <span class="unit">min</span></div>
    </div>
    <div class="stat-card">
      <div class="label">Concerts</div>
      <div class="value">{len(concerts)}</div>
    </div>
  </div>

  <div class="vehicles-overview">
    <h2>Vehicles</h2>
    <div id="vehicle-list"></div>
  </div>

  <div class="concerts-section" style="margin-top:30px;">
    <div class="vehicles-overview">
      <h2>Concerts Timeline</h2>
      <div id="concerts-timeline"></div>
    </div>
  </div>
</div>

<!-- Vehicle Pages (generated by JS) -->
<div id="vehicle-pages"></div>

<script>
  // ── Data ──────────────────────────────────────────────────────────────────
  var vehicleRoutes = {vehicle_routes_json};
  var roadmaps = {roadmaps_json};
  var markersData = {markers_json};
  var concerts = {concerts_json};
  var centerLat = {center_lat};
  var centerLon = {center_lon};

  // ── Maps storage ──────────────────────────────────────────────────────────
  var vehicleMaps = {{}};

  // ── Helper functions ──────────────────────────────────────────────────────
  function formatTime(minutes) {{
    if (minutes === null || minutes === undefined) return '—';
    var h = Math.floor(minutes / 60);
    var m = Math.round(minutes % 60);
    return ('0' + h).slice(-2) + 'h' + ('0' + m).slice(-2);
  }}

  function formatLoad(load, capacity) {{
    if (load === null || load === undefined) return '—';
    var pct = capacity > 0 ? Math.round(100 * load / capacity) : 0;
    return load.toFixed(2) + ' m³ (' + pct + '%)';
  }}

  function formatDelta(delta) {{
    if (delta === null || delta === undefined || Math.abs(delta) < 0.001) return '—';
    if (delta > 0) {{
      return '<span style="color:#4CAF50">+' + delta.toFixed(2) + ' m³</span> (pickup)';
    }} else {{
      return '<span style="color:#2196F3">' + delta.toFixed(2) + ' m³</span> (dropoff)';
    }}
  }}

  function wavyPath(p1, p2, style, nPts) {{
    var dLat = p2[0] - p1[0];
    var dLon = p2[1] - p1[1];
    var len  = Math.sqrt(dLat * dLat + dLon * dLon);
    if (len < 1e-10) return [p1, p2];
    var perpLat = -dLon / len;
    var perpLon =  dLat / len;
    var p1Off = [p1[0] + perpLat * style.offset, p1[1] + perpLon * style.offset];
    var p2Off = [p2[0] + perpLat * style.offset, p2[1] + perpLon * style.offset];
    var midLat = (p1Off[0] + p2Off[0]) / 2 + perpLat * style.curv;
    var midLon = (p1Off[1] + p2Off[1]) / 2 + perpLon * style.curv;
    var pts = [];
    for (var i = 0; i <= nPts; i++) {{
      var t = i / nPts;
      var s = 1 - t;
      var baseLat = s*s*p1Off[0] + 2*s*t*midLat + t*t*p2Off[0];
      var baseLon = s*s*p1Off[1] + 2*s*t*midLon + t*t*p2Off[1];
      var envelope = Math.sin(Math.PI * t);
      var wave = style.amp * envelope * Math.sin(style.freq * t * 2 * Math.PI + style.phase);
      pts.push([baseLat + perpLat * wave, baseLon + perpLon * wave]);
    }}
    return pts;
  }}

  function randomEdgeStyle() {{
    return {{
      offset: (Math.random() - 0.5) * 0.002,
      curv:   (Math.random() - 0.5) * 0.04,
      freq:   0.5 + Math.random() * 1.5,
      amp:    0.0001 + Math.random() * 0.0004,
      phase:  Math.random() * 2 * Math.PI
    }};
  }}

  // ── Generate concerts timeline on summary page ─────────────────────────────
  function generateConcertsTimeline() {{
    if (!concerts || concerts.length === 0) {{
      document.getElementById('concerts-timeline').innerHTML =
        '<p style="color:#888;font-size:13px;padding:16px;">No concerts scheduled.</p>';
      return;
    }}

    var html = '';
    concerts.forEach(function(concert) {{
      var startTime = formatTime(concert.concert_start);
      var endTime = formatTime(concert.concert_end);

      // Build instruments tags
      var instrHtml = '';
      if (concert.instrument_counts && Object.keys(concert.instrument_counts).length > 0) {{
        var tags = Object.entries(concert.instrument_counts)
          .sort(function(a, b) {{ return b[1] - a[1]; }})
          .map(function(item) {{
            return '<span class="instrument-tag">' + item[1] + 'x ' + item[0] + '</span>';
          }}).join('');
        instrHtml = '<div class="concert-instruments">' +
          '<div class="title">Instruments (' + concert.total_instruments + ' items)</div>' +
          '<div class="instrument-tags">' + tags + '</div>' +
        '</div>';
      }}

      html += '<div class="concert-item">' +
        '<div class="concert-time">' +
          '<div class="start">' + startTime + '</div>' +
          '<div class="end">' + endTime + '</div>' +
        '</div>' +
        '<div class="concert-details">' +
          '<div class="concert-name">' + concert.name + '</div>' +
          '<div class="concert-address">' + concert.address + '</div>' +
          '<div class="concert-meta">' +
            '<span class="badge duration">' + concert.concert_duration + ' min concert</span>' +
            '<span class="badge setup">' + concert.setup_duration + ' min setup</span>' +
            '<span class="badge teardown">' + concert.teardown_duration + ' min teardown</span>' +
          '</div>' +
          instrHtml +
        '</div>' +
      '</div>';
    }});

    document.getElementById('concerts-timeline').innerHTML = html;
  }}

  // ── Generate vehicle list on summary page ─────────────────────────────────
  function generateVehicleList() {{
    var html = '';
    vehicleRoutes.forEach(function(route, idx) {{
      var roadmap = roadmaps.find(function(r) {{ return r.plate === route.plate; }});
      html += '<div class="vehicle-row" data-vehicle="' + idx + '">' +
        '<div class="vehicle-color" style="background:' + route.color + '"></div>' +
        '<div class="vehicle-info">' +
          '<div class="plate">' + route.plate + '</div>' +
          '<div class="details">Capacity: ' + route.capacity + ' m³</div>' +
        '</div>' +
        '<div class="vehicle-stats">' +
          '<span>' + (roadmap ? roadmap.stop_count : 0) + ' stops</span>' +
          '<span>' + (roadmap ? roadmap.total_distance.toFixed(1) : 0) + ' km</span>' +
          '<span>' + (roadmap ? Math.round(roadmap.total_travel_time) : 0) + ' min</span>' +
        '</div>' +
      '</div>';
    }});
    document.getElementById('vehicle-list').innerHTML = html;

    // Click handlers
    document.querySelectorAll('.vehicle-row').forEach(function(row) {{
      row.addEventListener('click', function() {{
        var idx = parseInt(this.getAttribute('data-vehicle'));
        showVehiclePage(idx);
      }});
    }});
  }}

  // ── Generate vehicle pages ────────────────────────────────────────────────
  function generateVehiclePages() {{
    var container = document.getElementById('vehicle-pages');
    var html = '';

    vehicleRoutes.forEach(function(route, idx) {{
      var roadmap = roadmaps.find(function(r) {{ return r.plate === route.plate; }});

      html += '<div id="page-vehicle-' + idx + '" class="page vehicle-page">' +
        '<div class="vehicle-content">' +
          '<div class="map-section">' +
            '<div id="map-' + idx + '" class="map-container"></div>' +
          '</div>' +
          '<div class="roadmap-section">' +
            '<div class="roadmap-header">' +
              '<h2>' + route.plate + ' — Roadmap</h2>' +
              '<button class="print-btn" onclick="window.print()">Print</button>' +
            '</div>' +
            '<div class="roadmap-stats">' +
              '<div class="roadmap-stat"><div class="val">' + (roadmap ? roadmap.stop_count : 0) + '</div><div class="lbl">Stops</div></div>' +
              '<div class="roadmap-stat"><div class="val">' + (roadmap ? roadmap.total_distance.toFixed(1) : 0) + '</div><div class="lbl">km</div></div>' +
              '<div class="roadmap-stat"><div class="val">' + (roadmap ? Math.round(roadmap.total_travel_time) : 0) + '</div><div class="lbl">min</div></div>' +
            '</div>' +
            '<div class="stop-list" id="stops-' + idx + '"></div>' +
          '</div>' +
        '</div>' +
      '</div>';
    }});

    container.innerHTML = html;

    // Generate stop lists
    vehicleRoutes.forEach(function(route, idx) {{
      var roadmap = roadmaps.find(function(r) {{ return r.plate === route.plate; }});
      if (!roadmap) return;

      var stopsHtml = '';
      roadmap.stops.forEach(function(stop, stopIdx) {{
        var numClass = 'depot';
        if (stop.action === 'Delivery') numClass = 'delivery';
        else if (stop.action === 'Recovery') numClass = 'recovery';

        var twStr = (stop.time_window_start !== null && stop.time_window_end !== null)
          ? formatTime(stop.time_window_start) + ' – ' + formatTime(stop.time_window_end)
          : '—';

        var deltaHtml = '';
        if (stop.volume_delta > 0.001) {{
          deltaHtml = '<span class="delta-positive">+' + stop.volume_delta.toFixed(2) + ' m³</span>';
        }} else if (stop.volume_delta < -0.001) {{
          deltaHtml = '<span class="delta-negative">' + stop.volume_delta.toFixed(2) + ' m³</span>';
        }}

        // Concert info for this stop
        var concertHtml = '';
        if (stop.concert) {{
          var c = stop.concert;
          var concertStart = formatTime(c.concert_start);
          var concertEnd = formatTime(c.concert_start + c.concert_duration);

          var instrSummary = '';
          if (c.instrument_counts && Object.keys(c.instrument_counts).length > 0) {{
            var instrList = Object.entries(c.instrument_counts)
              .sort(function(a, b) {{ return b[1] - a[1]; }})
              .slice(0, 4)
              .map(function(item) {{ return item[1] + 'x ' + item[0]; }})
              .join(', ');
            var total = Object.values(c.instrument_counts).reduce(function(a, b) {{ return a + b; }}, 0);
            instrSummary = '<br><small style="color:#666">' + total + ' instruments: ' + instrList +
              (Object.keys(c.instrument_counts).length > 4 ? '...' : '') + '</small>';
          }}

          concertHtml = '<div class="stop-concert">' +
            '<span class="concert-badge">Concert</span><br>' +
            '<b>' + concertStart + ' – ' + concertEnd + '</b> (' + c.concert_duration + ' min)<br>' +
            '<small>Setup: ' + c.setup_duration + ' min · Teardown: ' + c.teardown_duration + ' min</small>' +
            instrSummary +
          '</div>';
        }}

        stopsHtml += '<div class="stop-item">' +
          '<div class="stop-number ' + numClass + '">' + stop.step + '</div>' +
          '<div class="stop-details">' +
            '<div class="stop-name">' + stop.label + '</div>' +
            '<div class="stop-address">' + (stop.address || '') + '</div>' +
            '<div class="stop-meta">' +
              '<span class="tag">' + stop.action + '</span>' +
              '<span class="time">' + formatTime(stop.arrival_time) + '</span>' +
              '<span class="window">Window: ' + twStr + '</span>' +
              (deltaHtml ? deltaHtml : '') +
              '<span class="load">Load: ' + formatLoad(stop.load_after, roadmap.capacity) + '</span>' +
            '</div>' +
            concertHtml +
          '</div>' +
        '</div>';

        // Travel info between stops
        if (stopIdx < roadmap.stops.length - 1) {{
          var nextStop = roadmap.stops[stopIdx + 1];
          if (nextStop.distance_from_prev !== null) {{
            stopsHtml += '<div class="travel-info">' +
              nextStop.distance_from_prev.toFixed(1) + ' km · ' +
              Math.round(nextStop.travel_time_from_prev || 0) + ' min' +
            '</div>';
          }}
        }}
      }});

      document.getElementById('stops-' + idx).innerHTML = stopsHtml;
    }});
  }}

  // ── Initialize map for a vehicle ──────────────────────────────────────────
  function initVehicleMap(idx, callback) {{
    if (vehicleMaps[idx]) {{
      // Already initialized, just invalidate size
      vehicleMaps[idx].invalidateSize();
      if (callback) callback();
      return;
    }}

    var mapContainer = document.getElementById('map-' + idx);
    if (!mapContainer) {{
      console.error('Map container not found for vehicle ' + idx);
      return;
    }}

    var route = vehicleRoutes[idx];
    if (!route) {{
      console.error('Route not found for vehicle ' + idx);
      return;
    }}

    var map = L.map('map-' + idx, {{
      center: [centerLat, centerLon],
      zoom: 12
    }});

    L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
      attribution: '&copy; OpenStreetMap'
    }}).addTo(map);

    // Draw route segments
    var bounds = [];
    route.segments.forEach(function(seg) {{
      var style = randomEdgeStyle();
      var pts = wavyPath(seg.coords[0], seg.coords[1], style, 64);
      bounds.push(seg.coords[0]);
      bounds.push(seg.coords[1]);

      var tooltipHtml = '<div style="min-width:260px">' +
        '<b style="font-size:13px;color:' + route.color + '">' + route.plate + '</b>' +
        ' <span style="color:#aaa">Step ' + seg.step + '</span>' +
        '<hr style="margin:4px 0;border-color:#555">' +
        '<b>From:</b> ' + seg.from + '<br>' +
        '<b>To:</b> ' + seg.to +
        '<hr style="margin:4px 0;border-color:#555">' +
        '<b>Transported:</b> ' + formatLoad(seg.transported_load, route.capacity) + '<br>' +
        '<b>Departure:</b> ' + formatTime(seg.departure_time) + '<br>' +
        '<b>Arrival:</b> ' + formatTime(seg.arrival_time) + '<br>' +
        '<b>Travel:</b> ' + (seg.travel_time_min !== null ? Math.round(seg.travel_time_min) + ' min' : '—') +
        ' · ' + (seg.distance_km !== null ? seg.distance_km.toFixed(1) + ' km' : '—') +
        '</div>';

      var line = L.polyline(pts, {{
        color: route.color, weight: 8, opacity: 0.85
      }}).bindTooltip(tooltipHtml, {{sticky: true, className: 'route-tooltip'}}).addTo(map);

      L.polylineDecorator(line, {{
        patterns: [{{
          offset: '50%', repeat: 0,
          symbol: L.Symbol.arrowHead({{
            pixelSize: 20, polygon: false,
            pathOptions: {{ stroke: true, color: route.color, weight: 4, opacity: 1 }}
          }})
        }}]
      }}).addTo(map);
    }});

    // Add markers for nodes on this route
    var routeNodeIds = new Set();
    var roadmap = roadmaps.find(function(r) {{ return r.plate === route.plate; }});
    if (roadmap) {{
      roadmap.stops.forEach(function(stop) {{
        if (stop.gps) {{
          routeNodeIds.add(stop.gps[0].toFixed(5) + ',' + stop.gps[1].toFixed(5));
        }}
      }});
    }}

    markersData.forEach(function(m) {{
      var key = m.lat.toFixed(5) + ',' + m.lon.toFixed(5);
      if (routeNodeIds.has(key) || m.nodeId === 0) {{ // Include depot always
        L.circleMarker([m.lat, m.lon], {{
          radius: m.radius, color: m.strokeColor, weight: 2,
          fillColor: m.fillColor, fillOpacity: 0.9
        }}).bindPopup(m.popupHtml).addTo(map);
      }}
    }});

    // Store map reference
    vehicleMaps[idx] = map;

    // Invalidate size and fit bounds after a short delay
    setTimeout(function() {{
      map.invalidateSize();
      if (bounds.length > 0) {{
        map.fitBounds(bounds, {{ padding: [50, 50] }});
      }}
      if (callback) callback();
    }}, 50);
  }}

  // ── Page navigation ───────────────────────────────────────────────────────
  function showPage(pageId) {{
    document.querySelectorAll('.page').forEach(function(p) {{ p.classList.remove('active'); }});
    document.querySelectorAll('.tab-btn').forEach(function(b) {{ b.classList.remove('active'); }});
    document.getElementById('page-' + pageId).classList.add('active');
    document.querySelector('[data-page="' + pageId + '"]').classList.add('active');
  }}

  function showVehiclePage(idx) {{
    document.querySelectorAll('.page').forEach(function(p) {{ p.classList.remove('active'); }});
    document.querySelectorAll('.tab-btn').forEach(function(b) {{ b.classList.remove('active'); }});
    document.getElementById('page-vehicle-' + idx).classList.add('active');
    var vehicleTab = document.querySelector('[data-vehicle="' + idx + '"]');
    if (vehicleTab) vehicleTab.classList.add('active');

    // Initialize map after page is visible using requestAnimationFrame for better timing
    requestAnimationFrame(function() {{
      setTimeout(function() {{
        initVehicleMap(idx);
      }}, 150);
    }});
  }}

  // ── Event listeners ───────────────────────────────────────────────────────
  document.querySelectorAll('.tab-btn[data-page]').forEach(function(btn) {{
    btn.addEventListener('click', function() {{
      showPage(this.getAttribute('data-page'));
    }});
  }});

  document.querySelectorAll('.tab-btn[data-vehicle]').forEach(function(btn) {{
    btn.addEventListener('click', function() {{
      showVehiclePage(parseInt(this.getAttribute('data-vehicle')));
    }});
  }});

  // ── Initialize ────────────────────────────────────────────────────────────
  generateVehicleList();
  generateConcertsTimeline();
  generateVehiclePages();
</script>
</body>
</html>
"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Visualization saved to: {output_path}")


def render_html_terminal(
    result,
    data:            dict | None,
    output_path:     str,
    solve_status:    str        = "",
    objective_value: float | None = None,
) -> None:
    """
    Generate a terminal-style HTML file visualizing the VRPPD solution.
    Retro CRT aesthetic with monospace fonts and green-on-black styling.
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

    # Build data
    vehicle_routes = _build_vehicle_routes(result, color_map, data)
    roadmaps = _build_roadmap_data(result, data)
    concerts = _build_concerts_data(data)

    vehicle_routes_json = json.dumps(vehicle_routes, separators=(",", ":"))
    roadmaps_json = json.dumps(roadmaps, separators=(",", ":"))
    concerts_json = json.dumps(concerts, separators=(",", ":"))

    # Stats
    obj_str = f"{objective_value:.3f}" if objective_value is not None else "N/A"
    active_vehicle_count = len(vehicle_routes)
    total_stops = sum(r["stop_count"] for r in roadmaps)
    total_distance = sum(r["total_distance"] for r in roadmaps)
    total_time = sum(r["total_travel_time"] for r in roadmaps)

    # Vehicle nav items
    vehicle_nav_html = ""
    for i, route in enumerate(vehicle_routes):
        plate = route["plate"]
        vehicle_nav_html += f'<span class="nav-item" data-vehicle="{i}">[{i+1}] {plate}</span>\n'

    html = f"""\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>VRPPD Solution // Terminal</title>
  <style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&family=VT323&display=swap');

    :root {{
      --bg: #0a0a0a;
      --bg-secondary: #111;
      --green: #00ff41;
      --green-dim: #00aa2a;
      --amber: #ffb000;
      --cyan: #00ffff;
      --red: #ff3333;
      --magenta: #ff00ff;
      --white: #e0e0e0;
      --gray: #555;
      --border: #333;
    }}

    * {{ margin:0; padding:0; box-sizing:border-box; }}

    body {{
      font-family: 'JetBrains Mono', 'Courier New', monospace;
      background: var(--bg);
      color: var(--green);
      font-size: 13px;
      line-height: 1.6;
      min-height: 100vh;
    }}

    /* CRT Scanline effect */
    body::before {{
      content: "";
      position: fixed;
      top: 0; left: 0; right: 0; bottom: 0;
      background: repeating-linear-gradient(
        0deg,
        rgba(0, 0, 0, 0.15),
        rgba(0, 0, 0, 0.15) 1px,
        transparent 1px,
        transparent 2px
      );
      pointer-events: none;
      z-index: 10000;
    }}

    /* Glow effect */
    body::after {{
      content: "";
      position: fixed;
      top: 0; left: 0; right: 0; bottom: 0;
      background: radial-gradient(ellipse at center, transparent 0%, rgba(0,0,0,0.3) 100%);
      pointer-events: none;
      z-index: 9999;
    }}

    .terminal {{
      max-width: 1200px;
      margin: 0 auto;
      padding: 20px;
    }}

    /* Header */
    .header {{
      border: 1px solid var(--green);
      padding: 20px;
      margin-bottom: 20px;
      position: relative;
    }}
    .header::before {{
      content: "╔══════════════════════════════════════════════════════════════════╗";
      position: absolute;
      top: -1px; left: -1px;
      color: var(--green-dim);
      font-size: 10px;
      letter-spacing: -1px;
    }}

    .logo {{
      font-family: 'VT323', monospace;
      font-size: 28px;
      color: var(--amber);
      text-shadow: 0 0 10px var(--amber);
      margin-bottom: 10px;
    }}

    .logo-sub {{
      color: var(--gray);
      font-size: 11px;
    }}

    /* Navigation */
    .nav {{
      display: flex;
      gap: 20px;
      padding: 12px 0;
      border-bottom: 1px dashed var(--border);
      margin-bottom: 20px;
      flex-wrap: wrap;
    }}
    .nav-item {{
      color: var(--cyan);
      cursor: pointer;
      padding: 4px 8px;
      transition: all 0.1s;
    }}
    .nav-item:hover {{
      background: var(--cyan);
      color: var(--bg);
    }}
    .nav-item.active {{
      background: var(--green);
      color: var(--bg);
    }}

    /* Pages */
    .page {{ display: none; }}
    .page.active {{ display: block; }}

    /* Stats Grid */
    .stats-box {{
      border: 1px solid var(--border);
      margin-bottom: 20px;
    }}
    .stats-title {{
      background: var(--border);
      padding: 8px 12px;
      color: var(--amber);
      font-weight: bold;
    }}
    .stats-content {{
      padding: 16px;
    }}
    .stats-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 16px;
    }}
    .stat {{
      border-left: 2px solid var(--green-dim);
      padding-left: 12px;
    }}
    .stat-label {{
      color: var(--gray);
      font-size: 10px;
      text-transform: uppercase;
      letter-spacing: 1px;
    }}
    .stat-value {{
      font-size: 24px;
      font-weight: bold;
      color: var(--green);
      text-shadow: 0 0 8px var(--green);
    }}
    .stat-value.optimal {{ color: var(--cyan); text-shadow: 0 0 8px var(--cyan); }}
    .stat-unit {{ font-size: 12px; color: var(--gray); }}

    /* Table */
    .table-box {{
      border: 1px solid var(--border);
      margin-bottom: 20px;
    }}
    .table-title {{
      background: var(--border);
      padding: 8px 12px;
      color: var(--amber);
      display: flex;
      justify-content: space-between;
      align-items: center;
    }}
    .table-content {{
      padding: 0;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
    }}
    th {{
      text-align: left;
      padding: 10px 12px;
      background: var(--bg-secondary);
      color: var(--cyan);
      font-size: 10px;
      text-transform: uppercase;
      letter-spacing: 1px;
      border-bottom: 1px solid var(--border);
    }}
    td {{
      padding: 10px 12px;
      border-bottom: 1px solid var(--bg-secondary);
    }}
    tr:hover td {{
      background: rgba(0, 255, 65, 0.05);
    }}
    tr.clickable {{ cursor: pointer; }}

    /* Vehicle badge */
    .v-badge {{
      display: inline-block;
      padding: 2px 8px;
      border-radius: 2px;
      font-size: 11px;
      font-weight: bold;
    }}

    /* Concert section */
    .concert-row {{
      display: flex;
      gap: 20px;
      padding: 12px;
      border-bottom: 1px solid var(--bg-secondary);
    }}
    .concert-row:last-child {{ border-bottom: none; }}
    .concert-time {{
      color: var(--amber);
      font-weight: bold;
      min-width: 120px;
      text-shadow: 0 0 5px var(--amber);
    }}
    .concert-name {{
      color: var(--white);
      font-weight: bold;
    }}
    .concert-meta {{
      color: var(--gray);
      font-size: 11px;
      margin-top: 4px;
    }}
    .concert-instruments {{
      color: var(--cyan);
      font-size: 11px;
      margin-top: 4px;
    }}

    /* Vehicle Page */
    .vehicle-header {{
      display: flex;
      align-items: center;
      gap: 20px;
      margin-bottom: 20px;
      padding: 16px;
      border: 1px solid var(--border);
    }}
    .vehicle-plate {{
      font-size: 24px;
      font-weight: bold;
      text-shadow: 0 0 10px currentColor;
    }}
    .vehicle-stats {{
      display: flex;
      gap: 30px;
    }}
    .vehicle-stat {{
      text-align: center;
    }}
    .vehicle-stat-val {{
      font-size: 20px;
      font-weight: bold;
      color: var(--cyan);
    }}
    .vehicle-stat-lbl {{
      font-size: 10px;
      color: var(--gray);
      text-transform: uppercase;
    }}

    /* Roadmap */
    .roadmap {{
      border: 1px solid var(--border);
    }}
    .roadmap-title {{
      background: var(--border);
      padding: 8px 12px;
      color: var(--amber);
    }}
    .stop {{
      display: flex;
      border-bottom: 1px solid var(--bg-secondary);
    }}
    .stop:last-child {{ border-bottom: none; }}
    .stop-num {{
      width: 50px;
      padding: 12px;
      text-align: center;
      background: var(--bg-secondary);
      color: var(--gray);
      font-weight: bold;
      border-right: 1px solid var(--border);
    }}
    .stop-num.delivery {{ color: var(--cyan); }}
    .stop-num.recovery {{ color: var(--red); }}
    .stop-num.depot {{ color: var(--amber); }}
    .stop-content {{
      flex: 1;
      padding: 12px;
    }}
    .stop-main {{
      display: flex;
      justify-content: space-between;
      margin-bottom: 6px;
    }}
    .stop-name {{
      color: var(--white);
      font-weight: bold;
    }}
    .stop-time {{
      color: var(--green);
      font-weight: bold;
    }}
    .stop-address {{
      color: var(--gray);
      font-size: 11px;
      margin-bottom: 6px;
    }}
    .stop-details {{
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      font-size: 11px;
    }}
    .stop-detail {{
      color: var(--gray);
    }}
    .stop-detail span {{
      color: var(--green);
    }}
    .stop-detail.positive span {{ color: var(--cyan); }}
    .stop-detail.negative span {{ color: var(--red); }}

    .stop-concert {{
      margin-top: 10px;
      padding: 10px;
      background: rgba(255, 176, 0, 0.1);
      border-left: 3px solid var(--amber);
    }}
    .stop-concert-title {{
      color: var(--amber);
      font-weight: bold;
      font-size: 10px;
      text-transform: uppercase;
      margin-bottom: 6px;
    }}
    .stop-concert-time {{
      color: var(--white);
    }}
    .stop-concert-meta {{
      color: var(--gray);
      font-size: 11px;
      margin-top: 4px;
    }}

    .travel-line {{
      padding: 6px 12px 6px 62px;
      color: var(--gray);
      font-size: 11px;
      background: var(--bg);
      border-bottom: 1px solid var(--bg-secondary);
    }}
    .travel-line::before {{
      content: "│";
      margin-right: 20px;
      color: var(--border);
    }}

    /* ASCII Art */
    .ascii-divider {{
      color: var(--border);
      font-size: 10px;
      padding: 8px 0;
      text-align: center;
      letter-spacing: 2px;
    }}

    /* Blinking cursor */
    .cursor {{
      display: inline-block;
      width: 10px;
      height: 16px;
      background: var(--green);
      animation: blink 1s step-end infinite;
      vertical-align: middle;
      margin-left: 4px;
    }}
    @keyframes blink {{
      50% {{ opacity: 0; }}
    }}

    /* Print button */
    .print-btn {{
      background: transparent;
      border: 1px solid var(--cyan);
      color: var(--cyan);
      padding: 6px 12px;
      cursor: pointer;
      font-family: inherit;
      font-size: 11px;
      transition: all 0.1s;
    }}
    .print-btn:hover {{
      background: var(--cyan);
      color: var(--bg);
    }}

    /* Print */
    @media print {{
      body::before, body::after {{ display: none; }}
      body {{ background: white; color: black; }}
      .nav, .print-btn {{ display: none; }}
      .page {{ display: block !important; page-break-after: always; }}
      * {{ color: black !important; border-color: #ccc !important; text-shadow: none !important; }}
    }}
  </style>
</head>
<body>
<div class="terminal">
  <!-- Header -->
  <div class="header">
    <div class="logo">
      ██╗   ██╗██████╗ ██████╗ ██████╗ ██████╗<br>
      ██║   ██║██╔══██╗██╔══██╗██╔══██╗██╔══██╗<br>
      ██║   ██║██████╔╝██████╔╝██████╔╝██║  ██║<br>
      ╚██╗ ██╔╝██╔══██╗██╔═══╝ ██╔═══╝ ██║  ██║<br>
       ╚████╔╝ ██║  ██║██║     ██║     ██████╔╝<br>
        ╚═══╝  ╚═╝  ╚═╝╚═╝     ╚═╝     ╚═════╝
    </div>
    <div class="logo-sub">Vehicle Routing Problem with Pickup & Delivery // Solution Viewer v1.0</div>
  </div>

  <!-- Navigation -->
  <div class="nav">
    <span class="nav-item active" data-page="summary">[S] SUMMARY</span>
    <span class="nav-item" data-page="concerts">[C] CONCERTS</span>
    {vehicle_nav_html}
  </div>

  <!-- Summary Page -->
  <div id="page-summary" class="page active">
    <div class="stats-box">
      <div class="stats-title">═══ SOLUTION STATISTICS ═══</div>
      <div class="stats-content">
        <div class="stats-grid">
          <div class="stat">
            <div class="stat-label">Status</div>
            <div class="stat-value {'optimal' if solve_status == 'Optimal' else ''}">{solve_status}</div>
          </div>
          <div class="stat">
            <div class="stat-label">Objective</div>
            <div class="stat-value">{obj_str}</div>
          </div>
          <div class="stat">
            <div class="stat-label">Active Vehicles</div>
            <div class="stat-value">{active_vehicle_count}<span class="stat-unit">/{len(vehicles)}</span></div>
          </div>
          <div class="stat">
            <div class="stat-label">Total Stops</div>
            <div class="stat-value">{total_stops}</div>
          </div>
          <div class="stat">
            <div class="stat-label">Total Distance</div>
            <div class="stat-value">{total_distance:.1f}<span class="stat-unit">km</span></div>
          </div>
          <div class="stat">
            <div class="stat-label">Total Travel Time</div>
            <div class="stat-value">{total_time:.0f}<span class="stat-unit">min</span></div>
          </div>
          <div class="stat">
            <div class="stat-label">Concerts</div>
            <div class="stat-value">{len(concerts)}</div>
          </div>
        </div>
      </div>
    </div>

    <div class="table-box">
      <div class="table-title">
        <span>═══ FLEET STATUS ═══</span>
      </div>
      <div class="table-content">
        <table>
          <thead>
            <tr>
              <th>#</th>
              <th>Plate</th>
              <th>Capacity</th>
              <th>Stops</th>
              <th>Distance</th>
              <th>Time</th>
            </tr>
          </thead>
          <tbody id="fleet-table"></tbody>
        </table>
      </div>
    </div>

    <div class="ascii-divider">━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━</div>
    <p style="color:var(--gray);font-size:11px;">
      > System ready. Select a vehicle to view detailed roadmap.<span class="cursor"></span>
    </p>
  </div>

  <!-- Concerts Page -->
  <div id="page-concerts" class="page">
    <div class="stats-box">
      <div class="stats-title">═══ CONCERTS SCHEDULE ═══</div>
      <div class="stats-content" id="concerts-list">
        <!-- Generated by JS -->
      </div>
    </div>
  </div>

  <!-- Vehicle Pages (generated by JS) -->
  <div id="vehicle-pages"></div>
</div>

<script>
  var vehicleRoutes = {vehicle_routes_json};
  var roadmaps = {roadmaps_json};
  var concerts = {concerts_json};

  function formatTime(minutes) {{
    if (minutes === null || minutes === undefined) return '——:——';
    var h = Math.floor(minutes / 60);
    var m = Math.round(minutes % 60);
    return ('0' + h).slice(-2) + ':' + ('0' + m).slice(-2);
  }}

  function formatLoad(load, capacity) {{
    if (load === null || load === undefined) return '—';
    var pct = capacity > 0 ? Math.round(100 * load / capacity) : 0;
    return load.toFixed(2) + 'm³ [' + pct + '%]';
  }}

  // Generate fleet table
  function generateFleetTable() {{
    var html = '';
    vehicleRoutes.forEach(function(route, idx) {{
      var roadmap = roadmaps.find(function(r) {{ return r.plate === route.plate; }});
      html += '<tr class="clickable" data-vehicle="' + idx + '">' +
        '<td style="color:var(--gray)">' + (idx + 1) + '</td>' +
        '<td><span class="v-badge" style="background:' + route.color + ';color:#000">' + route.plate + '</span></td>' +
        '<td>' + route.capacity + ' m³</td>' +
        '<td style="color:var(--cyan)">' + (roadmap ? roadmap.stop_count : 0) + '</td>' +
        '<td>' + (roadmap ? roadmap.total_distance.toFixed(1) : 0) + ' km</td>' +
        '<td>' + (roadmap ? Math.round(roadmap.total_travel_time) : 0) + ' min</td>' +
      '</tr>';
    }});
    document.getElementById('fleet-table').innerHTML = html;

    document.querySelectorAll('#fleet-table tr').forEach(function(row) {{
      row.addEventListener('click', function() {{
        showVehiclePage(parseInt(this.getAttribute('data-vehicle')));
      }});
    }});
  }}

  // Generate concerts list
  function generateConcertsList() {{
    if (!concerts || concerts.length === 0) {{
      document.getElementById('concerts-list').innerHTML =
        '<p style="color:var(--gray)">No concerts scheduled.</p>';
      return;
    }}

    var html = '';
    concerts.forEach(function(c, idx) {{
      var instrHtml = '';
      if (c.instrument_counts && Object.keys(c.instrument_counts).length > 0) {{
        var items = Object.entries(c.instrument_counts)
          .sort(function(a,b) {{ return b[1] - a[1]; }})
          .map(function(i) {{ return i[1] + 'x ' + i[0]; }})
          .join(' | ');
        instrHtml = '<div class="concert-instruments">' + items + '</div>';
      }}

      html += '<div class="concert-row">' +
        '<div class="concert-time">' + formatTime(c.concert_start) + ' → ' + formatTime(c.concert_end) + '</div>' +
        '<div style="flex:1">' +
          '<div class="concert-name">[' + (idx+1) + '] ' + c.name + '</div>' +
          '<div class="concert-meta">' +
            'Duration: ' + c.concert_duration + 'min | ' +
            'Setup: ' + c.setup_duration + 'min | ' +
            'Teardown: ' + c.teardown_duration + 'min' +
          '</div>' +
          instrHtml +
        '</div>' +
      '</div>';
    }});
    document.getElementById('concerts-list').innerHTML = html;
  }}

  // Generate vehicle pages
  function generateVehiclePages() {{
    var container = document.getElementById('vehicle-pages');
    var html = '';

    vehicleRoutes.forEach(function(route, idx) {{
      var roadmap = roadmaps.find(function(r) {{ return r.plate === route.plate; }});

      html += '<div id="page-vehicle-' + idx + '" class="page">' +
        '<div class="vehicle-header" style="border-color:' + route.color + '">' +
          '<div class="vehicle-plate" style="color:' + route.color + '">' + route.plate + '</div>' +
          '<div class="vehicle-stats">' +
            '<div class="vehicle-stat"><div class="vehicle-stat-val">' + (roadmap ? roadmap.stop_count : 0) + '</div><div class="vehicle-stat-lbl">Stops</div></div>' +
            '<div class="vehicle-stat"><div class="vehicle-stat-val">' + (roadmap ? roadmap.total_distance.toFixed(1) : 0) + '</div><div class="vehicle-stat-lbl">km</div></div>' +
            '<div class="vehicle-stat"><div class="vehicle-stat-val">' + (roadmap ? Math.round(roadmap.total_travel_time) : 0) + '</div><div class="vehicle-stat-lbl">min</div></div>' +
            '<div class="vehicle-stat"><div class="vehicle-stat-val">' + route.capacity + '</div><div class="vehicle-stat-lbl">m³ cap</div></div>' +
          '</div>' +
          '<button class="print-btn" onclick="window.print()">[ PRINT ]</button>' +
        '</div>' +
        '<div class="roadmap">' +
          '<div class="roadmap-title">═══ ROUTE MANIFEST ═══</div>' +
          '<div id="roadmap-' + idx + '"></div>' +
        '</div>' +
      '</div>';
    }});

    container.innerHTML = html;

    // Generate roadmaps
    vehicleRoutes.forEach(function(route, idx) {{
      var roadmap = roadmaps.find(function(r) {{ return r.plate === route.plate; }});
      if (!roadmap) return;

      var stopsHtml = '';
      roadmap.stops.forEach(function(stop, stopIdx) {{
        var numClass = 'depot';
        if (stop.action === 'Delivery') numClass = 'delivery';
        else if (stop.action === 'Recovery') numClass = 'recovery';

        var twStr = (stop.time_window_start !== null && stop.time_window_end !== null)
          ? formatTime(stop.time_window_start) + '-' + formatTime(stop.time_window_end)
          : '—';

        var deltaClass = '';
        var deltaStr = '—';
        if (stop.volume_delta > 0.001) {{
          deltaClass = 'positive';
          deltaStr = '+' + stop.volume_delta.toFixed(2) + 'm³';
        }} else if (stop.volume_delta < -0.001) {{
          deltaClass = 'negative';
          deltaStr = stop.volume_delta.toFixed(2) + 'm³';
        }}

        var concertHtml = '';
        if (stop.concert) {{
          var c = stop.concert;
          var instrSummary = '';
          if (c.instrument_counts && Object.keys(c.instrument_counts).length > 0) {{
            var total = Object.values(c.instrument_counts).reduce(function(a,b) {{ return a + b; }}, 0);
            instrSummary = ' | ' + total + ' instruments';
          }}
          concertHtml = '<div class="stop-concert">' +
            '<div class="stop-concert-title">▶ Concert</div>' +
            '<div class="stop-concert-time">' + formatTime(c.concert_start) + ' → ' + formatTime(c.concert_start + c.concert_duration) + '</div>' +
            '<div class="stop-concert-meta">Setup: ' + c.setup_duration + 'min | Teardown: ' + c.teardown_duration + 'min' + instrSummary + '</div>' +
          '</div>';
        }}

        stopsHtml += '<div class="stop">' +
          '<div class="stop-num ' + numClass + '">' + stop.step + '</div>' +
          '<div class="stop-content">' +
            '<div class="stop-main">' +
              '<span class="stop-name">' + stop.label + '</span>' +
              '<span class="stop-time">' + formatTime(stop.arrival_time) + '</span>' +
            '</div>' +
            '<div class="stop-address">' + (stop.address || '—') + '</div>' +
            '<div class="stop-details">' +
              '<div class="stop-detail">Action: <span>' + stop.action + '</span></div>' +
              '<div class="stop-detail">Window: <span>' + twStr + '</span></div>' +
              '<div class="stop-detail ' + deltaClass + '">Delta: <span>' + deltaStr + '</span></div>' +
              '<div class="stop-detail">Load: <span>' + formatLoad(stop.load_after, roadmap.capacity) + '</span></div>' +
            '</div>' +
            concertHtml +
          '</div>' +
        '</div>';

        if (stopIdx < roadmap.stops.length - 1) {{
          var next = roadmap.stops[stopIdx + 1];
          if (next.distance_from_prev !== null) {{
            stopsHtml += '<div class="travel-line">' +
              '→ ' + next.distance_from_prev.toFixed(1) + ' km / ' +
              Math.round(next.travel_time_from_prev || 0) + ' min' +
            '</div>';
          }}
        }}
      }});

      document.getElementById('roadmap-' + idx).innerHTML = stopsHtml;
    }});
  }}

  // Navigation
  function showPage(pageId) {{
    document.querySelectorAll('.page').forEach(function(p) {{ p.classList.remove('active'); }});
    document.querySelectorAll('.nav-item').forEach(function(n) {{ n.classList.remove('active'); }});
    document.getElementById('page-' + pageId).classList.add('active');
    document.querySelector('[data-page="' + pageId + '"]').classList.add('active');
  }}

  function showVehiclePage(idx) {{
    document.querySelectorAll('.page').forEach(function(p) {{ p.classList.remove('active'); }});
    document.querySelectorAll('.nav-item').forEach(function(n) {{ n.classList.remove('active'); }});
    document.getElementById('page-vehicle-' + idx).classList.add('active');
    document.querySelector('[data-vehicle="' + idx + '"]').classList.add('active');
  }}

  // Event listeners
  document.querySelectorAll('.nav-item[data-page]').forEach(function(item) {{
    item.addEventListener('click', function() {{
      showPage(this.getAttribute('data-page'));
    }});
  }});

  document.querySelectorAll('.nav-item[data-vehicle]').forEach(function(item) {{
    item.addEventListener('click', function() {{
      showVehiclePage(parseInt(this.getAttribute('data-vehicle')));
    }});
  }});

  // Initialize
  generateFleetTable();
  generateConcertsList();
  generateVehiclePages();
</script>
</body>
</html>
"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Terminal visualization saved to: {output_path}")


# ──────────────────────────────────────────────────────────────────────────────
# Dark Mode Multi-File Generator
# ──────────────────────────────────────────────────────────────────────────────

_DARK_CSS = """
:root {
  --bg-primary: #1a1a1f;
  --bg-secondary: #232328;
  --bg-tertiary: #2d2d35;
  --bg-card: #28282f;
  --border: #3a3a45;
  --text-primary: #e8e8ec;
  --text-secondary: #a0a0a8;
  --text-muted: #6a6a75;
  --orange: #ff8c42;
  --orange-dim: #cc6f35;
  --orange-glow: rgba(255, 140, 66, 0.3);
  --purple: #a855f7;
  --purple-dim: #8b45d4;
  --purple-glow: rgba(168, 85, 247, 0.3);
  --cyan: #22d3ee;
  --green: #4ade80;
  --red: #f87171;
}

* { margin:0; padding:0; box-sizing:border-box; }

body {
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  background: var(--bg-primary);
  color: var(--text-primary);
  line-height: 1.6;
}

a { color: var(--orange); text-decoration: none; }
a:hover { text-decoration: underline; }

/* Header */
.header {
  background: linear-gradient(135deg, var(--bg-secondary) 0%, var(--bg-tertiary) 100%);
  border-bottom: 1px solid var(--border);
  padding: 20px 32px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.header-title {
  font-size: 24px;
  font-weight: 700;
  background: linear-gradient(135deg, var(--orange) 0%, var(--purple) 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}
.header-subtitle { color: var(--text-muted); font-size: 13px; margin-top: 4px; }
.header-nav { display: flex; gap: 12px; }
.nav-link {
  padding: 10px 18px;
  background: var(--bg-tertiary);
  border: 1px solid var(--border);
  border-radius: 8px;
  color: var(--text-secondary);
  font-size: 13px;
  font-weight: 500;
  transition: all 0.2s;
}
.nav-link:hover {
  background: var(--orange);
  color: var(--bg-primary);
  border-color: var(--orange);
  text-decoration: none;
}
.nav-link.active {
  background: var(--purple);
  color: white;
  border-color: var(--purple);
}

/* Main container */
.main { padding: 24px 32px; max-width: 1600px; margin: 0 auto; }

/* Stats Grid */
.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 16px;
  margin-bottom: 24px;
}
.stat-card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 20px;
  transition: transform 0.2s, box-shadow 0.2s;
}
.stat-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 24px rgba(0,0,0,0.3);
}
.stat-label {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: var(--text-muted);
  margin-bottom: 8px;
}
.stat-value {
  font-size: 28px;
  font-weight: 700;
  color: var(--orange);
}
.stat-value.purple { color: var(--purple); }
.stat-unit { font-size: 14px; color: var(--text-muted); font-weight: 400; }

/* Cards */
.card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 12px;
  overflow: hidden;
  margin-bottom: 24px;
}
.card-header {
  padding: 16px 20px;
  border-bottom: 1px solid var(--border);
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.card-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
}
.card-body { padding: 0; }

/* Map */
.map-container {
  width: 100%;
  height: 500px;
  background: var(--bg-secondary);
}
.map-container.full { height: calc(100vh - 200px); min-height: 500px; }

/* Vehicle List */
.vehicle-list { }
.vehicle-item {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border);
  transition: background 0.2s;
  cursor: pointer;
}
.vehicle-item:last-child { border-bottom: none; }
.vehicle-item:hover { background: var(--bg-tertiary); }
.vehicle-color {
  width: 6px;
  height: 48px;
  border-radius: 3px;
}
.vehicle-info { flex: 1; }
.vehicle-plate {
  font-weight: 600;
  font-size: 15px;
  color: var(--text-primary);
}
.vehicle-details {
  font-size: 12px;
  color: var(--text-muted);
  margin-top: 2px;
}
.vehicle-stats {
  display: flex;
  gap: 20px;
  font-size: 13px;
}
.vehicle-stats span { color: var(--text-secondary); }
.vehicle-stats strong { color: var(--orange); }

/* Concert List */
.concert-item {
  display: flex;
  gap: 20px;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border);
}
.concert-item:last-child { border-bottom: none; }
.concert-time {
  min-width: 100px;
  padding: 12px;
  background: linear-gradient(135deg, var(--orange) 0%, var(--orange-dim) 100%);
  border-radius: 8px;
  text-align: center;
  color: white;
}
.concert-time .start { font-size: 18px; font-weight: 700; }
.concert-time .end { font-size: 12px; opacity: 0.8; }
.concert-details { flex: 1; }
.concert-name { font-weight: 600; font-size: 15px; color: var(--text-primary); }
.concert-address { font-size: 12px; color: var(--text-muted); margin-top: 2px; }
.concert-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 10px;
}
.concert-badge {
  padding: 4px 10px;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 500;
}
.concert-badge.duration { background: var(--purple-glow); color: var(--purple); }
.concert-badge.setup { background: rgba(34, 211, 238, 0.15); color: var(--cyan); }
.concert-badge.teardown { background: rgba(248, 113, 113, 0.15); color: var(--red); }
.concert-instruments {
  margin-top: 10px;
  padding: 10px;
  background: var(--bg-tertiary);
  border-radius: 6px;
  font-size: 12px;
  color: var(--text-secondary);
}

/* Roadmap */
.roadmap { }
.stop {
  display: flex;
  border-bottom: 1px solid var(--border);
}
.stop:last-child { border-bottom: none; }
.stop-num {
  width: 60px;
  padding: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg-tertiary);
  border-right: 1px solid var(--border);
}
.stop-badge {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
  font-size: 13px;
  color: white;
}
.stop-badge.depot { background: var(--text-muted); }
.stop-badge.delivery { background: var(--purple); }
.stop-badge.recovery { background: var(--orange); }
.stop-content { flex: 1; padding: 16px; }
.stop-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 8px;
}
.stop-name { font-weight: 600; color: var(--text-primary); }
.stop-time { color: var(--green); font-weight: 600; font-size: 14px; }
.stop-address { font-size: 12px; color: var(--text-muted); margin-bottom: 10px; }
.stop-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  font-size: 12px;
}
.stop-meta-item { color: var(--text-muted); }
.stop-meta-item span { color: var(--text-secondary); }
.stop-meta-item.positive span { color: var(--green); }
.stop-meta-item.negative span { color: var(--red); }
.stop-concert {
  margin-top: 12px;
  padding: 12px;
  background: var(--orange-glow);
  border-left: 3px solid var(--orange);
  border-radius: 0 8px 8px 0;
}
.stop-concert-label {
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: var(--orange);
  font-weight: 600;
  margin-bottom: 6px;
}
.stop-concert-time { color: var(--text-primary); font-weight: 500; }
.stop-concert-meta { font-size: 12px; color: var(--text-muted); margin-top: 4px; }

.travel-line {
  padding: 8px 16px 8px 76px;
  background: var(--bg-primary);
  border-bottom: 1px solid var(--border);
  font-size: 11px;
  color: var(--text-muted);
  display: flex;
  align-items: center;
  gap: 8px;
}
.travel-line::before {
  content: "↓";
  color: var(--purple);
}

/* Print button */
.print-btn {
  padding: 8px 16px;
  background: var(--purple);
  color: white;
  border: none;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.2s;
}
.print-btn:hover { background: var(--purple-dim); }

/* Vehicle page header */
.vehicle-header {
  display: flex;
  align-items: center;
  gap: 24px;
  padding: 24px;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 12px;
  margin-bottom: 24px;
}
.vehicle-header-color {
  width: 8px;
  height: 64px;
  border-radius: 4px;
}
.vehicle-header-info { flex: 1; }
.vehicle-header-plate {
  font-size: 28px;
  font-weight: 700;
  color: var(--text-primary);
}
.vehicle-header-capacity {
  font-size: 14px;
  color: var(--text-muted);
  margin-top: 4px;
}
.vehicle-header-stats {
  display: flex;
  gap: 32px;
}
.vehicle-header-stat { text-align: center; }
.vehicle-header-stat-value {
  font-size: 24px;
  font-weight: 700;
  color: var(--purple);
}
.vehicle-header-stat-label {
  font-size: 11px;
  color: var(--text-muted);
  text-transform: uppercase;
}

/* Leaflet dark theme overrides */
.leaflet-container { background: var(--bg-secondary); }
.leaflet-popup-content-wrapper {
  background: var(--bg-card);
  color: var(--text-primary);
  border-radius: 8px;
  box-shadow: 0 4px 20px rgba(0,0,0,0.4);
}
.leaflet-popup-tip { background: var(--bg-card); }
.leaflet-popup-content { margin: 12px 16px; }
.route-tooltip {
  background: var(--bg-card) !important;
  color: var(--text-primary) !important;
  border: 1px solid var(--border) !important;
  border-radius: 8px !important;
  box-shadow: 0 4px 20px rgba(0,0,0,0.4) !important;
  padding: 12px 16px !important;
}
.route-tooltip hr { border-color: var(--border); }

/* Animation Controls */
.player-controls {
  position: absolute;
  bottom: 24px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 1000;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 16px 24px;
  display: flex;
  align-items: center;
  gap: 16px;
  box-shadow: 0 8px 32px rgba(0,0,0,0.4);
  min-width: 500px;
}
.player-controls.hidden { display: none; }
.play-btn {
  width: 44px;
  height: 44px;
  border-radius: 50%;
  background: var(--orange);
  border: none;
  color: white;
  font-size: 18px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.2s, transform 0.1s;
}
.play-btn:hover { background: var(--orange-dim); transform: scale(1.05); }
.play-btn:active { transform: scale(0.95); }
.time-display {
  font-size: 24px;
  font-weight: 700;
  color: var(--orange);
  min-width: 70px;
  text-align: center;
  font-family: 'JetBrains Mono', monospace;
}
.time-slider-container { flex: 1; }
.time-slider {
  width: 100%;
  height: 8px;
  -webkit-appearance: none;
  appearance: none;
  background: var(--bg-tertiary);
  border-radius: 4px;
  outline: none;
  cursor: pointer;
}
.time-slider::-webkit-slider-thumb {
  -webkit-appearance: none;
  appearance: none;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: var(--purple);
  cursor: pointer;
  box-shadow: 0 2px 8px rgba(168, 85, 247, 0.4);
  transition: transform 0.1s;
}
.time-slider::-webkit-slider-thumb:hover { transform: scale(1.2); }
.time-slider::-moz-range-thumb {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: var(--purple);
  cursor: pointer;
  border: none;
}
.speed-btn {
  padding: 6px 12px;
  background: var(--bg-tertiary);
  border: 1px solid var(--border);
  border-radius: 6px;
  color: var(--text-secondary);
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s;
}
.speed-btn:hover { background: var(--purple); color: white; border-color: var(--purple); }
.speed-btn.active { background: var(--purple); color: white; border-color: var(--purple); }

/* Vehicle Emoji Markers */
.vehicle-emoji-marker {
  background: transparent !important;
  border: none !important;
}
.disco-marker, .sparkle-marker {
  background: transparent !important;
  border: none !important;
}

/* Disco ball animation */
@keyframes disco-spin {
  0% { transform: rotate(0deg) scale(1); }
  25% { transform: rotate(90deg) scale(1.1); }
  50% { transform: rotate(180deg) scale(1); }
  75% { transform: rotate(270deg) scale(1.1); }
  100% { transform: rotate(360deg) scale(1); }
}
.disco-ball {
  animation: disco-spin 0.8s linear infinite;
  filter: drop-shadow(0 0 8px rgba(255, 200, 100, 0.6));
}

/* Mode Toggle */
.mode-toggle {
  display: flex;
  background: var(--bg-tertiary);
  border-radius: 8px;
  padding: 4px;
  gap: 4px;
}
.mode-btn {
  padding: 8px 16px;
  background: transparent;
  border: none;
  border-radius: 6px;
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}
.mode-btn:hover { color: var(--text-primary); }
.mode-btn.active {
  background: var(--purple);
  color: white;
}

/* Vehicle markers for animation */
.vehicle-marker {
  background: var(--bg-card);
  border: 3px solid;
  border-radius: 50%;
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 10px;
  font-weight: 700;
  color: white;
  box-shadow: 0 2px 8px rgba(0,0,0,0.3);
}

/* Concert markers */
.concert-marker {
  width: 12px;
  height: 12px;
  background: var(--orange);
  border-radius: 50%;
  animation: pulse 2s infinite;
}
@keyframes pulse {
  0%, 100% { transform: scale(1); opacity: 1; }
  50% { transform: scale(1.3); opacity: 0.7; }
}

/* Print */
@media print {
  body { background: white; color: black; }
  .header, .nav-link, .player-controls, .mode-toggle { display: none; }
  .card, .stat-card, .vehicle-header { border-color: #ccc; }
  * { color: black !important; background: white !important; }
}
"""

_DARK_JS_HELPERS = """
function formatTime(minutes) {
  if (minutes === null || minutes === undefined) return '—';
  var h = Math.floor(minutes / 60);
  var m = Math.round(minutes % 60);
  return ('0' + h).slice(-2) + 'h' + ('0' + m).slice(-2);
}

function formatLoad(load, capacity) {
  if (load === null || load === undefined) return '—';
  var pct = capacity > 0 ? Math.round(100 * load / capacity) : 0;
  return load.toFixed(2) + ' m³ (' + pct + '%)';
}

function wavyPath(p1, p2, style, nPts) {
  var dLat = p2[0] - p1[0];
  var dLon = p2[1] - p1[1];
  var len = Math.sqrt(dLat * dLat + dLon * dLon);
  if (len < 1e-10) return [p1, p2];
  var perpLat = -dLon / len;
  var perpLon = dLat / len;
  var p1Off = [p1[0] + perpLat * style.offset, p1[1] + perpLon * style.offset];
  var p2Off = [p2[0] + perpLat * style.offset, p2[1] + perpLon * style.offset];
  var midLat = (p1Off[0] + p2Off[0]) / 2 + perpLat * style.curv;
  var midLon = (p1Off[1] + p2Off[1]) / 2 + perpLon * style.curv;
  var pts = [];
  for (var i = 0; i <= nPts; i++) {
    var t = i / nPts;
    var s = 1 - t;
    var baseLat = s*s*p1Off[0] + 2*s*t*midLat + t*t*p2Off[0];
    var baseLon = s*s*p1Off[1] + 2*s*t*midLon + t*t*p2Off[1];
    var envelope = Math.sin(Math.PI * t);
    var wave = style.amp * envelope * Math.sin(style.freq * t * 2 * Math.PI + style.phase);
    pts.push([baseLat + perpLat * wave, baseLon + perpLon * wave]);
  }
  return pts;
}

function randomEdgeStyle() {
  return {
    offset: (Math.random() - 0.5) * 0.002,
    curv: (Math.random() - 0.5) * 0.04,
    freq: 0.5 + Math.random() * 1.5,
    amp: 0.0001 + Math.random() * 0.0004,
    phase: Math.random() * 2 * Math.PI
  };
}

// Animation controller class
function AnimationController(map, vehicleRoutes, options) {
  this.map = map;
  this.vehicleRoutes = vehicleRoutes;
  this.options = options || {};
  this.isPlaying = false;
  this.currentTime = options.startTime || 480; // 8:00 AM default
  this.endTime = options.endTime || 1380; // 11:00 PM default
  this.speed = 1; // 1 = 1 min per frame at 60fps
  this.animationId = null;
  this.lastFrameTime = 0;

  // Layers
  this.routeLayers = {};
  this.vehicleMarkers = {};
  this.discoMarkers = [];
  this.segmentData = {};
  this.staticLayers = []; // Store references to static layers to clear later
  this.concerts = options.concerts || []; // Concert timing data for disco balls

  // Precompute segment timing data and stop times
  this.preprocessRoutes();
}

AnimationController.prototype.preprocessRoutes = function() {
  var self = this;
  this.vehicleRoutes.forEach(function(route) {
    self.segmentData[route.plate] = [];
    self.routeLayers[route.plate] = [];

    route.segments.forEach(function(seg, idx) {
      var startTime = seg.departure_time || 480;
      var endTime = seg.arrival_time || startTime + 30;
      var style = randomEdgeStyle();
      var pts = wavyPath(seg.coords[0], seg.coords[1], style, 64);

      self.segmentData[route.plate].push({
        index: idx,
        startTime: startTime,
        endTime: endTime,
        pts: pts,
        from: seg.from,
        to: seg.to,
        color: route.color,
        fromCoords: seg.coords[0],
        toCoords: seg.coords[1],
        serviceTime: seg.service_time || 15 // Time spent at destination
      });
    });
  });
};

// Get vehicle state at current time
AnimationController.prototype.getVehicleState = function(plate) {
  var segments = this.segmentData[plate];
  if (!segments || segments.length === 0) return null;

  var currentTime = this.currentTime;

  // Check if waiting before first segment
  if (currentTime < segments[0].startTime) {
    return { state: 'waiting', position: segments[0].fromCoords };
  }

  for (var i = 0; i < segments.length; i++) {
    var seg = segments[i];
    var nextSeg = segments[i + 1];

    // Moving during this segment
    if (currentTime >= seg.startTime && currentTime < seg.endTime) {
      var progress = (currentTime - seg.startTime) / (seg.endTime - seg.startTime);
      var ptIdx = Math.floor(progress * (seg.pts.length - 1));
      var t = (progress * (seg.pts.length - 1)) % 1;
      var pos;
      if (ptIdx < seg.pts.length - 1) {
        pos = [
          seg.pts[ptIdx][0] + t * (seg.pts[ptIdx+1][0] - seg.pts[ptIdx][0]),
          seg.pts[ptIdx][1] + t * (seg.pts[ptIdx+1][1] - seg.pts[ptIdx][1])
        ];
      } else {
        pos = seg.pts[seg.pts.length - 1];
      }
      return { state: 'moving', position: pos, color: seg.color };
    }

    // At destination (working) - between arrival and next departure
    if (nextSeg) {
      if (currentTime >= seg.endTime && currentTime < nextSeg.startTime) {
        return { state: 'working', position: seg.toCoords, color: seg.color };
      }
    } else {
      // Last segment - at final destination
      if (currentTime >= seg.endTime) {
        return { state: 'working', position: seg.toCoords, color: seg.color };
      }
    }
  }

  // Default: at last position
  var lastSeg = segments[segments.length - 1];
  return { state: 'waiting', position: lastSeg.toCoords, color: lastSeg.color };
};

AnimationController.prototype.setTime = function(minutes) {
  this.currentTime = Math.max(this.options.startTime || 480, Math.min(minutes, this.endTime));
  this.render();
  if (this.options.onTimeChange) {
    this.options.onTimeChange(this.currentTime);
  }
};

AnimationController.prototype.render = function() {
  var self = this;
  var currentTime = this.currentTime;

  // Clear existing route layers
  Object.keys(this.routeLayers).forEach(function(plate) {
    self.routeLayers[plate].forEach(function(layer) {
      self.map.removeLayer(layer);
    });
    self.routeLayers[plate] = [];
  });

  // Clear vehicle markers
  Object.keys(this.vehicleMarkers).forEach(function(plate) {
    if (self.vehicleMarkers[plate]) {
      self.map.removeLayer(self.vehicleMarkers[plate]);
    }
  });

  // Clear disco markers
  this.discoMarkers.forEach(function(m) { self.map.removeLayer(m); });
  this.discoMarkers = [];

  // Draw segments based on current time
  this.vehicleRoutes.forEach(function(route) {
    var segments = self.segmentData[route.plate];

    segments.forEach(function(seg) {
      if (currentTime >= seg.endTime) {
        // Segment fully completed - draw full line
        var line = L.polyline(seg.pts, {
          color: route.color,
          weight: 6,
          opacity: 0.9
        }).addTo(self.map);
        self.routeLayers[route.plate].push(line);

        // Arrow
        var decorator = L.polylineDecorator(line, {
          patterns: [{
            offset: '50%', repeat: 0,
            symbol: L.Symbol.arrowHead({
              pixelSize: 14, polygon: false,
              pathOptions: { stroke: true, color: route.color, weight: 3, opacity: 1 }
            })
          }]
        }).addTo(self.map);
        self.routeLayers[route.plate].push(decorator);
      } else if (currentTime >= seg.startTime && currentTime < seg.endTime) {
        // Segment in progress - draw partial line
        var progress = (currentTime - seg.startTime) / (seg.endTime - seg.startTime);
        var pointIndex = Math.floor(progress * (seg.pts.length - 1));
        var partialPts = seg.pts.slice(0, pointIndex + 1);

        if (partialPts.length > 1) {
          var line = L.polyline(partialPts, {
            color: route.color,
            weight: 6,
            opacity: 0.9
          }).addTo(self.map);
          self.routeLayers[route.plate].push(line);
        }
      }
    });

    // Get vehicle state and draw emoji marker
    var state = self.getVehicleState(route.plate);
    if (state && state.position) {
      var emoji = '🚜'; // Default: tractor (moving)
      if (state.state === 'waiting') emoji = '🛏️'; // Bed (waiting)
      else if (state.state === 'working') emoji = '🔨'; // Hammer (working)

      var icon = L.divIcon({
        className: 'vehicle-emoji-marker',
        html: '<div style="font-size:28px;text-shadow:0 2px 4px rgba(0,0,0,0.3);filter:drop-shadow(0 2px 4px rgba(0,0,0,0.3));transform:translate(-50%,-50%)">' + emoji + '</div>',
        iconSize: [40, 40],
        iconAnchor: [20, 20]
      });
      self.vehicleMarkers[route.plate] = L.marker(state.position, { icon: icon, zIndexOffset: 1000 }).addTo(self.map);
    }
  });

  // Render disco balls at concert venues during concert times
  this.renderDiscoBalls(currentTime);
};

AnimationController.prototype.renderDiscoBalls = function(currentTime) {
  var self = this;

  this.concerts.forEach(function(concert) {
    if (!concert.coords) return;

    var concertStart = concert.concert_start;
    var concertEnd = concert.concert_start + concert.concert_duration;

    // Show disco ball during concert
    if (currentTime >= concertStart && currentTime < concertEnd) {
      // Pulsing animation offset based on time
      var pulse = Math.sin((currentTime - concertStart) * 0.5) * 0.2 + 1;

      // Create disco ball with rotation animation
      var icon = L.divIcon({
        className: 'disco-marker',
        html: '<div class="disco-ball" style="font-size:' + (24 * pulse) + 'px;animation:disco-spin 0.5s linear infinite;">🪩</div>',
        iconSize: [40, 40],
        iconAnchor: [20, 20]
      });

      var marker = L.marker(concert.coords, { icon: icon, zIndexOffset: 900 }).addTo(self.map);
      self.discoMarkers.push(marker);

      // Add sparkle particles around the disco ball
      for (var i = 0; i < 3; i++) {
        var angle = ((currentTime * 10) + i * 120) * Math.PI / 180;
        var radius = 0.0003 + Math.sin(currentTime * 0.3 + i) * 0.0001;
        var sparklePos = [
          concert.coords[0] + Math.cos(angle) * radius,
          concert.coords[1] + Math.sin(angle) * radius
        ];
        var sparkleIcon = L.divIcon({
          className: 'sparkle-marker',
          html: '<div style="font-size:14px;opacity:' + (0.5 + Math.sin(currentTime + i) * 0.3) + '">✨</div>',
          iconSize: [20, 20],
          iconAnchor: [10, 10]
        });
        var sparkle = L.marker(sparklePos, { icon: sparkleIcon, zIndexOffset: 800 }).addTo(self.map);
        self.discoMarkers.push(sparkle);
      }
    }
  });
};

AnimationController.prototype.play = function() {
  if (this.isPlaying) return;
  this.isPlaying = true;
  this.lastFrameTime = performance.now();
  this.animate();
  if (this.options.onPlayStateChange) {
    this.options.onPlayStateChange(true);
  }
};

AnimationController.prototype.pause = function() {
  this.isPlaying = false;
  if (this.animationId) {
    cancelAnimationFrame(this.animationId);
    this.animationId = null;
  }
  if (this.options.onPlayStateChange) {
    this.options.onPlayStateChange(false);
  }
};

AnimationController.prototype.toggle = function() {
  if (this.isPlaying) {
    this.pause();
  } else {
    this.play();
  }
};

AnimationController.prototype.animate = function() {
  if (!this.isPlaying) return;

  var self = this;
  var now = performance.now();
  var delta = (now - this.lastFrameTime) / 1000; // seconds
  this.lastFrameTime = now;

  // Advance time (speed is in minutes per second of real time)
  this.currentTime += delta * this.speed * 10; // 10x real time by default

  if (this.currentTime >= this.endTime) {
    this.currentTime = this.options.startTime || 480;
  }

  this.render();

  if (this.options.onTimeChange) {
    this.options.onTimeChange(this.currentTime);
  }

  this.animationId = requestAnimationFrame(function() {
    self.animate();
  });
};

AnimationController.prototype.setSpeed = function(speed) {
  this.speed = speed;
};

AnimationController.prototype.reset = function() {
  this.pause();
  this.currentTime = this.options.startTime || 480;

  // Clear any static layers that were added before animation started
  var self = this;
  this.staticLayers.forEach(function(layer) {
    self.map.removeLayer(layer);
  });
  this.staticLayers = [];

  this.render();
  if (this.options.onTimeChange) {
    this.options.onTimeChange(this.currentTime);
  }
};

AnimationController.prototype.registerStaticLayer = function(layer) {
  this.staticLayers.push(layer);
};

AnimationController.prototype.clearStaticLayers = function() {
  var self = this;
  this.staticLayers.forEach(function(layer) {
    self.map.removeLayer(layer);
  });
  this.staticLayers = [];
};

AnimationController.prototype.showStatic = function() {
  this.pause();
  var self = this;

  // Clear animated layers
  Object.keys(this.routeLayers).forEach(function(plate) {
    self.routeLayers[plate].forEach(function(layer) {
      self.map.removeLayer(layer);
    });
    self.routeLayers[plate] = [];
  });
  Object.keys(this.vehicleMarkers).forEach(function(plate) {
    if (self.vehicleMarkers[plate]) {
      self.map.removeLayer(self.vehicleMarkers[plate]);
    }
  });

  // Draw all routes fully
  this.vehicleRoutes.forEach(function(route) {
    route.segments.forEach(function(seg) {
      var style = randomEdgeStyle();
      var pts = wavyPath(seg.coords[0], seg.coords[1], style, 64);

      var tooltipHtml = '<div style="min-width:200px">' +
        '<b style="color:' + route.color + '">' + route.plate + '</b> Step ' + seg.step + '<hr>' +
        '<b>From:</b> ' + seg.from + '<br>' +
        '<b>To:</b> ' + seg.to + '<hr>' +
        '<b>Departure:</b> ' + formatTime(seg.departure_time) + '<br>' +
        '<b>Arrival:</b> ' + formatTime(seg.arrival_time) +
        '</div>';

      var line = L.polyline(pts, {
        color: route.color, weight: 6, opacity: 0.8
      }).bindTooltip(tooltipHtml, {sticky: true, className: 'route-tooltip'}).addTo(self.map);
      self.routeLayers[route.plate].push(line);

      var decorator = L.polylineDecorator(line, {
        patterns: [{
          offset: '50%', repeat: 0,
          symbol: L.Symbol.arrowHead({
            pixelSize: 16, polygon: false,
            pathOptions: { stroke: true, color: route.color, weight: 3, opacity: 1 }
          })
        }]
      }).addTo(self.map);
      self.routeLayers[route.plate].push(decorator);
    });
  });
};
"""


def render_html_multi(
    result,
    data: dict | None,
    output_dir: str,
    solve_status: str = "",
    objective_value: float | None = None,
) -> list[str]:
    """
    Generate multiple HTML files: one summary + one per vehicle.
    Dark mode with grey/orange/purple theme.

    Returns list of generated file paths.
    """
    import os
    import pulp

    os.makedirs(output_dir, exist_ok=True)

    problem = result.problem
    vehicles = list(problem.vehicles_dict.values())
    color_map = {
        v.id: _VEHICLE_COLORS[i % len(_VEHICLE_COLORS)]
        for i, v in enumerate(vehicles)
    }

    if objective_value is None:
        objective_value = pulp.value(result.pulp_problem.objective)
    if not solve_status:
        solve_status = pulp.LpStatus[result.pulp_problem.status]

    # Build data
    vehicle_routes = _build_vehicle_routes(result, color_map, data)
    roadmaps = _build_roadmap_data(result, data)
    concerts = _build_concerts_data(data)

    # Map center
    all_lats = [n.gps_coordinates[0] for n in problem.all_nodes if n.gps_coordinates]
    all_lons = [n.gps_coordinates[1] for n in problem.all_nodes if n.gps_coordinates]
    center_lat = sum(all_lats) / len(all_lats)
    center_lon = sum(all_lons) / len(all_lons)

    # Stats
    obj_str = f"{objective_value:.3f}" if objective_value is not None else "—"
    active_vehicle_count = len(vehicle_routes)
    total_stops = sum(r["stop_count"] for r in roadmaps)
    total_distance = sum(r["total_distance"] for r in roadmaps)
    total_time = sum(r["total_travel_time"] for r in roadmaps)

    generated_files = []

    # ══════════════════════════════════════════════════════════════════════════
    # SUMMARY PAGE
    # ══════════════════════════════════════════════════════════════════════════

    # Build vehicle nav links
    vehicle_nav_html = ""
    for i, route in enumerate(vehicle_routes):
        plate = route["plate"]
        safe_plate = plate.replace(" ", "_").replace("-", "_")
        vehicle_nav_html += f'<a href="vehicle_{safe_plate}.html" class="nav-link">{plate}</a>\n'

    # Build vehicle list HTML
    vehicle_list_html = ""
    for i, route in enumerate(vehicle_routes):
        plate = route["plate"]
        color = route["color"]
        safe_plate = plate.replace(" ", "_").replace("-", "_")
        roadmap = next((r for r in roadmaps if r["plate"] == plate), None)
        v_stops = roadmap["stop_count"] if roadmap else 0
        v_dist = f'{roadmap["total_distance"]:.1f}' if roadmap else "0"
        v_time = int(roadmap["total_travel_time"]) if roadmap else 0
        vehicle_list_html += f'''
        <a href="vehicle_{safe_plate}.html" class="vehicle-item" style="text-decoration:none">
          <div class="vehicle-color" style="background:{color}"></div>
          <div class="vehicle-info">
            <div class="vehicle-plate">{plate}</div>
            <div class="vehicle-details">Capacity: {route["capacity"]} m³</div>
          </div>
          <div class="vehicle-stats">
            <span><strong>{v_stops}</strong> stops</span>
            <span><strong>{v_dist}</strong> km</span>
            <span><strong>{v_time}</strong> min</span>
          </div>
        </a>'''

    # Build concerts HTML
    concerts_html = ""
    for c in concerts:
        instr_html = ""
        if c["instrument_counts"]:
            items = [f'{v}x {k}' for k, v in sorted(c["instrument_counts"].items(), key=lambda x: -x[1])]
            instr_html = f'<div class="concert-instruments">{", ".join(items)}</div>'

        concerts_html += f'''
        <div class="concert-item">
          <div class="concert-time">
            <div class="start">{_hhmm(c["concert_start"])}</div>
            <div class="end">{_hhmm(c["concert_end"])}</div>
          </div>
          <div class="concert-details">
            <div class="concert-name">{c["name"]}</div>
            <div class="concert-address">{c["address"]}</div>
            <div class="concert-meta">
              <span class="concert-badge duration">{c["concert_duration"]} min</span>
              <span class="concert-badge setup">Setup {c["setup_duration"]} min</span>
              <span class="concert-badge teardown">Teardown {c["teardown_duration"]} min</span>
            </div>
            {instr_html}
          </div>
        </div>'''

    # Build markers data for summary map (all nodes)
    markers_data = []
    for node in problem.all_nodes:
        ll = _node_latlng(node)
        if ll is None:
            continue
        lat, lon = ll

        if isinstance(node, DepositNode):
            radius, fill_color, stroke_color = 12, "#6a6a75", "#fff"
        elif isinstance(node, DeliveryNode):
            radius, fill_color, stroke_color = 10, "#a855f7", "#8b45d4"
        else:
            radius, fill_color, stroke_color = 10, "#ff8c42", "#cc6f35"

        markers_data.append({
            "lat": lat, "lon": lon,
            "radius": radius, "fillColor": fill_color, "strokeColor": stroke_color,
            "nodeId": node.id,
        })

    vehicle_routes_json = json.dumps(vehicle_routes, separators=(",", ":"))
    markers_json = json.dumps(markers_data, separators=(",", ":"))
    concerts_json = json.dumps(concerts, separators=(",", ":"))

    summary_html = f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>VRPPD Solution — Summary</title>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;700&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <script src="https://unpkg.com/leaflet-polylinedecorator@1.6.0/dist/leaflet.polylineDecorator.js"></script>
  <style>{_DARK_CSS}</style>
</head>
<body>
  <header class="header">
    <div>
      <div class="header-title">VRPPD Solution</div>
      <div class="header-subtitle">Vehicle Routing with Pickup & Delivery</div>
    </div>
    <nav class="header-nav">
      <span class="nav-link active">Summary</span>
      {vehicle_nav_html}
    </nav>
  </header>

  <main class="main">
    <div class="stats-grid">
      <div class="stat-card">
        <div class="stat-label">Status</div>
        <div class="stat-value">{solve_status}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Objective</div>
        <div class="stat-value purple">{obj_str}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Active Vehicles</div>
        <div class="stat-value">{active_vehicle_count}<span class="stat-unit">/{len(vehicles)}</span></div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Total Stops</div>
        <div class="stat-value">{total_stops}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Total Distance</div>
        <div class="stat-value">{total_distance:.1f}<span class="stat-unit">km</span></div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Total Time</div>
        <div class="stat-value">{int(total_time)}<span class="stat-unit">min</span></div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Concerts</div>
        <div class="stat-value purple">{len(concerts)}</div>
      </div>
    </div>

    <div class="card" style="position:relative;">
      <div class="card-header">
        <span class="card-title">All Routes</span>
        <div class="mode-toggle">
          <button class="mode-btn active" id="mode-static">Static</button>
          <button class="mode-btn" id="mode-dynamic">Dynamic</button>
        </div>
      </div>
      <div class="card-body" style="position:relative;">
        <div id="map" class="map-container full"></div>
        <div id="player-controls" class="player-controls hidden">
          <button id="play-btn" class="play-btn">▶</button>
          <div class="time-display" id="time-display">08h00</div>
          <div class="time-slider-container">
            <input type="range" class="time-slider" id="time-slider" min="480" max="1380" value="480">
          </div>
          <button class="speed-btn" data-speed="0.5">0.5x</button>
          <button class="speed-btn active" data-speed="1">1x</button>
          <button class="speed-btn" data-speed="2">2x</button>
          <button class="speed-btn" data-speed="5">5x</button>
        </div>
      </div>
    </div>

    <div style="display:grid; grid-template-columns: 1fr 1fr; gap:24px;">
      <div class="card">
        <div class="card-header">
          <span class="card-title">Vehicles</span>
        </div>
        <div class="card-body">
          <div class="vehicle-list">{vehicle_list_html}</div>
        </div>
      </div>

      <div class="card">
        <div class="card-header">
          <span class="card-title">Concerts</span>
        </div>
        <div class="card-body">
          {concerts_html if concerts_html else '<p style="padding:20px;color:var(--text-muted)">No concerts</p>'}
        </div>
      </div>
    </div>
  </main>

  <script>
    {_DARK_JS_HELPERS}

    var vehicleRoutes = {vehicle_routes_json};
    var markersData = {markers_json};
    var concertsData = {concerts_json};

    // Build concerts with coords for animation
    var concertsWithCoords = concertsData.map(function(c) {{
      return {{
        concert_start: c.concert_start,
        concert_duration: c.concert_duration,
        coords: (c.lat && c.lon) ? [c.lat, c.lon] : null,
        name: c.name
      }};
    }}).filter(function(c) {{ return c.coords !== null; }});

    // Initialize map
    var map = L.map('map').setView([{center_lat}, {center_lon}], 11);
    L.tileLayer('https://tile.openstreetmap.org/' + '{{z}}/{{x}}/{{y}}.png', {{
      attribution: '&copy; OpenStreetMap'
    }}).addTo(map);

    // Animation controller (initialized first to register static layers)
    var animController = new AnimationController(map, vehicleRoutes, {{
      startTime: 480,
      endTime: 1380,
      concerts: concertsWithCoords,
      onTimeChange: function(time) {{
        document.getElementById('time-display').textContent = formatTime(time);
        document.getElementById('time-slider').value = time;
      }},
      onPlayStateChange: function(isPlaying) {{
        document.getElementById('play-btn').textContent = isPlaying ? '⏸' : '▶';
      }}
    }});

    // Draw all routes (static mode)
    var bounds = [];
    vehicleRoutes.forEach(function(route) {{
      route.segments.forEach(function(seg) {{
        var style = randomEdgeStyle();
        var pts = wavyPath(seg.coords[0], seg.coords[1], style, 64);
        bounds.push(seg.coords[0]);
        bounds.push(seg.coords[1]);

        var tooltipHtml = '<div style="min-width:200px">' +
          '<b style="color:' + route.color + '">' + route.plate + '</b> Step ' + seg.step + '<hr>' +
          '<b>From:</b> ' + seg.from + '<br>' +
          '<b>To:</b> ' + seg.to + '<hr>' +
          '<b>Departure:</b> ' + formatTime(seg.departure_time) + '<br>' +
          '<b>Arrival:</b> ' + formatTime(seg.arrival_time) +
          '</div>';

        var line = L.polyline(pts, {{
          color: route.color, weight: 6, opacity: 0.8
        }}).bindTooltip(tooltipHtml, {{sticky: true, className: 'route-tooltip'}}).addTo(map);
        animController.registerStaticLayer(line);

        var decorator = L.polylineDecorator(line, {{
          patterns: [{{
            offset: '50%', repeat: 0,
            symbol: L.Symbol.arrowHead({{
              pixelSize: 16, polygon: false,
              pathOptions: {{ stroke: true, color: route.color, weight: 3, opacity: 1 }}
            }})
          }}]
        }}).addTo(map);
        animController.registerStaticLayer(decorator);
      }});
    }});

    // Add markers
    markersData.forEach(function(m) {{
      var marker = L.circleMarker([m.lat, m.lon], {{
        radius: m.radius, color: m.strokeColor, weight: 2,
        fillColor: m.fillColor, fillOpacity: 0.9
      }}).addTo(map);
      animController.registerStaticLayer(marker);
    }});

    if (bounds.length > 0) {{
      map.fitBounds(bounds, {{ padding: [30, 30] }});
    }}

    // Mode toggle
    var isStaticMode = true;

    document.getElementById('mode-static').addEventListener('click', function() {{
      if (isStaticMode) return;
      isStaticMode = true;
      this.classList.add('active');
      document.getElementById('mode-dynamic').classList.remove('active');
      document.getElementById('player-controls').classList.add('hidden');

      // Show static view
      animController.showStatic();

      // Re-add static markers
      markersData.forEach(function(m) {{
        var marker = L.circleMarker([m.lat, m.lon], {{
          radius: m.radius, color: m.strokeColor, weight: 2,
          fillColor: m.fillColor, fillOpacity: 0.9
        }}).addTo(map);
        animController.registerStaticLayer(marker);
      }});
    }});

    document.getElementById('mode-dynamic').addEventListener('click', function() {{
      if (!isStaticMode) return;
      isStaticMode = false;
      this.classList.add('active');
      document.getElementById('mode-static').classList.remove('active');
      document.getElementById('player-controls').classList.remove('hidden');

      // Clear ALL static layers and start animation
      animController.clearStaticLayers();
      animController.currentTime = animController.options.startTime || 480;
      animController.render();
    }});

    // Play button
    document.getElementById('play-btn').addEventListener('click', function() {{
      animController.toggle();
    }});

    // Time slider
    document.getElementById('time-slider').addEventListener('input', function() {{
      animController.setTime(parseInt(this.value));
    }});

    // Speed buttons
    document.querySelectorAll('.speed-btn').forEach(function(btn) {{
      btn.addEventListener('click', function() {{
        document.querySelectorAll('.speed-btn').forEach(function(b) {{ b.classList.remove('active'); }});
        this.classList.add('active');
        animController.setSpeed(parseFloat(this.getAttribute('data-speed')));
      }});
    }});
  </script>
</body>
</html>'''

    summary_path = os.path.join(output_dir, "summary.html")
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write(summary_html)
    generated_files.append(summary_path)

    # ══════════════════════════════════════════════════════════════════════════
    # PER-VEHICLE PAGES
    # ══════════════════════════════════════════════════════════════════════════

    for route in vehicle_routes:
        plate = route["plate"]
        color = route["color"]
        safe_plate = plate.replace(" ", "_").replace("-", "_")
        roadmap = next((r for r in roadmaps if r["plate"] == plate), None)

        if not roadmap:
            continue

        # Build nav links
        nav_links = '<a href="summary.html" class="nav-link">Summary</a>\n'
        for r in vehicle_routes:
            p = r["plate"]
            sp = p.replace(" ", "_").replace("-", "_")
            active = "active" if p == plate else ""
            nav_links += f'<a href="vehicle_{sp}.html" class="nav-link {active}">{p}</a>\n'

        # Build stops HTML
        stops_html = ""
        for i, stop in enumerate(roadmap["stops"]):
            badge_class = "depot"
            if stop["action"] == "Delivery":
                badge_class = "delivery"
            elif stop["action"] == "Recovery":
                badge_class = "recovery"

            tw_str = "—"
            if stop["time_window_start"] is not None and stop["time_window_end"] is not None:
                tw_str = f'{_hhmm(stop["time_window_start"])} – {_hhmm(stop["time_window_end"])}'

            delta_class = ""
            delta_str = "—"
            if stop["volume_delta"] and abs(stop["volume_delta"]) > 0.001:
                if stop["volume_delta"] > 0:
                    delta_class = "positive"
                    delta_str = f'+{stop["volume_delta"]:.2f} m³'
                else:
                    delta_class = "negative"
                    delta_str = f'{stop["volume_delta"]:.2f} m³'

            load_str = f'{stop["load_after"]:.2f} m³' if stop["load_after"] is not None else "—"

            # Concert info
            concert_html = ""
            if stop.get("concert"):
                c = stop["concert"]
                c_start = _hhmm(c["concert_start"])
                c_end = _hhmm(c["concert_start"] + c["concert_duration"])
                instr_count = sum(c["instrument_counts"].values()) if c["instrument_counts"] else 0
                concert_html = f'''
                <div class="stop-concert">
                  <div class="stop-concert-label">Concert</div>
                  <div class="stop-concert-time">{c_start} → {c_end} ({c["concert_duration"]} min)</div>
                  <div class="stop-concert-meta">Setup: {c["setup_duration"]} min · Teardown: {c["teardown_duration"]} min · {instr_count} instruments</div>
                </div>'''

            stops_html += f'''
            <div class="stop">
              <div class="stop-num">
                <div class="stop-badge {badge_class}">{stop["step"]}</div>
              </div>
              <div class="stop-content">
                <div class="stop-header">
                  <span class="stop-name">{stop["label"]}</span>
                  <span class="stop-time">{_hhmm(stop["arrival_time"])}</span>
                </div>
                <div class="stop-address">{stop["address"] or "—"}</div>
                <div class="stop-meta">
                  <div class="stop-meta-item">Action: <span>{stop["action"]}</span></div>
                  <div class="stop-meta-item">Window: <span>{tw_str}</span></div>
                  <div class="stop-meta-item {delta_class}">Delta: <span>{delta_str}</span></div>
                  <div class="stop-meta-item">Load: <span>{load_str}</span></div>
                </div>
                {concert_html}
              </div>
            </div>'''

            # Travel line
            if i < len(roadmap["stops"]) - 1:
                next_stop = roadmap["stops"][i + 1]
                if next_stop.get("distance_from_prev") is not None:
                    dist = next_stop["distance_from_prev"]
                    time = next_stop.get("travel_time_from_prev") or 0
                    stops_html += f'<div class="travel-line">{dist:.1f} km · {int(time)} min</div>'

        # Build route JSON for this vehicle only
        route_json = json.dumps([route], separators=(",", ":"))

        # Build markers for this route
        route_markers = []
        route_node_ids = set()
        for stop in roadmap["stops"]:
            if stop.get("gps"):
                route_node_ids.add(f'{stop["gps"][0]:.5f},{stop["gps"][1]:.5f}')

        for m in markers_data:
            key = f'{m["lat"]:.5f},{m["lon"]:.5f}'
            if key in route_node_ids or m["nodeId"] == 0:
                route_markers.append(m)

        route_markers_json = json.dumps(route_markers, separators=(",", ":"))

        vehicle_html = f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>VRPPD — {plate}</title>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;700&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <script src="https://unpkg.com/leaflet-polylinedecorator@1.6.0/dist/leaflet.polylineDecorator.js"></script>
  <style>{_DARK_CSS}</style>
</head>
<body>
  <header class="header">
    <div>
      <div class="header-title">VRPPD Solution</div>
      <div class="header-subtitle">Vehicle Routing with Pickup & Delivery</div>
    </div>
    <nav class="header-nav">
      {nav_links}
    </nav>
  </header>

  <main class="main">
    <div class="vehicle-header">
      <div class="vehicle-header-color" style="background:{color}"></div>
      <div class="vehicle-header-info">
        <div class="vehicle-header-plate">{plate}</div>
        <div class="vehicle-header-capacity">Capacity: {route["capacity"]} m³</div>
      </div>
      <div class="vehicle-header-stats">
        <div class="vehicle-header-stat">
          <div class="vehicle-header-stat-value">{roadmap["stop_count"]}</div>
          <div class="vehicle-header-stat-label">Stops</div>
        </div>
        <div class="vehicle-header-stat">
          <div class="vehicle-header-stat-value">{roadmap["total_distance"]:.1f}</div>
          <div class="vehicle-header-stat-label">km</div>
        </div>
        <div class="vehicle-header-stat">
          <div class="vehicle-header-stat-value">{int(roadmap["total_travel_time"])}</div>
          <div class="vehicle-header-stat-label">min</div>
        </div>
      </div>
      <button class="print-btn" onclick="window.print()">Print Roadmap</button>
    </div>

    <div style="display:grid; grid-template-columns: 1fr 450px; gap:24px;">
      <div class="card" style="position:relative;">
        <div class="card-header">
          <span class="card-title">Route Map</span>
          <div class="mode-toggle">
            <button class="mode-btn active" id="mode-static">Static</button>
            <button class="mode-btn" id="mode-dynamic">Dynamic</button>
          </div>
        </div>
        <div class="card-body" style="position:relative;">
          <div id="map" class="map-container full"></div>
          <div id="player-controls" class="player-controls hidden">
            <button id="play-btn" class="play-btn">▶</button>
            <div class="time-display" id="time-display">08h00</div>
            <div class="time-slider-container">
              <input type="range" class="time-slider" id="time-slider" min="480" max="1380" value="480">
            </div>
            <button class="speed-btn" data-speed="0.5">0.5x</button>
            <button class="speed-btn active" data-speed="1">1x</button>
            <button class="speed-btn" data-speed="2">2x</button>
            <button class="speed-btn" data-speed="5">5x</button>
          </div>
        </div>
      </div>

      <div class="card">
        <div class="card-header">
          <span class="card-title">Roadmap</span>
        </div>
        <div class="card-body">
          <div class="roadmap">{stops_html}</div>
        </div>
      </div>
    </div>
  </main>

  <script>
    {_DARK_JS_HELPERS}

    var vehicleRoutes = {route_json};
    var markersData = {route_markers_json};
    var concertsData = {concerts_json};

    // Build concerts with coords for animation
    var concertsWithCoords = concertsData.map(function(c) {{
      return {{
        concert_start: c.concert_start,
        concert_duration: c.concert_duration,
        coords: (c.lat && c.lon) ? [c.lat, c.lon] : null,
        name: c.name
      }};
    }}).filter(function(c) {{ return c.coords !== null; }});

    var map = L.map('map').setView([{center_lat}, {center_lon}], 12);
    L.tileLayer('https://tile.openstreetmap.org/' + '{{z}}/{{x}}/{{y}}.png', {{
      attribution: '&copy; OpenStreetMap'
    }}).addTo(map);

    // Animation controller (initialized first to register static layers)
    var animController = new AnimationController(map, vehicleRoutes, {{
      startTime: 480,
      endTime: 1380,
      concerts: concertsWithCoords,
      onTimeChange: function(time) {{
        document.getElementById('time-display').textContent = formatTime(time);
        document.getElementById('time-slider').value = time;
      }},
      onPlayStateChange: function(isPlaying) {{
        document.getElementById('play-btn').textContent = isPlaying ? '⏸' : '▶';
      }}
    }});

    var bounds = [];
    vehicleRoutes.forEach(function(route) {{
      route.segments.forEach(function(seg) {{
        var style = randomEdgeStyle();
        var pts = wavyPath(seg.coords[0], seg.coords[1], style, 64);
        bounds.push(seg.coords[0]);
        bounds.push(seg.coords[1]);

        var tooltipHtml = '<div style="min-width:200px">' +
          '<b style="color:' + route.color + '">' + route.plate + '</b> Step ' + seg.step + '<hr>' +
          '<b>From:</b> ' + seg.from + '<br>' +
          '<b>To:</b> ' + seg.to + '<hr>' +
          '<b>Transported:</b> ' + formatLoad(seg.transported_load, route.capacity) + '<br>' +
          '<b>Departure:</b> ' + formatTime(seg.departure_time) + '<br>' +
          '<b>Arrival:</b> ' + formatTime(seg.arrival_time) +
          '</div>';

        var line = L.polyline(pts, {{
          color: route.color, weight: 8, opacity: 0.9
        }}).bindTooltip(tooltipHtml, {{sticky: true, className: 'route-tooltip'}}).addTo(map);
        animController.registerStaticLayer(line);

        var decorator = L.polylineDecorator(line, {{
          patterns: [{{
            offset: '50%', repeat: 0,
            symbol: L.Symbol.arrowHead({{
              pixelSize: 20, polygon: false,
              pathOptions: {{ stroke: true, color: route.color, weight: 4, opacity: 1 }}
            }})
          }}]
        }}).addTo(map);
        animController.registerStaticLayer(decorator);
      }});
    }});

    markersData.forEach(function(m) {{
      var marker = L.circleMarker([m.lat, m.lon], {{
        radius: m.radius, color: m.strokeColor, weight: 2,
        fillColor: m.fillColor, fillOpacity: 0.9
      }}).addTo(map);
      animController.registerStaticLayer(marker);
    }});

    if (bounds.length > 0) {{
      map.fitBounds(bounds, {{ padding: [40, 40] }});
    }}

    // Mode toggle
    var isStaticMode = true;

    document.getElementById('mode-static').addEventListener('click', function() {{
      if (isStaticMode) return;
      isStaticMode = true;
      this.classList.add('active');
      document.getElementById('mode-dynamic').classList.remove('active');
      document.getElementById('player-controls').classList.add('hidden');

      // Show static view
      animController.showStatic();

      // Re-add static markers
      markersData.forEach(function(m) {{
        var marker = L.circleMarker([m.lat, m.lon], {{
          radius: m.radius, color: m.strokeColor, weight: 2,
          fillColor: m.fillColor, fillOpacity: 0.9
        }}).addTo(map);
        animController.registerStaticLayer(marker);
      }});
    }});

    document.getElementById('mode-dynamic').addEventListener('click', function() {{
      if (!isStaticMode) return;
      isStaticMode = false;
      this.classList.add('active');
      document.getElementById('mode-static').classList.remove('active');
      document.getElementById('player-controls').classList.remove('hidden');

      // Clear ALL static layers and start animation
      animController.clearStaticLayers();
      animController.currentTime = animController.options.startTime || 480;
      animController.render();
    }});

    document.getElementById('play-btn').addEventListener('click', function() {{
      animController.toggle();
    }});

    document.getElementById('time-slider').addEventListener('input', function() {{
      animController.setTime(parseInt(this.value));
    }});

    document.querySelectorAll('.speed-btn').forEach(function(btn) {{
      btn.addEventListener('click', function() {{
        document.querySelectorAll('.speed-btn').forEach(function(b) {{ b.classList.remove('active'); }});
        this.classList.add('active');
        animController.setSpeed(parseFloat(this.getAttribute('data-speed')));
      }});
    }});
  </script>
</body>
</html>'''

        vehicle_path = os.path.join(output_dir, f"vehicle_{safe_plate}.html")
        with open(vehicle_path, "w", encoding="utf-8") as f:
            f.write(vehicle_html)
        generated_files.append(vehicle_path)

    print(f"Generated {len(generated_files)} HTML files in: {output_dir}")
    for f in generated_files:
        print(f"  → {os.path.basename(f)}")

    return generated_files
