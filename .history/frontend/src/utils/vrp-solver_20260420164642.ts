import type { Vehicle, Spot, GearItem, Route } from '../types';

/**
 * Types pour les réponses du solveur
 */
export interface SolutionEtape {
  de: string;
  vers: string;
  dist_km: number;
  trajet_min: number;
}

export interface SolutionConcert {
  concert_start: number;
  concert_duration: number;
  setup_duration: number;
  teardown_duration: number;
  instruments: string[];
  instrument_counts: Record<string, number>;
  venue_name: string;
}

export interface SolutionStop {
  step: number;
  label: string;
  address: string;
  action: 'Departure' | 'Delivery' | 'Recovery' | 'Return';
  arrival_time: number | null;
  time_window_start: number | null;
  time_window_end: number | null;
  volume_delta: number;
  load_after: number | null;
  service_time: number | null;
  distance_from_prev: number | null;
  travel_time_from_prev: number | null;
  concert: SolutionConcert | null;
}

export interface SolutionVehicle {
  nom: string;
  destinations: string[];
  temps_min: number;
  distance_km: number;
  etapes: SolutionEtape[];
  arrets: SolutionStop[];
  capacite_m3: number;
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
const API_BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:5000';

/**
 * Appelle le serveur d'optimisation
 * Le backend lit directement la base de données — aucune donnée à envoyer
 */
export async function callVRPSolver(
  _spots: Spot[],       // conservé pour ne pas casser les appels existants
  _vehicles: Vehicle[], // conservé pour ne pas casser les appels existants
  _gears: GearItem[],   // conservé pour ne pas casser les appels existants
  config: string = 'equilibre'
): Promise<OptimizationResponse> {
  try {
    console.log(`📤 Envoi de la demande d'optimisation (${config})...`);
    console.log('ℹ️  Le backend lit les données depuis la base de données');

    // Le backend construit lui-même le JSON depuis la DB
    // On envoie uniquement la configuration
    const response = await fetch(`${API_BASE_URL}/api/optimize/run`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ config }), // ✅ uniquement la config
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
      volume: 0
    })),
    totalDistance: vehicle.distance_km,
    totalVolume: 0,
    utilization: 0
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
