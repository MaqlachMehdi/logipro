import type { Spot } from '../types';

const API_BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:5000';

export async function fetchSpots(): Promise<Spot[]> {
  const response = await fetch(`${API_BASE_URL}/api/spots`, {
    method: 'GET',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' }
  });

  if (!response.ok) {
    throw new Error(`Erreur API lieux: ${response.status}`);
  }

  const result = await response.json();
  if (!result.success || !Array.isArray(result.spots)) {
    throw new Error(result.error || 'Réponse lieux invalide');
  }

  return result.spots as Spot[];
}

export async function syncSpots(spots: Spot[]): Promise<Spot[]> {
  const response = await fetch(`${API_BASE_URL}/api/spots/sync`, {
    method: 'PUT',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ spots })
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.error || `Erreur sync lieux: ${response.status}`);
  }

  const result = await response.json();
  if (!result.success || !Array.isArray(result.spots)) {
    throw new Error(result.error || 'Réponse sync lieux invalide');
  }

  return result.spots as Spot[];
}
