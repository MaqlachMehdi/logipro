import type { Spot } from '../types';

// Valeur par défaut si le dépôt n'est pas encore en base
export const DEPOT_SPOT: Spot = {
  id: 'depot-permanent',
  name: 'Dépôt',
  address: '',
  lat: 0,
  lon: 0,
  openingTime: '08:00',
  closingTime: '23:00',
  gearSelections: [],
};