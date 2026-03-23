import { useEffect, useReducer, useState } from 'react';
import mapboxgl from 'mapbox-gl';
import { VolumeEstimator, FleetManager, RouteSummary, MapPlanner, SpotManager, VehicleDetail, ExportDatabase } from './components';
import type { Spot, Vehicle, Route, AppState, GearItem } from './types';
import { Truck, AlertCircle } from 'lucide-react';
import { GEAR_CATALOG } from './utils/volume-data';
import { fetchVehicles, syncVehicles } from './utils/vehicles-api';
import { fetchSpots, syncSpots } from './utils/spots-api';
import { fetchGears, syncGears } from './utils/gears-api';

// ✅ DEPOT_SPOT garde son id fixe — valeurs viennent de la DB au chargement
const DEPOT_SPOT: Spot = {
  id: 'depot-permanent',
  name: 'Dépôt',
  address: '',
  lat: 0,
  lon: 0,
  openingTime: '08:00',
  closingTime: '23:00',
  gearSelections: [],
};

// ✅ SUPPRIMÉ : DEFAULT_VEHICLES hardcodé

const USER_SPOTS_KEY = 'regietour_spots';

const removeDepot = (spots: Spot[]): Spot[] => spots.filter((s) => s.id !== DEPOT_SPOT.id);

// ✅ withDepot utilise la version DB si elle existe
const withDepot = (spots: Spot[]): Spot[] => {
  const depotFromDb = spots.find((s) => s.id === DEPOT_SPOT.id);
  const otherSpots = spots.filter((s) => s.id !== DEPOT_SPOT.id);
  return [depotFromDb ?? DEPOT_SPOT, ...otherSpots];
};

/* --------------------- STATE --------------------- */
const createInitialState = (): AppState => {
  const savedSpots = localStorage.getItem(USER_SPOTS_KEY);
  const userSpots = savedSpots ? JSON.parse(savedSpots) : [];
  const spots = withDepot(userSpots);

  return {
    spots,
    selectedSpotId: spots.length > 0 ? spots[0].id : null,
    vehicles: [], // ✅ vide — chargé depuis DB
    routes: [],
    showLoadIn: true,
    showLoadOut: true,
    selectedVehicleId: null,
  };
};

/* --------------------- REDUCER --------------------- */
              <MapPlanner
                accessToken={'pk.eyJ1IjoiZXhhbXBsZSIsImEiOiJja2x4b2Z6b2MwMDFwMnBvN2J6b2Z6b2MwIn0.1234567890abcdef'}
                styleUrl={undefined}
                center={[DEPOT_SPOT.lat, DEPOT_SPOT.lon]}
                zoom={13}
                spots={state.spots}
                routes={state.routes}
                onMapLoaded={(map) => {
                  try {
                    // nothing to do; LeafletMap handles markers
                    console.log('Leaflet map loaded');
                  } catch (e) {
                    console.error('Map onLoad error', e);
                  }
                }}
              />
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
const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:5000';

async function geocodeAddress(address: string): Promise<{ lat: number; lon: number } | null> {
  if (!address?.trim()) return null;
  try {
    const res = await fetch(`${API_URL}/api/geocode`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ address: address.trim() }),
    });
    const data = await res.json();
    if (typeof data.lat === 'number' && typeof data.lon === 'number') {
      return { lat: data.lat, lon: data.lon };
    }
    return null;
  } catch {
    return null;
  }
}

export default function App() {
  const [state, dispatch] = useReducer(appReducer, undefined, createInitialState);
  const [gears, setGears] = useState<GearItem[]>(GEAR_CATALOG);

  const persistSpots = async (spotsWithDepot: Spot[]) => {
    try {
      const persisted = await syncSpots(spotsWithDepot);
      // ✅ withDepot garde les valeurs DB du dépôt
      dispatch({ type: 'SET_SPOTS', payload: withDepot(persisted) });
    } catch (error) {
      console.error('Erreur sauvegarde lieux en base:', error);
    }
  };

  const handleAddSpot = async (spotInput: Omit<Spot, 'id' | 'gearSelections'>) => {
    const coords = await geocodeAddress(spotInput.address);
    const newSpot: Spot = {
      id: `spot-${Date.now()}`,
      ...spotInput,
      lat: coords?.lat ?? spotInput.lat,
      lon: coords?.lon ?? spotInput.lon,
      gearSelections: [],
    };
    const nextSpots = [...state.spots, newSpot];
    dispatch({ type: 'SET_SPOTS', payload: nextSpots });
    dispatch({ type: 'SELECT_SPOT', payload: newSpot.id });
    await persistSpots(nextSpots);
  };

  const handleUpdateSpot = async (updatedSpot: Spot) => {
    const originalSpot = state.spots.find((s) => s.id === updatedSpot.id);
    const addressChanged = originalSpot?.address !== updatedSpot.address;

    let spotToSave = { ...updatedSpot };
    if (addressChanged) {
      const coords = await geocodeAddress(updatedSpot.address);
      if (coords) spotToSave = { ...spotToSave, ...coords };
    }

    const nextSpots = state.spots.map((s) => s.id === spotToSave.id ? spotToSave : s);
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
        // ✅ Plus de fallback DEFAULT_VEHICLES — DB fait foi
        dispatch({ type: 'SET_VEHICLES', payload: vehicles });
      } catch (error) {
        console.error('Erreur chargement véhicules depuis la base:', error);
      }
    };
    loadVehicles();
    return () => { isMounted = false; };
  }, []);

  useEffect(() => {
    let isMounted = true;

    const loadGears = async () => {
      try {
        // 1. Charger DB
        const gearsFromDb = await fetchGears();
        if (!isMounted) return;

        // 2. Charger localStorage custom categories/instruments
        let localCustomCategories: string[] = [];
        let localCustomGears: GearItem[] = [];
        try {
          const rawCat = localStorage.getItem('regietour_custom_gear_categories');
          if (rawCat) {
            const parsedCat = JSON.parse(rawCat);
            if (Array.isArray(parsedCat)) {
              localCustomCategories = parsedCat.filter((c) => typeof c === 'string' && c.trim().length > 0);
            }
          }
          // On récupère tous les instruments custom (ceux qui ne sont pas dans la DB)
          const rawGears = localStorage.getItem('regietour_custom_gears');
          if (rawGears) {
            const parsedGears = JSON.parse(rawGears);
            if (Array.isArray(parsedGears)) {
              localCustomGears = parsedGears.filter(
                (g) => g && typeof g.id === 'string' && typeof g.name === 'string' && typeof g.category === 'string' && typeof g.volume === 'number'
              );
            }
          }
        } catch {}

        // 3. Fusionner DB et local
        const allGears = [...gearsFromDb];
        for (const gear of localCustomGears) {
          if (!allGears.some((g) => g.id === gear.id)) {
            allGears.push(gear);
          }
        }

        // 4. Persister tout dans la DB
        const persisted = await syncGears(allGears);
        if (isMounted) {
          setGears(persisted);
        }
        // 5. Nettoyer localStorage (migration effective)
        localStorage.removeItem('regietour_custom_gear_categories');
        localStorage.removeItem('regietour_custom_gears');
      } catch (error) {
        console.error('Erreur migration/chargement matériels depuis la base:', error);
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
    const previousGears = gears;
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
      setGears(previousGears);
      throw error;
    }
  };

  const handleDeleteGear = async (gearId: string) => {
    const previousGears = gears;
    const previousSpots = state.spots;

    const nextGears = gears.filter((gear) => gear.id !== gearId);
    const nextSpots = state.spots.map((spot) => ({
      ...spot,
      gearSelections: spot.gearSelections.filter((selection) => selection.gearId !== gearId),
    }));

    setGears(nextGears);
    dispatch({ type: 'SET_SPOTS', payload: nextSpots });

    try {
      const [persistedGears, persistedSpots] = await Promise.all([
        syncGears(nextGears),
        syncSpots(removeDepot(nextSpots)),
      ]);

      setGears(persistedGears);
      dispatch({ type: 'SET_SPOTS', payload: withDepot(persistedSpots) });
    } catch (error) {
      console.error('Erreur suppression matériel en base:', error);
      setGears(previousGears);
      dispatch({ type: 'SET_SPOTS', payload: previousSpots });
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
                  onDeleteGear={handleDeleteGear}
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
                accessToken={'pk.eyJ1IjoiZXhhbXBsZSIsImEiOiJja2x4b2Z6b2MwMDFwMnBvN2J6b2Z6b2MwIn0.1234567890abcdef'}
                styleUrl={undefined}
                center={[2.3522, 48.8566]}
                zoom={13}
                terrain={true}
                theme={'light'}
                onMapLoaded={(map) => {
                  try {
                    // Add depot marker and open its popup so it's visible
                    const m = new mapboxgl.Marker({ color: 'red' })
                      .setLngLat([DEPOT_SPOT.lon, DEPOT_SPOT.lat])
                      .setPopup(new mapboxgl.Popup({ offset: 12 }).setText(DEPOT_SPOT.name || 'Dépôt'))
                      .addTo(map);
                    m.togglePopup();
                    console.log('Map loaded — depot marker placed');
                  } catch (e) {
                    console.error('Failed to add depot marker', e);
                  }
                }}
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
