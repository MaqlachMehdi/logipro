import { useReducer } from 'react';
import { VolumeEstimator, FleetManager, RouteSummary, MapPlanner, ExportPanel, SpotManager, VehicleDetail, ExportDatabase } from './components';
import { solveVRPTW } from './utils/vrptw-solver';
import type { Spot, Vehicle, Route, AppState } from './types';
import { Truck, AlertCircle, Zap } from 'lucide-react';
import { Button } from './components/ui';
import { GEAR_CATALOG } from './utils/volume-data';

type AppAction =
  | { type: 'SET_SPOTS'; payload: Spot[] }
  | { type: 'SELECT_SPOT'; payload: string | null }
  | { type: 'UPDATE_SPOT_GEAR'; payload: { spotId: string; gear: any[] } }
  | { type: 'ADD_SPOT'; payload: Omit<Spot, 'id' | 'gearSelections'> }
  | { type: 'DELETE_SPOT'; payload: string }
  | { type: 'SET_VEHICLES'; payload: Vehicle[] }
  | { type: 'SET_ROUTES'; payload: Route[] }
  | { type: 'TOGGLE_LOAD_IN' }
  | { type: 'TOGGLE_LOAD_OUT' }
  | { type: 'SELECT_VEHICLE'; payload: string | null };

const SPOTS_STORAGE_KEY = 'regietour_spots';
const LEGACY_SPOTS_STORAGE_KEYS = ['logipro_spots', 'regietour_venues'];

function normalizeTime(value: unknown, fallback: string): string {
  if (typeof value !== 'string') return fallback;
  const isValid = /^\d{2}:\d{2}$/.test(value);
  return isValid ? value : fallback;
}

function normalizeSpots(raw: unknown): Spot[] {
  if (!Array.isArray(raw)) return [];

  return raw
    .map((item, index) => {
      if (!item || typeof item !== 'object') return null;

      const candidate = item as Partial<Spot> & {
        loadInWindow?: [string, string];
        loadOutWindow?: [string, string];
      };

      const id = typeof candidate.id === 'string' && candidate.id.trim().length > 0
        ? candidate.id
        : `spot-legacy-${index}`;

      const name = typeof candidate.name === 'string' && candidate.name.trim().length > 0
        ? candidate.name
        : `Lieu ${index + 1}`;

      const address = typeof candidate.address === 'string' ? candidate.address : '';
      const lat = typeof candidate.lat === 'number' ? candidate.lat : 48.8566;
      const lon = typeof candidate.lon === 'number' ? candidate.lon : 2.3522;
      const openingTime = normalizeTime(candidate.openingTime ?? candidate.loadInWindow?.[0], '08:00');
      const closingTime = normalizeTime(candidate.closingTime ?? candidate.loadOutWindow?.[1], '23:00');
      const concertTime = normalizeTime(candidate.concertTime ?? candidate.loadOutWindow?.[0], '20:00');

      const gearSelections = Array.isArray(candidate.gearSelections)
        ? candidate.gearSelections
            .filter((sel) => sel && typeof sel.gearId === 'string' && typeof sel.quantity === 'number' && sel.quantity > 0)
            .map((sel) => ({ gearId: sel.gearId, quantity: sel.quantity }))
        : [];

      return {
        id,
        name,
        address,
        lat,
        lon,
        openingTime,
        closingTime,
        concertTime,
        gearSelections,
      } satisfies Spot;
    })
    .filter((spot): spot is Spot => spot !== null);
}

/* --------------------- STATE --------------------- */
const createInitialState = (): AppState => {
  const legacyPayload = LEGACY_SPOTS_STORAGE_KEYS
    .map((key) => localStorage.getItem(key))
    .find((value) => value !== null);

  const rawPayload = localStorage.getItem(SPOTS_STORAGE_KEY) ?? legacyPayload;

  let spots: Spot[] = [];
  if (rawPayload) {
    try {
      spots = normalizeSpots(JSON.parse(rawPayload));
    } catch {
      spots = [];
    }
  }

  localStorage.setItem(SPOTS_STORAGE_KEY, JSON.stringify(spots));

  return {
    spots,
    selectedSpotId: spots.length > 0 ? spots[0].id : null,
    vehicles: [
      { id: 'v-1', name: 'AA-123-BB', type: 'van', capacity: 20, color: 'indigo-500' },
      { id: 'v-2', name: 'CC-456-DD', type: 'van', capacity: 20, color: 'emerald-500' },
      { id: 'v-3', name: 'TR-789-XX', type: 'truck', capacity: 40, color: 'amber-500' },
    ],
    routes: [],
    showLoadIn: true,
    showLoadOut: true,
    selectedVehicleId: null,
  };
};

/* --------------------- REDUCER --------------------- */
function appReducer(state: AppState, action: AppAction): AppState {
  switch (action.type) {
    case 'SET_SPOTS':
      localStorage.setItem(SPOTS_STORAGE_KEY, JSON.stringify(action.payload));
      return {
        ...state,
        spots: action.payload,
        selectedSpotId:
          action.payload.find((spot) => spot.id === state.selectedSpotId)?.id ?? action.payload[0]?.id ?? null,
      };

    case 'SELECT_SPOT':
      return { ...state, selectedSpotId: action.payload };

    case 'UPDATE_SPOT_GEAR':
      const updatedSpots = state.spots.map((spot) =>
        spot.id === action.payload.spotId ? { ...spot, gearSelections: action.payload.gear } : spot,
      );
      localStorage.setItem(SPOTS_STORAGE_KEY, JSON.stringify(updatedSpots));
      return { ...state, spots: updatedSpots };

    case 'ADD_SPOT':
      const newSpot: Spot = {
        id: `spot-${Date.now()}`,
        ...action.payload,
        gearSelections: [],
      };
      const newSpots = [...state.spots, newSpot];
      localStorage.setItem(SPOTS_STORAGE_KEY, JSON.stringify(newSpots));
      return { ...state, spots: newSpots, selectedSpotId: newSpot.id };

    case 'DELETE_SPOT':
      const filteredSpots = state.spots.filter((s) => s.id !== action.payload);
      localStorage.setItem(SPOTS_STORAGE_KEY, JSON.stringify(filteredSpots));
      return {
        ...state,
        spots: filteredSpots,
        selectedSpotId:
          state.selectedSpotId === action.payload
            ? filteredSpots[0]?.id ?? null
            : state.selectedSpotId,
      };

    case 'SET_VEHICLES':
      return { ...state, vehicles: action.payload };

    case 'SET_ROUTES':
      return { ...state, routes: action.payload };

    case 'TOGGLE_LOAD_IN':
      return { ...state, showLoadIn: !state.showLoadIn };

    case 'TOGGLE_LOAD_OUT':
      return { ...state, showLoadOut: !state.showLoadOut };

    case 'SELECT_VEHICLE':
      return { ...state, selectedVehicleId: action.payload };

    default:
      return state;
  }
}

/* --------------------- APP --------------------- */
export default function App() {
  const [state, dispatch] = useReducer(appReducer, undefined, createInitialState);

  const selectedSpot = state.spots.find((s) => s.id === state.selectedSpotId) ?? state.spots[0] ?? null;

  const totalVolume = state.spots.reduce((sum, spot) => {
    const spotVolume = spot.gearSelections.reduce((spotSum, sel) => {
      const gear = GEAR_CATALOG.find((g: any) => g.id === sel.gearId);
      return spotSum + (gear?.volume || 0) * sel.quantity;
    }, 0);
    return sum + spotVolume;
  }, 0);

  const handleOptimize = () => {
    const routes = solveVRPTW(state.vehicles, state.spots, state.showLoadIn, state.showLoadOut);
    dispatch({ type: 'SET_ROUTES', payload: routes });
  };

  return (
    /* 1️⃣  <-- Ajout de overflow-x-hidden pour stopper tout débordement horizontal */
    <div className="flex flex-col min-h-screen bg-gray-50 text-gray-900 overflow-x-hidden">
      {/* ===== Header ===== */}
      <header className="sticky top-0 z-50 bg-white border-b border-gray-200 px-6 py-3 shadow-sm">
        {/* 2️⃣  <-- max‑w‑7xl remplacé par max‑w‑full pour occuper toute la largeur */}
        <div className="max-w-full mx-auto">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Truck className="w-8 h-8 text-blue-600 flex-shrink-0" />
              <div>
                <h1 className="text-2xl font-bold text-gray-900">RegieTour</h1>
                <p className="text-xs text-gray-600">Optimisateur de tournées événementielles</p>
              </div>
            </div>
            <div className="text-right">
              <div className="text-2xl font-bold text-blue-600">{totalVolume.toFixed(1)} m³</div>
              <div className="text-xs text-gray-600">Volume total</div>
            </div>
          </div>
        </div>
      </header>

      {/* ===== Main Content ===== */}
      <main className="flex-1 w-full bg-gray-50">
        {/* 3️⃣  <-- max‑w‑full au lieu de max‑w‑7xl */}
        <div className="max-w-full mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <div className="grid grid-cols-12 gap-6">
            {/* ── LEFT PANEL – Configuration ── */}
            <div className="col-span-12 lg:col-span-4 space-y-6">
              <SpotManager
                spots={state.spots}
                selectedSpotId={state.selectedSpotId ?? state.spots[0]?.id ?? null}
                onSelectSpot={(id) => dispatch({ type: 'SELECT_SPOT', payload: id })}
                onAddSpot={(spot) => dispatch({ type: 'ADD_SPOT', payload: spot })}
                onDeleteSpot={(id) => dispatch({ type: 'DELETE_SPOT', payload: id })}
              />

              {selectedSpot && (
                <VolumeEstimator
                  selections={selectedSpot.gearSelections}
                  onChange={(gear) =>
                    dispatch({ type: 'UPDATE_SPOT_GEAR', payload: { spotId: selectedSpot.id, gear } })
                  }
                  spotName={selectedSpot.name}
                />
              )}

              <FleetManager
                vehicles={state.vehicles}
                onChange={(vehicles) => dispatch({ type: 'SET_VEHICLES', payload: vehicles })}
              />
            </div>

            {/* ── CENTER PANEL – Map & Routes ── */}
            <div className="col-span-12 lg:col-span-5 space-y-6">
              <div className="space-y-3">
                <div className="flex gap-2">
                  <Button
                    size="sm"
                    className={`flex-1 ${
                      state.showLoadIn
                        ? 'bg-blue-600 hover:bg-blue-700 text-white'
                        : 'bg-gray-100 hover:bg-gray-200 text-gray-700 border border-gray-300'
                    }`}
                    onClick={() => dispatch({ type: 'TOGGLE_LOAD_IN' })}
                  >
                    {state.showLoadIn ? '✓' : ''} Load‑in
                  </Button>

                  <Button
                    size="sm"
                    className={`flex-1 ${
                      state.showLoadOut
                        ? 'bg-blue-600 hover:bg-blue-700 text-white'
                        : 'bg-gray-100 hover:bg-gray-200 text-gray-700 border border-gray-300'
                    }`}
                    onClick={() => dispatch({ type: 'TOGGLE_LOAD_OUT' })}
                  >
                    {state.showLoadOut ? '✓' : ''} Load‑out
                  </Button>

                  <Button
                    size="sm"
                    className="flex-1 bg-emerald-600 hover:bg-emerald-700 text-white"
                    onClick={handleOptimize}
                  >
                    <Zap className="w-4 h-4 mr-1" />
                    Optimiser
                  </Button>
                </div>
              </div>

              <MapPlanner
                routes={state.routes}
                vehicles={state.vehicles}
                spots={state.spots}
                selectedVehicleId={state.selectedVehicleId}
                showLoadIn={state.showLoadIn}
                showLoadOut={state.showLoadOut}
              />

              <RouteSummary
                routes={state.routes}
                vehicles={state.vehicles}
                selectedVehicleId={state.selectedVehicleId}
                onSelectVehicle={(id) => dispatch({ type: 'SELECT_VEHICLE', payload: id })}
              />
            </div>

            {/* ── RIGHT PANEL – Details & Export ── */}
            <div className="col-span-12 lg:col-span-3 space-y-6">
              <VehicleDetail
                routes={state.routes}
                vehicles={state.vehicles}
                spots={state.spots}
                selectedVehicleId={state.selectedVehicleId}
              />

              <ExportPanel routes={state.routes} vehicles={state.vehicles} spots={state.spots} />

              {state.spots.length > 0 && (
                <ExportDatabase
                  vehicles={state.vehicles}
                  venues={state.spots.map((s) => ({
                    ...s,
                    timeWindow: [8, 23] as [number, number],
                    demand: 0,
                    instruments: s.gearSelections
                      .map((sel) => {
                        const gear = GEAR_CATALOG.find((g) => g.id === sel.gearId);
                        if (!gear || sel.quantity <= 0) return null;
                        return `${gear.name} x${sel.quantity}`;
                      })
                      .filter((item): item is string => item !== null)
                      .join(', '),
                  }))}
                  gearCatalog={GEAR_CATALOG}
                  routes={state.routes.map((r) => ({
                    ...r,
                    totalVolume: r.totalVolume,
                  }))}
                />
              )}
            </div>
          </div>

          {/* ===== EMPTY STATE / WARNINGS ===== */}
          {state.spots.length === 0 && (
            <div className="col-span-1 md:col-span-2 lg:col-span-3 mt-6">
              <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg flex items-start gap-3">
                <AlertCircle className="w-5 h-5 text-blue-600 mt-0.5 flex-shrink-0" />
                <div>
                  <h3 className="font-semibold text-blue-900">Commencez par ajouter des lieux</h3>
                  <p className="text-sm text-blue-700 mt-1">
                    Utilisez le gestionnaire de lieux pour créer vos premiers concerts,
                    puis ajoutez du matériel à chacun d’eux.
                  </p>
                </div>
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
