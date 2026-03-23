export interface GearItem {
  id: string;
  name: string;
  category: string;
  volume: number;
}

export interface GearSelection {
  gearId: string;
  quantity: number;
}

export type VehicleType = 'car' | 'van' | 'truck';

export interface Vehicle {
  id: string;
  name: string;
  type: VehicleType;
  capacity: number;
  color: string;
}

export interface Stop {
  venueId: string;
  type: 'load-in' | 'load-out';
  time: string;
  volume: number;
}

export interface Route {
  vehicleId: string;
  stops: Stop[];
  totalDistance: number;
  totalVolume: number;
  utilization: number;
  _rawData?: any;
}

export interface Spot {
  id: string;
  name: string;
  address: string;
  lat: number;
  lon: number;
  openingTime: string;
  closingTime: string;
  concertTime?: string;
  concertDuration?: number;
  gearSelections: GearSelection[];
}

export interface Venue {
  id: string;
  name: string;
  address: string;
  lat: number;
  lon: number;
  loadInWindow?: [string, string];
  loadOutWindow?: [string, string];
  volume?: number;
  timeWindow?: [number, number];
  demand?: number;
  instruments?: string;
  concertDuration?: number;
}

export interface AppState {
  spots: Spot[];
  selectedSpotId: string | null;
  vehicles: Vehicle[];
  routes: Route[];
  showLoadIn: boolean;
  showLoadOut: boolean;
  selectedVehicleId: string | null;
}
