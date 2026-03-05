import type { Vehicle } from '../types';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:5000';

export async function fetchVehicles(): Promise<Vehicle[]> {
  const response = await fetch(`${API_BASE_URL}/api/vehicles`, {
    method: 'GET',
    headers: { 'Content-Type': 'application/json' }
  });

  if (!response.ok) {
    throw new Error(`Erreur API véhicules: ${response.status}`);
  }

  const result = await response.json();
  if (!result.success || !Array.isArray(result.vehicles)) {
    throw new Error(result.error || 'Réponse véhicules invalide');
  }

  return result.vehicles as Vehicle[];
}

export async function syncVehicles(vehicles: Vehicle[]): Promise<Vehicle[]> {
  const response = await fetch(`${API_BASE_URL}/api/vehicles/sync`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ vehicles })
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.error || `Erreur sync véhicules: ${response.status}`);
  }

  const result = await response.json();
  if (!result.success || !Array.isArray(result.vehicles)) {
    throw new Error(result.error || 'Réponse sync véhicules invalide');
  }

  return result.vehicles as Vehicle[];
}
