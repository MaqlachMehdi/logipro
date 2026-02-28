import type { Vehicle, Spot, GearItem, Route } from '../types';

/**
 * Types pour les réponses du solveur
 */
export interface SolutionVehicle {
  nom: string;
  destinations: string[];
  temps_min: number;
  distance_km: number;
}

export interface VRPSolution {
  id: number;
  label: string;
  timestamp: string;
  nb_vehicules: number;
  temps_total_min: number;
  distance_totale_km: number;
  objectif: number;
  weights: {
    vehicule: number;
    temps: number;
    distance: number;
  };
  details_vehicules: SolutionVehicle[];
  routes: Record<string, any>;
}

export interface OptimizationResponse {
  success: boolean;
  solution?: VRPSolution;
  error?: string;
}

/**
 * Configuration de l'API
 */
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:5000';

/**
 * Convertit une heure (HH:MM) en minutes depuis minuit
 */
function timeToMinutes(timeStr: string | undefined): number | null {
  if (!timeStr) return null;
  const [hours, minutes] = timeStr.split(':').map(Number);
  return hours * 60 + minutes;
}

/**
 * Prépare les données pour l'optimisation
 */
function prepareOptimizationData(
  spots: Spot[],
  vehicles: Vehicle[],
  gears: GearItem[]
) {
  // Créer les lieux avec index
  const lieux = spots.map((spot, idx) => {
    // Récupérer les instruments pour ce spot
    const instruments = spot.gearSelections
      .map(selection => {
        const gear = gears.find(g => g.id === selection.gearId);
        return gear ? Array(selection.quantity).fill(gear.name).join(', ') : '';
      })
      .filter(Boolean)
      .join(', ');

    return {
      Id_Lieux: idx,
      Nom: spot.name,
      Adresse: spot.address,
      lat: spot.lat,
      lon: spot.lon,
      Instruments: instruments || '',
      HeureTot: timeToMinutes(spot.openingTime),
      HeureConcert: timeToMinutes(spot.concertTime),
      HeureTard: timeToMinutes(spot.closingTime) || 22 * 60 // ← Convertir en minutes
    };
  });

  // Ajouter le dépôt (lieu 0)
  lieux.unshift({
    Id_Lieux: 0,
    Nom: 'Dépôt',
    Adresse: 'Dépôt',
    lat: spots[0]?.lat || 48.8566,
    lon: spots[0]?.lon || 2.3522,
    Instruments: '',
    HeureTot: 480, // 8:00
    HeureConcert: 1440, // Minuit
    HeureTard: '22:00' // 22:00
  });

  // Instruments (sans doublons)
  const instruments = Array.from(
    new Map(gears.map(g => [g.name, { Nom: g.name, Volume: g.volume }])).values()
  );

  // Véhicules
  const vehicules = vehicles.map((v, idx) => ({
    Id_vehicules: idx + 1,
    Nom: v.name,
    Volume_dispo: v.capacity
  }));

  return { lieux, instruments, vehicules };
}

/**
 * Appelle le serveur d'optimisation
 */
export async function callVRPSolver(
  spots: Spot[],
  vehicles: Vehicle[],
  gears: GearItem[],
  config: string = 'equilibre'
): Promise<OptimizationResponse> {
  try {
    if (!spots.length || !vehicles.length) {
      throw new Error('Au moins 1 lieu et 1 véhicule requis');
    }

    // Préparer les données
    const data = prepareOptimizationData(spots, vehicles, gears);

    console.log(`📤 Envoi de la demande d\'optimisation (${config})...`);

    // Appeler l'API avec la configuration
    const response = await fetch(`${API_BASE_URL}/api/optimize`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        ...data,
        config
      })
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(
        errorData.error || `Erreur API: ${response.status} ${response.statusText}`
      );
    }

    const result: OptimizationResponse = await response.json();

    if (!result.success) {
      throw new Error(result.error || 'Erreur lors de l\'optimisation');
    }

    console.log('✅ Optimisation réussie');
    console.log(`   - ${result.solution?.label || 'Solution'} obtenue`);

    return result;
  } catch (error) {
    console.error('❌ Erreur optimisation:', error);
    throw error;
  }
}

/**
 * Convertit une solution VRP en routes pour l'interface
 */
export function convertSolutionToRoutes(solution: VRPSolution): Route[] {
  return solution.details_vehicules.map((vehicle, idx) => ({
    vehicleId: `route-${idx}`,
    stops: vehicle.destinations.map((_dest, stopIdx) => ({
      venueId: `venue-${stopIdx}`,
      type: stopIdx === 0 ? 'load-out' : 'load-in',
      time: `${Math.floor(solution.temps_total_min / vehicle.destinations.length * stopIdx / 60)}:00`,
      volume: 0 // À calculer depuis les détails
    })),
    totalDistance: vehicle.distance_km,
    totalVolume: 0, // À calculer
    utilization: 0 // À calculer
  }));
}

/**
 * Formate une solution pour l'affichage
 */
export function formatSolution(solution: VRPSolution): {
  title: string;
  stats: Array<{ label: string; value: string | number }>;
  routes: Array<{ vehicle: string; stops: string; time: string; distance: string }>;
} {
  return {
    title: solution.label,
    stats: [
      { label: 'Véhicules', value: solution.nb_vehicules },
      { label: 'Temps total', value: `${solution.temps_total_min?.toFixed(0) || 0} min` },
      { label: 'Distance', value: `${solution.distance_totale_km?.toFixed(1) || 0} km` },
      { label: 'Score', value: solution.objectif?.toFixed(2) || '0' }
    ],
    routes: solution.details_vehicules.map(v => ({
      vehicle: v.nom,
      stops: v.destinations.join(' → '),
      time: `${v.temps_min?.toFixed(1) || 0} min`,
      distance: `${v.distance_km?.toFixed(1) || 0} km`
    }))
  };
}

/**
 * Vérifie l'état du serveur
 */
export async function checkServerHealth(): Promise<boolean> {
  try {
    const response = await fetch(`${API_BASE_URL}/api/health`, {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' }
    });
    return response.ok;
  } catch {
    return false;
  }
}
