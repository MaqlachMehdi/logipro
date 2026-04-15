import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import 'leaflet-polylinedecorator';

import type { Spot, Route } from '../types';

// ─── Types ────────────────────────────────────────────────────────────────────

interface Segment {
  coords: [[number, number], [number, number]];
  from: string;
  to: string;
  departure_time: number | null;
  arrival_time: number | null;
  distance_km: number | null;
  travel_time_min: number | null;
  transported_load: number | null;
  delta_at_departure: number;
  delta_at_arrival: number;
  step: number;
}

export interface VehicleRoute {
  plate: string;
  color: string;
  capacity: number;
  segments: Segment[];
}

export interface ConcertData {
  id: number;
  name: string;
  address: string;
  concert_start: number;
  concert_end: number;
  concert_duration: number;
  setup_duration: number;
  teardown_duration: number;
  lat: number | null;
  lon: number | null;
}

interface LeafletMapProps {
  center?: [number, number];
  zoom?: number;
  spots?: Spot[];
  routes?: Route[];
  vehicleRoutes?: VehicleRoute[];
  concertsData?: ConcertData[];
  className?: string;
  onMapLoaded?: (map: L.Map) => void;
  filterPlate?: string | null;
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function formatTime(minutes: number): string {
  const h = Math.floor(minutes / 60);
  const m = Math.round(minutes % 60);
  return `${String(h).padStart(2, '0')}h${String(m).padStart(2, '0')}`;
}

interface WavyStyle {
  offset: number;
  curv: number;
  freq: number;
  amp: number;
  phase: number;
}

function randomEdgeStyle(): WavyStyle {
  return {
    offset: (Math.random() - 0.5) * 0.002,
    curv: (Math.random() - 0.5) * 0.04,
    freq: 0.5 + Math.random() * 1.5,
    amp: 0.0001 + Math.random() * 0.0004,
    phase: Math.random() * 2 * Math.PI,
  };
}

function wavyPath(
  p1: [number, number],
  p2: [number, number],
  style: WavyStyle,
  nPts = 64,
): [number, number][] {
  const dLat = p2[0] - p1[0];
  const dLon = p2[1] - p1[1];
  const len = Math.sqrt(dLat * dLat + dLon * dLon);
  if (len < 1e-10) return [p1, p2];

  const perpLat = -dLon / len;
  const perpLon = dLat / len;

  const p1Off: [number, number] = [p1[0] + perpLat * style.offset, p1[1] + perpLon * style.offset];
  const p2Off: [number, number] = [p2[0] + perpLat * style.offset, p2[1] + perpLon * style.offset];
  const midLat = (p1Off[0] + p2Off[0]) / 2 + perpLat * style.curv;
  const midLon = (p1Off[1] + p2Off[1]) / 2 + perpLon * style.curv;

  const pts: [number, number][] = [];
  for (let i = 0; i <= nPts; i++) {
    const t = i / nPts;
    const s = 1 - t;
    const baseLat = s * s * p1Off[0] + 2 * s * t * midLat + t * t * p2Off[0];
    const baseLon = s * s * p1Off[1] + 2 * s * t * midLon + t * t * p2Off[1];
    const envelope = Math.sin(Math.PI * t);
    const wave = style.amp * envelope * Math.sin(style.freq * t * 2 * Math.PI + style.phase);
    pts.push([baseLat + perpLat * wave, baseLon + perpLon * wave]);
  }
  return pts;
}

// Pre-compute wavy paths for each segment (stable per mount)
interface PrecomputedSegment {
  pts: [number, number][];
  startTime: number;
  endTime: number;
  color: string;
  from: string;
  to: string;
  fromCoords: [number, number];
  toCoords: [number, number];
}

function precompute(vehicleRoutes: VehicleRoute[], geometries: Record<string, [number, number][]>): Record<string, PrecomputedSegment[]> {
  const result: Record<string, PrecomputedSegment[]> = {};
  for (const route of vehicleRoutes) {
    result[route.plate] = route.segments.map((seg, i) => {
      const roadPts = geometries[`${route.plate}:${i}`];
      const pts = roadPts ?? wavyPath(seg.coords[0], seg.coords[1], randomEdgeStyle(), 64);
      return {
        pts,
        startTime: seg.departure_time ?? 480,
        endTime: seg.arrival_time ?? (seg.departure_time ?? 480) + 30,
        color: route.color,
        from: seg.from,
        to: seg.to,
        fromCoords: seg.coords[0],
        toCoords: seg.coords[1],
      };
    });
  }
  return result;
}

// ─── Component ────────────────────────────────────────────────────────────────

export const LeafletMap: React.FC<LeafletMapProps> = ({
  center = [48.8566, 2.3522],
  zoom = 11,
  spots = [],
  routes = [],
  vehicleRoutes,
  concertsData,
  className,
  onMapLoaded,
  filterPlate,
}) => {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<L.Map | null>(null);
  const markersRef = useRef<L.LayerGroup | null>(null);
  const routesRef = useRef<L.LayerGroup | null>(null);
  // Animation layers
  const animLayersRef = useRef<L.Layer[]>([]);
  const segmentDataRef = useRef<Record<string, PrecomputedSegment[]>>({});
  const rafRef = useRef<number | null>(null);
  const lastFrameRef = useRef<number>(0);
  const roadGeometriesRef = useRef<Record<string, [number, number][]>>({});
  const [geomVersion, setGeomVersion] = useState(0);

  const hasVehicleRoutes = vehicleRoutes && vehicleRoutes.length > 0;

  // UI state
  const [mode, setMode] = useState<'static' | 'dynamic'>('static');
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(480);
  const [speed, setSpeed] = useState(1);
  const SPEED_OPTIONS = [0.5, 1, 2, 5];
  const START_TIME = 480;
  const END_TIME = 1380;

  // ── Map init ────────────────────────────────────────────────────────────────
  useEffect(() => {
    if (!containerRef.current) return;
    if (mapRef.current) return;

    const map = L.map(containerRef.current, { preferCanvas: true }).setView(
      [center[0], center[1]],
      zoom,
    );

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; OpenStreetMap contributors',
    }).addTo(map);

    markersRef.current = L.layerGroup().addTo(map);
    routesRef.current = L.layerGroup().addTo(map);
    mapRef.current = map;
    if (onMapLoaded) onMapLoaded(map);

    return () => {
      try { map.remove(); } catch (_) {}
      mapRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── Spots markers ───────────────────────────────────────────────────────────
  useEffect(() => {
    const map = mapRef.current;
    const markers = markersRef.current;
    if (!map || !markers) return;

    markers.clearLayers();

    for (const s of spots) {
      if (typeof s.lat !== 'number' || typeof s.lon !== 'number') continue;
      const isDepot = s.id === 'depot-permanent';
      const icon = L.divIcon({
        className: isDepot ? 'vehicle-marker' : 'concert-marker',
        iconSize: isDepot ? [28, 28] : [12, 12],
      });
      const m = L.marker([s.lat, s.lon], { icon });
      const popup = `<strong>${s.name}</strong><br/>${s.address || ''}<br/>${s.concertTime || ''} ${s.concertDuration ? `(${s.concertDuration} min)` : ''}`;
      m.bindPopup(popup);
      markers.addLayer(m);
    }

    if (!hasVehicleRoutes) {
      const coords = spots
        .filter((s) => typeof s.lat === 'number' && typeof s.lon === 'number')
        .map((s) => [s.lat, s.lon] as [number, number]);
      try {
        if (coords.length >= 2) map.fitBounds(coords as L.LatLngExpression[], { padding: [40, 40] });
        else if (coords.length === 1) map.setView(coords[0], Math.max(map.getZoom(), 12));
      } catch (_) {}
    }
  }, [spots, hasVehicleRoutes]);

  // ── Basic routes (when no vehicleRoutes) ────────────────────────────────────
  useEffect(() => {
    const map = mapRef.current;
    const routesLayer = routesRef.current;
    if (!map || !routesLayer || hasVehicleRoutes) return;

    routesLayer.clearLayers();

    for (const r of routes) {
      const latlngs: L.LatLngExpression[] = [];
      for (const stop of r.stops) {
        if (typeof (stop as any).lat === 'number' && typeof (stop as any).lon === 'number') {
          latlngs.push([(stop as any).lat, (stop as any).lon]);
        }
      }
      if (latlngs.length < 2) continue;

      const poly = L.polyline(latlngs, { color: '#60a5fa', weight: 4, opacity: 0.9 }).addTo(routesLayer);
      try {
        // @ts-ignore
        if (L.polylineDecorator) {
          // @ts-ignore
          L.polylineDecorator(poly, {
            patterns: [{ offset: 12, repeat: 40, symbol: L.Symbol.arrowHead({ pixelSize: 8, polygon: false, pathOptions: { stroke: true, color: '#60a5fa' } }) }],
          }).addTo(routesLayer);
        }
      } catch (_) {}
      poly.bindTooltip(`${r.vehicleId} — ${r.totalDistance ?? ''} km`, { className: 'route-tooltip' });
    }
  }, [routes, hasVehicleRoutes]);

  // ── Pre-compute wavy paths when vehicleRoutes arrive ───────────────────────
  useEffect(() => {
    if (!vehicleRoutes) return;
    segmentDataRef.current = precompute(vehicleRoutes, roadGeometriesRef.current);
  }, [vehicleRoutes]);

  // ── Fetch real road geometry from OSRM for each segment ───────────────────
  useEffect(() => {
    if (!vehicleRoutes || vehicleRoutes.length === 0) return;

    roadGeometriesRef.current = {};
    const controller = new AbortController();

    const fetches = vehicleRoutes.flatMap((route) =>
      route.segments.map((seg, i) => {
        const [lat1, lon1] = seg.coords[0];
        const [lat2, lon2] = seg.coords[1];
        const url = `https://router.project-osrm.org/route/v1/driving/${lon1},${lat1};${lon2},${lat2}?overview=full&geometries=geojson`;
        return fetch(url, { signal: controller.signal })
          .then((r) => r.json())
          .then((data: any) => {
            const coords = data?.routes?.[0]?.geometry?.coordinates;
            if (coords) {
              // GeoJSON is [lon, lat] — flip to [lat, lon] for Leaflet
              roadGeometriesRef.current[`${route.plate}:${i}`] = coords.map(
                ([lon, lat]: [number, number]) => [lat, lon] as [number, number],
              );
            }
          })
          .catch(() => {}); // silently fall back to wavy arc
      }),
    );

    Promise.all(fetches).then(() => {
      setGeomVersion((v) => v + 1);
    });

    return () => controller.abort();
  }, [vehicleRoutes]);

  // ── Clear animation layers helper ──────────────────────────────────────────
  const clearAnimLayers = useCallback(() => {
    const map = mapRef.current;
    if (!map) return;
    for (const l of animLayersRef.current) {
      try { map.removeLayer(l); } catch (_) {}
    }
    animLayersRef.current = [];
  }, []);

  const addAnimLayer = useCallback((layer: L.Layer) => {
    const map = mapRef.current;
    if (!map) return;
    layer.addTo(map);
    animLayersRef.current.push(layer);
  }, []);

  // ── Draw static routes ─────────────────────────────────────────────────────
  const drawStatic = useCallback(() => {
    if (!vehicleRoutes) return;
    const map = mapRef.current;
    if (!map) return;

    clearAnimLayers();
    const bounds: [number, number][] = [];

    const routesToDraw = filterPlate
      ? vehicleRoutes.filter((r) => r.plate === filterPlate)
      : vehicleRoutes;

    for (const route of routesToDraw) {
      for (let segIdx = 0; segIdx < route.segments.length; segIdx++) {
        const seg = route.segments[segIdx];
        const roadPts = roadGeometriesRef.current[`${route.plate}:${segIdx}`];
        const pts = roadPts ?? wavyPath(seg.coords[0], seg.coords[1], randomEdgeStyle(), 64);
        bounds.push(seg.coords[0], seg.coords[1]);

        const tooltipHtml = `<div style="min-width:180px"><b style="color:${route.color}">${route.plate}</b> Étape ${seg.step}<hr/><b>De:</b> ${seg.from}<br/><b>À:</b> ${seg.to}<hr/><b>Départ:</b> ${seg.departure_time != null ? formatTime(seg.departure_time) : '—'}<br/><b>Arrivée:</b> ${seg.arrival_time != null ? formatTime(seg.arrival_time) : '—'}</div>`;

        const poly = L.polyline(pts, { color: route.color, weight: roadPts ? 5 : 6, opacity: 0.85 });
        poly.bindTooltip(tooltipHtml, { sticky: true, className: 'route-tooltip' });
        addAnimLayer(poly);

        try {
          // @ts-ignore
          if (L.polylineDecorator) {
            // @ts-ignore
            const dec = L.polylineDecorator(poly, {
              patterns: [{ offset: '50%', repeat: 0, symbol: L.Symbol.arrowHead({ pixelSize: 14, polygon: false, pathOptions: { stroke: true, color: route.color, weight: 3, opacity: 1 } }) }],
            });
            addAnimLayer(dec);
          }
        } catch (_) {}
      }
    }

    if (bounds.length > 0) {
      try { map.fitBounds(bounds, { padding: [30, 30] }); } catch (_) {}
    }
  }, [vehicleRoutes, filterPlate, clearAnimLayers, addAnimLayer]);

  // ── Render one animation frame ─────────────────────────────────────────────
  const renderFrame = useCallback((time: number) => {
    if (!vehicleRoutes) return;
    clearAnimLayers();

    const segData = segmentDataRef.current;
    const routesToAnimate = filterPlate
      ? vehicleRoutes.filter((r) => r.plate === filterPlate)
      : vehicleRoutes;

    for (const route of routesToAnimate) {
      const segments = segData[route.plate] || [];

      for (const seg of segments) {
        if (time >= seg.endTime) {
          // fully done
          const poly = L.polyline(seg.pts, { color: seg.color, weight: 6, opacity: 0.9 });
          addAnimLayer(poly);
          try {
            // @ts-ignore
            if (L.polylineDecorator) {
              // @ts-ignore
              const dec = L.polylineDecorator(poly, { patterns: [{ offset: '50%', repeat: 0, symbol: L.Symbol.arrowHead({ pixelSize: 14, polygon: false, pathOptions: { stroke: true, color: seg.color, weight: 3, opacity: 1 } }) }] });
              addAnimLayer(dec);
            }
          } catch (_) {}
        } else if (time >= seg.startTime && time < seg.endTime) {
          const progress = (time - seg.startTime) / (seg.endTime - seg.startTime);
          const ptIdx = Math.floor(progress * (seg.pts.length - 1));
          const partialPts = seg.pts.slice(0, ptIdx + 1);
          if (partialPts.length > 1) {
            addAnimLayer(L.polyline(partialPts, { color: seg.color, weight: 6, opacity: 0.9 }));
          }
        }
      }

      // Vehicle emoji marker
      const state = getVehicleState(segments, time);
      if (state) {
        const emoji = state.status === 'waiting' ? '🛏️' : state.status === 'working' ? '🔨' : '🚚';
        const icon = L.divIcon({
          className: 'vehicle-emoji-marker',
          html: `<div style="font-size:26px;transform:translate(-50%,-50%);filter:drop-shadow(0 2px 4px rgba(0,0,0,.3))">${emoji}</div>`,
          iconSize: [40, 40],
          iconAnchor: [20, 20],
        });
        addAnimLayer(L.marker(state.position, { icon, zIndexOffset: 1000 }));
      }
    }

    // Disco balls
    if (concertsData) {
      for (const concert of concertsData) {
        if (!concert.lat || !concert.lon) continue;
        if (time >= concert.concert_start && time < concert.concert_end) {
          const pulse = Math.sin((time - concert.concert_start) * 0.5) * 0.2 + 1;
          const discoIcon = L.divIcon({
            className: 'disco-marker',
            html: `<div class="disco-ball" style="font-size:${Math.round(24 * pulse)}px;animation:disco-spin 0.5s linear infinite;">🪩</div>`,
            iconSize: [40, 40],
            iconAnchor: [20, 20],
          });
          addAnimLayer(L.marker([concert.lat, concert.lon], { icon: discoIcon, zIndexOffset: 900 }));

          for (let i = 0; i < 3; i++) {
            const angle = ((time * 10) + i * 120) * Math.PI / 180;
            const radius = 0.0003 + Math.sin(time * 0.3 + i) * 0.0001;
            const sparklePos: [number, number] = [concert.lat + Math.cos(angle) * radius, concert.lon + Math.sin(angle) * radius];
            const sparkleIcon = L.divIcon({
              className: 'sparkle-marker',
              html: `<div style="font-size:14px;opacity:${(0.5 + Math.sin(time + i) * 0.3).toFixed(2)}">✨</div>`,
              iconSize: [20, 20],
              iconAnchor: [10, 10],
            });
            addAnimLayer(L.marker(sparklePos, { icon: sparkleIcon, zIndexOffset: 800 }));
          }
        }
      }
    }
  }, [vehicleRoutes, filterPlate, concertsData, clearAnimLayers, addAnimLayer]);

  // ── Init static when vehicleRoutes become available ────────────────────────
  useEffect(() => {
    if (!hasVehicleRoutes) return;
    if (mode === 'static') drawStatic();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [vehicleRoutes]);

  // ── Redraw with real road geometry once OSRM fetches complete ──────────────
  useEffect(() => {
    if (geomVersion === 0 || !vehicleRoutes) return;
    segmentDataRef.current = precompute(vehicleRoutes, roadGeometriesRef.current);
    if (mode === 'static') drawStatic();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [geomVersion]);

  // ── Redraw when filter changes ─────────────────────────────────────────────
  useEffect(() => {
    if (!hasVehicleRoutes) return;
    if (mode === 'static') drawStatic();
    else renderFrame(currentTimeRef.current);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filterPlate]);

  // ── Mode switch ─────────────────────────────────────────────────────────────
  const handleModeStatic = useCallback(() => {
    setMode('static');
    setIsPlaying(false);
    if (rafRef.current != null) { cancelAnimationFrame(rafRef.current); rafRef.current = null; }
    drawStatic();
  }, [drawStatic]);

  const handleModeDynamic = useCallback(() => {
    setMode('dynamic');
    setIsPlaying(false);
    if (rafRef.current != null) { cancelAnimationFrame(rafRef.current); rafRef.current = null; }
    setCurrentTime(START_TIME);
    renderFrame(START_TIME);
  }, [renderFrame]);

  // ── Animation loop ──────────────────────────────────────────────────────────
  const animateRef = useRef<(t: number) => void>(() => {});
  const speedRef = useRef(speed);
  const currentTimeRef = useRef(currentTime);
  const isPlayingRef = useRef(isPlaying);

  speedRef.current = speed;
  currentTimeRef.current = currentTime;
  isPlayingRef.current = isPlaying;

  animateRef.current = (now: number) => {
    if (!isPlayingRef.current) return;
    const delta = (now - lastFrameRef.current) / 1000;
    lastFrameRef.current = now;

    let newTime = currentTimeRef.current + delta * speedRef.current * 10;
    if (newTime >= END_TIME) newTime = START_TIME;

    currentTimeRef.current = newTime;
    setCurrentTime(newTime);
    renderFrame(newTime);

    rafRef.current = requestAnimationFrame((t) => animateRef.current!(t));
  };

  const startPlay = useCallback(() => {
    setIsPlaying(true);
    isPlayingRef.current = true;
    lastFrameRef.current = performance.now();
    rafRef.current = requestAnimationFrame((t) => animateRef.current!(t));
  }, []);

  const stopPlay = useCallback(() => {
    setIsPlaying(false);
    isPlayingRef.current = false;
    if (rafRef.current != null) { cancelAnimationFrame(rafRef.current); rafRef.current = null; }
  }, []);

  const handlePlayPause = useCallback(() => {
    if (isPlaying) stopPlay();
    else startPlay();
  }, [isPlaying, startPlay, stopPlay]);

  const handleSlider = useCallback((val: number) => {
    stopPlay();
    setCurrentTime(val);
    currentTimeRef.current = val;
    renderFrame(val);
  }, [stopPlay, renderFrame]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (rafRef.current != null) cancelAnimationFrame(rafRef.current);
    };
  }, []);

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%' }}>
      {/* Mode toggle — only shown if we have solver routes */}
      {hasVehicleRoutes && (
        <div style={{
          position: 'absolute', top: 8, right: 8, zIndex: 1000,
          display: 'flex', gap: 4, background: 'rgba(35,35,40,0.92)',
          borderRadius: 8, padding: 4, border: '1px solid #3a3a45',
        }}>
          <button
            onClick={handleModeStatic}
            style={{
              padding: '6px 14px', borderRadius: 6, border: 'none', cursor: 'pointer', fontSize: 12, fontWeight: 600,
              background: mode === 'static' ? '#60a5fa' : 'rgba(255,255,255,0.12)',
              color: mode === 'static' ? '#ffffff' : '#d1d5db',
            }}
          >Statique</button>
          <button
            onClick={handleModeDynamic}
            style={{
              padding: '6px 14px', borderRadius: 6, border: 'none', cursor: 'pointer', fontSize: 12, fontWeight: 600,
              background: mode === 'dynamic' ? '#60a5fa' : 'rgba(255,255,255,0.12)',
              color: mode === 'dynamic' ? '#ffffff' : '#d1d5db',
            }}
          >Dynamique</button>
        </div>
      )}

      {/* Player controls — shown only in dynamic mode */}
      {hasVehicleRoutes && mode === 'dynamic' && (
        <div style={{
          position: 'absolute', bottom: 16, left: '50%', transform: 'translateX(-50%)',
          zIndex: 1000, background: 'rgba(35,35,40,0.95)', border: '1px solid #3a3a45',
          borderRadius: 12, padding: '12px 20px', display: 'flex', alignItems: 'center',
          gap: 12, minWidth: 420, boxShadow: '0 8px 32px rgba(0,0,0,.4)',
        }}>
          {/* Play/Pause */}
          <button
            onClick={handlePlayPause}
            style={{
              width: 40, height: 40, borderRadius: '50%', background: '#1d4ed8', border: 'none',
              color: 'white', fontSize: 16, cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center',
              flexShrink: 0,
            }}
          >{isPlaying ? '⏸' : '▶'}</button>

          {/* Time display */}
          <span style={{ fontFamily: 'monospace', fontSize: 20, fontWeight: 700, color: '#60a5fa', minWidth: 60, textAlign: 'center' }}>
            {formatTime(Math.round(currentTime))}
          </span>

          {/* Slider */}
          <input
            type="range" min={START_TIME} max={END_TIME} value={Math.round(currentTime)}
            onChange={(e) => handleSlider(Number(e.target.value))}
            style={{ flex: 1, accentColor: '#60a5fa', cursor: 'pointer' }}
          />

          {/* Speed buttons */}
          <div style={{ display: 'flex', gap: 4 }}>
            {SPEED_OPTIONS.map((s) => (
              <button
                key={s}
                onClick={() => setSpeed(s)}
                style={{
                  padding: '4px 8px', borderRadius: 6, fontSize: 11, fontWeight: 600, cursor: 'pointer', border: 'none',
                  background: speed === s ? '#60a5fa' : '#2d2d35',
                  color: speed === s ? 'white' : '#a0a0a8',
                }}
              >{s}x</button>
            ))}
          </div>
        </div>
      )}

      <div
        ref={containerRef}
        className={className || 'map-container'}
        style={{ width: '100%', height: '100%' }}
      />
    </div>
  );
};

// ── Vehicle state helper ───────────────────────────────────────────────────────

function getVehicleState(
  segments: PrecomputedSegment[],
  time: number,
): { status: 'moving' | 'working' | 'waiting'; position: [number, number]; color?: string } | null {
  if (!segments.length) return null;

  if (time < segments[0].startTime) {
    return { status: 'waiting', position: segments[0].fromCoords };
  }

  for (let i = 0; i < segments.length; i++) {
    const seg = segments[i];
    const next = segments[i + 1];

    if (time >= seg.startTime && time < seg.endTime) {
      const progress = (time - seg.startTime) / (seg.endTime - seg.startTime);
      const ptIdx = Math.floor(progress * (seg.pts.length - 1));
      const t2 = (progress * (seg.pts.length - 1)) % 1;
      let pos: [number, number];
      if (ptIdx < seg.pts.length - 1) {
        pos = [
          seg.pts[ptIdx][0] + t2 * (seg.pts[ptIdx + 1][0] - seg.pts[ptIdx][0]),
          seg.pts[ptIdx][1] + t2 * (seg.pts[ptIdx + 1][1] - seg.pts[ptIdx][1]),
        ];
      } else {
        pos = seg.pts[seg.pts.length - 1];
      }
      return { status: 'moving', position: pos, color: seg.color };
    }

    if (next) {
      if (time >= seg.endTime && time < next.startTime) {
        return { status: 'working', position: seg.toCoords, color: seg.color };
      }
    } else if (time >= seg.endTime) {
      return { status: 'working', position: seg.toCoords, color: seg.color };
    }
  }

  const last = segments[segments.length - 1];
  return { status: 'waiting', position: last.toCoords, color: last.color };
}

export default LeafletMap;
