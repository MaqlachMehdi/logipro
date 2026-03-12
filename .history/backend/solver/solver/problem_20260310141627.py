from dataclasses import dataclass
from models.graph import DepositNode, DeliveryNode, Node, OrientedEdges, RecoveryNode, TimeWindow


@dataclass
class LossParams:
    alpha_time:     float
    alpha_distance: float

@dataclass
class TimeMargin:
    before_concert: int
    after_concert:  int
    before_closing: int

@dataclass
class Problem:
    name:            str
    deposit_node:    DepositNode
    delivery_nodes:  list[DeliveryNode]
    recovery_nodes:  list[RecoveryNode]
    oriented_edges:  OrientedEdges
    vehicles_dict:   dict          # plate -> Vehicle
    loss_params:     LossParams
    time_margin:    TimeMargin

    def health_check(self):
        if len(self.delivery_nodes) != len(self.recovery_nodes):
            raise ValueError("Mismatch between delivery and recovery node counts.")
        for d, r in zip(self.delivery_nodes, self.recovery_nodes):
            if not isinstance(d, DeliveryNode):
                raise TypeError(f"Expected DeliveryNode, got {type(d)}")
            if not isinstance(r, RecoveryNode):
                raise TypeError(f"Expected RecoveryNode, got {type(r)}")

    def __post_init__(self):
        self.number_of_locations = len(self.delivery_nodes)

        self._pulp_id_to_node = dict()

        for node in self.all_nodes:
            self._pulp_id_to_node[node.get_id_for_pulp()] = node

        self.health_check()

    def access_node_by_pulp_id(self, pulp_id: str) -> Node:
        if pulp_id not in self._pulp_id_to_node:
            raise KeyError(f"No node found for pulp_id: {pulp_id}")
        return self._pulp_id_to_node[pulp_id]

    @property
    def n_of_nodes(self) -> int:
        return 2 * self.number_of_locations + 1

    @property
    def all_nodes(self) -> list:
        return [self.deposit_node] + self.delivery_nodes + self.recovery_nodes

    def __str__(self) -> str:
        def hhmm(m: int) -> str:
            return f"{int(m)//60:02d}h{int(m)%60:02d}"

        sep  = "─" * 60
        lines = [
            sep,
            f"  PROBLEM : {self.name}",
            f"  Loss    : α_time={self.loss_params.alpha_time}  α_dist={self.loss_params.alpha_distance}",
            f"  Nodes   : {self.n_of_nodes}  ({self.number_of_locations} venues × 2 + depot)",
            f"  Vehicles: {len(self.vehicles_dict)}",
            sep,
        ]

        # ── Depot ──────────────────────────────────────────────────────────
        d = self.deposit_node
        tw = d.time_window
        lines += [
            "DEPOT",
            f"  id={d.id}  GPS={d.gps_coordinates}",
            f"  TW : [{tw.start_minutes}, {tw.end_minutes}]  "
            f"({hhmm(tw.start_minutes)} – {hhmm(tw.end_minutes)})" if tw else "  TW : None",
        ]

        # ── Delivery nodes ─────────────────────────────────────────────────
        lines += ["", "DELIVERY NODES (drop-off before concert)"]
        for node in self.delivery_nodes:
            tw  = node.time_window
            tw_s = (f"[{tw.start_minutes}, {tw.end_minutes}]  "
                    f"({hhmm(tw.start_minutes)} – {hhmm(tw.end_minutes)})"
                    if tw else "None")
            lines.append(
                f"  DeliveryNode id={node.id:>3}  "
                f"vol={node.required_volume:+.3f} m³  "
                f"GPS={node.gps_coordinates}  TW={tw_s}"
            )

        # ── Recovery nodes ─────────────────────────────────────────────────
        lines += ["", "RECOVERY NODES (pick-up after concert)"]
        for node in self.recovery_nodes:
            tw  = node.time_window
            tw_s = (f"[{tw.start_minutes}, {tw.end_minutes}]  "
                    f"({hhmm(tw.start_minutes)} – {hhmm(tw.end_minutes)})"
                    if tw else "None")
            lines.append(
                f"  RecoveryNode id={node.id:>3}  "
                f"vol={node.required_volume:+.3f} m³  "
                f"GPS={node.gps_coordinates}  TW={tw_s}"
            )

        # ── Vehicles ───────────────────────────────────────────────────────
        lines += ["", "VEHICLES"]
        for v in self.vehicles_dict.values():
            lines.append(f"  {v}")

        # ── Node-ID uniqueness check (critical for choose_edges keys) ──────
        lines += ["", "NODE-ID UNIQUENESS CHECK"]
        from collections import Counter
        id_counts = Counter(n.id for n in self.all_nodes)
        duplicates = {i: c for i, c in id_counts.items() if c > 1}
        if duplicates:
            lines.append("  *** WARNING: duplicate node IDs detected! ***")
            lines.append("  Delivery and Recovery nodes sharing the same id will")
            lines.append("  collapse to the SAME choose_edges variable — constraints")
            lines.append("  will reference the wrong edges.")
            for nid, count in duplicates.items():
                node_objs = [type(n).__name__ for n in self.all_nodes if n.id == nid]
                lines.append(f"    id={nid}  appears {count}× → {node_objs}")
        else:
            lines.append("  OK — all node IDs are unique")

        # ── Oriented edges summary ─────────────────────────────────────────
        lines += ["", "ORIENTED EDGES (distance km / travel time min)"]
        all_ids = sorted(set(i for i, _ in self.oriented_edges.distances_km))
        for i in all_ids:
            for j in all_ids:
                key = (i, j)
                if key in self.oriented_edges.distances_km:
                    d_km = self.oriented_edges.distances_km[key]
                    t_min = self.oriented_edges.travel_times_min.get(key, float("nan"))
                    lines.append(
                        f"  ({i:>3} → {j:>3})  {d_km:6.2f} km  {t_min:5.1f} min"
                    )

        # ── Time-window feasibility check ──────────────────────────────────
        lines += ["", "TIME-WINDOW FEASIBILITY"]
        for d_node, r_node in zip(self.delivery_nodes, self.recovery_nodes):
            d_tw = d_node.time_window
            r_tw = r_node.time_window
            ok_d = d_tw and d_tw.end_minutes > d_tw.start_minutes
            ok_r = r_tw and r_tw.end_minutes > r_tw.start_minutes
            lines.append(
                f"  venue id={d_node.id}  "
                f"delivery=[{d_tw.start_minutes},{d_tw.end_minutes}] {'OK' if ok_d else '*** INVALID ***'}  "
                f"recovery=[{r_tw.start_minutes},{r_tw.end_minutes}] {'OK' if ok_r else '*** INVALID ***'}"
            )

        # ── Volume vs vehicle capacity ─────────────────────────────────────
        lines += ["", "VOLUME vs VEHICLE CAPACITY"]
        total_vol = sum(
            abs(n.required_volume)
            for n in self.delivery_nodes
            if n.required_volume is not None
        )
        max_cap   = max(v.max_volume for v in self.vehicles_dict.values())
        total_cap = sum(v.max_volume for v in self.vehicles_dict.values())
        lines.append(f"  Total instrument volume : {total_vol:.3f} m³")
        lines.append(f"  Largest vehicle cap     : {max_cap:.1f} m³")
        lines.append(f"  Combined fleet cap      : {total_cap:.1f} m³")
        if total_vol > total_cap:
            lines.append("  *** WARNING: total volume exceeds fleet capacity — problem is infeasible ***")
        else:
            lines.append("  OK — fleet capacity sufficient")

        lines.append(sep)
        return "\n".join(lines)
    

# ──────────────────────────────────────────────────────────────────────────────
# Problem builder
# ──────────────────────────────────────────────────────────────────────────────

from models.graph import make_oriented_edges_cached
from models.vehicules import Vehicle

def _compute_location_volume(location: dict, vol_lookup: dict) -> float:
    """Sum the volume of all instruments listed for a location."""
    raw = location.get("instruments", "")
    items = [s.strip() for s in raw.split(",") if s.strip()]
    return sum(vol_lookup.get(item, 0.0) for item in items)


def build_problem(data: dict, loss_params: LossParams,time_margin:TimeMargin,recall_api:bool) -> Problem:
    """
    Build a Problem from a data dict matching the vrppd_data.json schema.

    Parameters
    ----------
    data        : dict loaded from vrppd_data.json
    loss_params : optional
    """


    # --- instrument volume lookup -------------------------------------------
    vol_lookup = {
        inst["name"]: inst["volume_m3"]
        for inst in data["instrument_catalog"]
    }

    # --- split depot vs. venue locations ------------------------------------
    depot_data = next(loc for loc in data["locations"] if loc["id"] == 0)
    venue_data = [loc for loc in data["locations"] if loc["id"] != 0]
    venue_ids  = [loc["id"] for loc in venue_data]

    # --- depot node ---------------------------------------------------------
    deposit_node = DepositNode(depot_data["id"])
    deposit_node.gps_coordinates = (depot_data["lat"], depot_data["lon"])
    deposit_node.time_window = TimeWindow(
        start_minutes=depot_data["open_time_min"],
        end_minutes=depot_data["close_time_min"],
    )

    # --- delivery + recovery nodes ------------------------------------------
    delivery_nodes = [DeliveryNode(vid) for vid in venue_ids]
    recovery_nodes = [RecoveryNode(vid) for vid in venue_ids]

    for loc, delivery_node, recovery_node in zip(venue_data, delivery_nodes, recovery_nodes):
        assert delivery_node.id == recovery_node.id == loc["id"]

        venue_volume = _compute_location_volume(loc, vol_lookup)
        delivery_node.required_volume = +venue_volume
        recovery_node.required_volume = -venue_volume

        concert_start  = loc["concert_start_min"]
        open_time      = loc["open_time_min"]
        close_time     = loc["close_time_min"]
        setup_time     = loc["setup_duration_min"]
        teardown_time  = loc["teardown_duration_min"]
        concert_dur    = loc["concert_duration_min"]
        coords         = (loc["lat"], loc["lon"])

        delivery_node.required_time = setup_time
        recovery_node.required_time = teardown_time

        delivery_node.time_window = TimeWindow(
            start_minutes=open_time,
            end_minutes=concert_start - setup_time - time_margin.before_concert,
        )
        recovery_node.time_window = TimeWindow(
            start_minutes=concert_start + concert_dur + time_margin.after_concert,
            end_minutes=close_time - teardown_time - time_margin.before_closing,
        )

        delivery_node.gps_coordinates = coords
        recovery_node.gps_coordinates = coords

        delivery_node.health_check()
        recovery_node.health_check()

    # --- oriented edges (with caching) --------------------------------------
    oriented_edges = make_oriented_edges_cached(recovery_nodes, delivery_nodes, deposit_node,recall_api)

    # --- vehicles -----------------------------------------------------------
    vehicles_dict: dict[str, Vehicle] = {}
    for v in data["vehicles"]:
        vehicles_dict[v["plate"]] = Vehicle(id=v["plate"], max_volume=v["capacity_m3"])

    return Problem(
        name="VRPPD Concerts",
        deposit_node=deposit_node,
        delivery_nodes=delivery_nodes,
        recovery_nodes=recovery_nodes,
        oriented_edges=oriented_edges,
        vehicles_dict=vehicles_dict,
        loss_params=loss_params,
        time_margin=time_margin,
    )