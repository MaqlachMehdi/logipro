import { useEffect, useReducer, useState } from 'react';
import { VolumeEstimator, FleetManager, RouteSummary, MapPlanner, ExportPanel, SpotManager, VehicleDetail, ExportDatabase } from './components';
import type { Spot, Vehicle, Route, AppState, GearItem } from './types';
import { Truck, AlertCircle } from 'lucide-react';
import { GEAR_CATALOG } from './utils/volume-data';
import { fetchVehicles, syncVehicles } from './utils/vehicles-api';
import { fetchSpots, syncSpots } from './utils/spots-api';
import { fetchGears, syncGears } from './utils/gears-api';

const DEPOT_SPOT: Spot = {
  id: 'depot-permanent',
  name: 'Dépôt',
  address: '32 allée du hêtre, 77340, Pontault-Combault, France',
  lat: 48.8566,
  lon: 2.3522,
  openingTime: '08:00',
  closingTime: '23:00',
  gearSelections: [],
};

type AppAction =
  | { type: 'SET_SPOTS'; payload: Spot[] }
  | { type: 'SELECT_SPOT'; payload: string | null }
  | { type: 'UPDATE_SPOT_GEAR'; payload: { spotId: string; gear: any[] } }
  | { type: 'UPDATE_SPOT'; payload: Spot }
  | { type: 'ADD_SPOT'; payload: Omit<Spot, 'id' | 'gearSelections'> }
  | { type: 'DELETE_SPOT'; payload: string }
  | { type: 'SET_VEHICLES'; payload: Vehicle[] }
  | { type: 'SET_ROUTES'; payload: Route[] }
  | { type: 'SELECT_VEHICLE'; payload: string | null };

const DEFAULT_VEHICLES: Vehicle[] = [
  { id: 'v-1', name: 'AA-123-BB', type: 'car', capacity: 4, color: 'indigo-500' },
  { id: 'v-2', name: 'CC-456-DD', type: 'van', capacity: 12, color: 'emerald-500' },
  { id: 'v-3', name: 'TR-789-XX', type: 'truck', capacity: 28, color: 'amber-500' },
  { id: 'v-4', name: 'PL-321-KK', type: 'van', capacity: 18, color: 'rose-500' },
  { id: 'v-5', name: 'ZX-908-QM', type: 'truck', capacity: 45, color: 'cyan-500' },
];

const USER_SPOTS_KEY = 'regietour_spots';

const removeDepot = (spots: Spot[]): Spot[] => spots.filter((s) => s.id !== DEPOT_SPOT.id);

const withDepot = (spots: Spot[]): Spot[] => [DEPOT_SPOT, ...removeDepot(spots)];

/* --------------------- STATE --------------------- */
const createInitialState = (): AppState => {
  const savedSpots = localStorage.getItem(USER_SPOTS_KEY);
  const userSpots = savedSpots ? JSON.parse(savedSpots) : [];
  const spots = withDepot(userSpots);

  return {
    spots,
    selectedSpotId: spots.length > 0 ? spots[0].id : null,
    vehicles: DEFAULT_VEHICLES,
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
      localStorage.setItem(USER_SPOTS_KEY, JSON.stringify(removeDepot(action.payload)));
      return { ...state, spots: action.payload };

    case 'SELECT_SPOT':
      return { ...state, selectedSpotId: action.payload };

    case 'UPDATE_SPOT_GEAR':
      const updatedSpots = state.spots.map((spot) =>
        spot.id === action.payload.spotId ? { ...spot, gearSelections: action.payload.gear } : spot,
      );
      localStorage.setItem(USER_SPOTS_KEY, JSON.stringify(removeDepot(updatedSpots)));
      return { ...state, spots: updatedSpots };

    case 'UPDATE_SPOT':
      const updatedSpotsForUpdate = state.spots.map((spot) =>
        spot.id === action.payload.id ? action.payload : spot,
      );
      localStorage.setItem(USER_SPOTS_KEY, JSON.stringify(removeDepot(updatedSpotsForUpdate)));
      return { ...state, spots: updatedSpotsForUpdate };

    case 'ADD_SPOT':
      const newSpot: Spot = {
        id: `spot-${Date.now()}`,
        ...action.payload,
        gearSelections: [],
      };
      const newSpots = [...state.spots, newSpot];
      localStorage.setItem(USER_SPOTS_KEY, JSON.stringify(removeDepot(newSpots)));
      return { ...state, spots: newSpots, selectedSpotId: newSpot.id };

    case 'DELETE_SPOT':
      if (action.payload === 'depot-permanent') return state;
      const filteredSpots = state.spots.filter((s) => s.id !== action.payload);
      localStorage.setItem(USER_SPOTS_KEY, JSON.stringify(removeDepot(filteredSpots)));
      return {
        ...state,
        spots: filteredSpots,
        selectedSpotId: state.selectedSpotId === action.payload ? null : state.selectedSpotId,
      };

    case 'SET_VEHICLES':
      return { ...state, vehicles: action.payload };

    case 'SET_ROUTES':
      return { ...state, routes: action.payload };

    case 'SELECT_VEHICLE':
      return { ...state, selectedVehicleId: action.payload };

    default:
      return state;
  }
}

/* --------------------- APP --------------------- */
export default function App() {
  const [state, dispatch] = useReducer(appReducer, undefined, createInitialState);
  const [gears, setGears] = useState<GearItem[]>(GEAR_CATALOG);

  const persistSpots = async (spotsWithDepot: Spot[]) => {
    const userSpots = removeDepot(spotsWithDepot);
    try {
      const persisted = await syncSpots(userSpots);
      dispatch({ type: 'SET_SPOTS', payload: withDepot(persisted) });
    } catch (error) {
      console.error('Erreur sauvegarde lieux en base:', error);
    }
  };

  const handleAddSpot = async (spotInput: Omit<Spot, 'id' | 'gearSelections'>) => {
    const newSpot: Spot = {
      id: `spot-${Date.now()}`,
      ...spotInput,
      gearSelections: [],
    };
    const nextSpots = [...state.spots, newSpot];
    dispatch({ type: 'SET_SPOTS', payload: nextSpots });
    dispatch({ type: 'SELECT_SPOT', payload: newSpot.id });
    await persistSpots(nextSpots);
  };

  const handleUpdateSpot = async (updatedSpot: Spot) => {
    const nextSpots = state.spots.map((spot) =>
      spot.id === updatedSpot.id ? updatedSpot : spot,
    );
    dispatch({ type: 'SET_SPOTS', payload: nextSpots });
    await persistSpots(nextSpots);
  };

  const handleDeleteSpot = async (spotId: string) => {
    if (spotId === DEPOT_SPOT.id) return;
    const nextSpots = state.spots.filter((spot) => spot.id !== spotId);
    dispatch({ type: 'SET_SPOTS', payload: nextSpots });
    if (state.selectedSpotId === spotId) {
      dispatch({ type: 'SELECT_SPOT', payload: DEPOT_SPOT.id });
    }
    await persistSpots(nextSpots);
  };

  const handleUpdateSpotGear = async (spotId: string, gear: any[]) => {
    const nextSpots = state.spots.map((spot) =>
      spot.id === spotId ? { ...spot, gearSelections: gear } : spot,
    );
    dispatch({ type: 'SET_SPOTS', payload: nextSpots });
    await persistSpots(nextSpots);
  };

  useEffect(() => {
    let isMounted = true;

    const loadVehicles = async () => {
      try {
        const vehicles = await fetchVehicles();

        if (!isMounted) return;

        if (vehicles.length > 0) {
          dispatch({ type: 'SET_VEHICLES', payload: vehicles });
        } else {
          await syncVehicles(DEFAULT_VEHICLES);
          if (isMounted) {
            dispatch({ type: 'SET_VEHICLES', payload: DEFAULT_VEHICLES });
          }
        }
      } catch (error) {
        console.error('Erreur chargement véhicules depuis la base:', error);
      }
    };

    loadVehicles();

    return () => {
      isMounted = false;
    };
  }, []);

  useEffect(() => {
    let isMounted = true;

    const loadGears = async () => {
      try {
        const gearsFromDb = await fetchGears();
        if (!isMounted) return;

        if (gearsFromDb.length > 0) {
          setGears(gearsFromDb);
        } else {
          const persisted = await syncGears(GEAR_CATALOG);
          if (isMounted) {
            setGears(persisted);
          }
        }
      } catch (error) {
        console.error('Erreur chargement matériels depuis la base:', error);
      }
    };

    loadGears();

    return () => {
      isMounted = false;
    };
  }, []);

  useEffect(() => {
    let isMounted = true;

    const loadSpots = async () => {
      try {
        const spotsFromDb = await fetchSpots();
        if (!isMounted) return;

        if (spotsFromDb.length > 0) {
          const spots = withDepot(spotsFromDb);
          dispatch({ type: 'SET_SPOTS', payload: spots });
          dispatch({ type: 'SELECT_SPOT', payload: spots[0]?.id || DEPOT_SPOT.id });
        } else {
          const savedSpots = localStorage.getItem(USER_SPOTS_KEY);
          const fallbackSpots = savedSpots ? JSON.parse(savedSpots) as Spot[] : [];
          if (fallbackSpots.length > 0) {
            const persisted = await syncSpots(removeDepot(fallbackSpots));
            if (isMounted) {
              const merged = withDepot(persisted);
              dispatch({ type: 'SET_SPOTS', payload: merged });
              dispatch({ type: 'SELECT_SPOT', payload: merged[0]?.id || DEPOT_SPOT.id });
            }
          }
        }
      } catch (error) {
        console.error('Erreur chargement lieux depuis la base:', error);
      }
    };

    loadSpots();

    return () => {
      isMounted = false;
    };
  }, []);

  const selectedSpot = state.spots.find((s) => s.id === state.selectedSpotId);

  const totalVolume = state.spots.reduce((sum, spot) => {
    const spotVolume = spot.gearSelections.reduce((spotSum, sel) => {
      const gear = gears.find((g: any) => g.id === sel.gearId);
      return spotSum + (gear?.volume || 0) * sel.quantity;
    }, 0);
    return sum + spotVolume;
  }, 0);

  const handleVehiclesChange = async (vehicles: Vehicle[]) => {
    dispatch({ type: 'SET_VEHICLES', payload: vehicles });
    try {
      const persistedVehicles = await syncVehicles(vehicles);
      dispatch({ type: 'SET_VEHICLES', payload: persistedVehicles });
    } catch (error) {
      console.error('Erreur sauvegarde véhicules en base:', error);
    }
  };

  const handleAddGear = async (gearInput: Omit<GearItem, 'id'>) => {
    const newGear: GearItem = {
      id: `gear-${Date.now()}`,
      name: gearInput.name.trim(),
      category: gearInput.category.trim(),
      volume: gearInput.volume,
    };

    const nextGears = [...gears, newGear];
    setGears(nextGears);

    try {
      const persisted = await syncGears(nextGears);
      setGears(persisted);
    } catch (error) {
      console.error('Erreur ajout matériel en base:', error);
      setGears(gears);
      throw error;
    }
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
                selectedSpotId={state.selectedSpotId}
                onSelectSpot={(id) => dispatch({ type: 'SELECT_SPOT', payload: id })}
                onAddSpot={handleAddSpot}
                onUpdateSpot={handleUpdateSpot}
                onDeleteSpot={handleDeleteSpot}
              />

              {selectedSpot && (
                <VolumeEstimator
                  selections={selectedSpot.gearSelections}
                  onChange={(gear) => handleUpdateSpotGear(selectedSpot.id, gear)}
                  spotName={selectedSpot.name}
                  gears={gears}
                  onAddGear={handleAddGear}
                />
              )}

              <FleetManager
                vehicles={state.vehicles}
                onChange={handleVehiclesChange}
              />
            </div>

            {/* ── CENTER PANEL – Map & Routes ── */}
            <div className="col-span-12 lg:col-span-5 space-y-6">

              <RouteSummary
                routes={state.routes}
                vehicles={state.vehicles}
                spots={state.spots}
                gears={gears}
                selectedVehicleId={state.selectedVehicleId}
                onSelectVehicle={(id) => dispatch({ type: 'SELECT_VEHICLE', payload: id })}
              />

              <MapPlanner
                routes={state.routes}
                vehicles={state.vehicles}
                spots={state.spots}
                selectedVehicleId={state.selectedVehicleId}
                showLoadIn={state.showLoadIn}
                showLoadOut={state.showLoadOut}
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
                  }))}
                  gearCatalog={gears.map((g) => ({ id: g.id, name: g.name, volume: g.volume }))}
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
