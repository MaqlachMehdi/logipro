import type { GearItem } from '../types';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:5000';

export async function fetchGears(): Promise<GearItem[]> {
  const response = await fetch(`${API_BASE_URL}/api/gears`, {
    method: 'GET',
    headers: { 'Content-Type': 'application/json' }
  });

  if (!response.ok) {
    throw new Error(`Erreur API matériels: ${response.status}`);
  }

  const result = await response.json();
  if (!result.success || !Array.isArray(result.gears)) {
    throw new Error(result.error || 'Réponse matériels invalide');
  }

  return result.gears as GearItem[];
}

export async function syncGears(gears: GearItem[]): Promise<GearItem[]> {
  const response = await fetch(`${API_BASE_URL}/api/gears/sync`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ gears })
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.error || `Erreur sync matériels: ${response.status}`);
  }

  const result = await response.json();
  if (!result.success || !Array.isArray(result.gears)) {
    throw new Error(result.error || 'Réponse sync matériels invalide');
  }

  return result.gears as GearItem[];
}
