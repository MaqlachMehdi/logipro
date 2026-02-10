import type { Route, Vehicle, Spot } from '../types';
import { Truck } from 'lucide-react';
import { GEAR_CATALOG } from '../utils/volume-data';
import { Card, CardContent, CardHeader, CardTitle } from './ui';

interface VehicleDetailProps {
  routes: Route[];
  vehicles: Vehicle[];
  spots: Spot[];
  selectedVehicleId: string | null;
}

function calculateDistance(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const R = 6371; 
  const dLat = (lat2 - lat1) * Math.PI / 180;
  const dLon = (lon2 - lon1) * Math.PI / 180;
  const a = 
    Math.sin(dLat/2) * Math.sin(dLat/2) +
    Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
    Math.sin(dLon/2) * Math.sin(dLon/2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
  return R * c;
}

function estimateTime(distanceKm: number): number {
  const avgSpeed = 30;
  return (distanceKm / avgSpeed) * 60;
}

export function VehicleDetail({ routes, vehicles, spots, selectedVehicleId }: VehicleDetailProps) {
  if (!selectedVehicleId) {
    return (
      <Card className="bg-white border-gray-200">
        <CardContent className="p-8 text-center text-gray-600">
          Sélectionnez un véhicule dans le résumé pour voir les détails
        </CardContent>
      </Card>
    );
  }

  const route = routes.find(r => r.vehicleId === selectedVehicleId);
  const vehicle = vehicles.find(v => v.id === selectedVehicleId);

  if (!route || !vehicle) return null;

  const DEPOT = { lat: 48.8566, lon: 2.3522, name: 'Dépôt' };

  const waypoints = [
    { ...DEPOT, type: 'depot' as const },
    ...route.stops.map(stop => {
      const spot = spots.find(s => s.id === stop.venueId);
      return { 
        lat: spot?.lat || 0, 
        lon: spot?.lon || 0, 
        name: spot?.name || 'Inconnu', 
        type: stop.type,
        venueId: stop.venueId
      };
    }),
    { ...DEPOT, type: 'depot' as const }
  ];

  const legs = [];
  let totalDistance = 0;
  let totalTime = 0;

  for (let i = 0; i < waypoints.length - 1; i++) {
    const from = waypoints[i];
    const to = waypoints[i + 1];
    const dist = calculateDistance(from.lat, from.lon, to.lat, to.lon);
    const time = estimateTime(dist);
    
    totalDistance += dist;
    totalTime += time;

    legs.push({
      from: from.name,
      to: to.name,
      distance: dist,
      time: time
    });
  }

  const instrumentsByVenue = new Map<string, Map<string, number>>();
  const totalInstruments = new Map<string, number>();

  route.stops.forEach(stop => {
    const spot = spots.find(s => s.id === stop.venueId);
    if (!spot) return;

    if (!instrumentsByVenue.has(spot.name)) {
      instrumentsByVenue.set(spot.name, new Map());
    }

    spot.gearSelections.forEach(sel => {
      const gear = GEAR_CATALOG.find(g => g.id === sel.gearId);
      if (!gear) return;

      const venueMap = instrumentsByVenue.get(spot.name)!;
      venueMap.set(gear.name, (venueMap.get(gear.name) || 0) + sel.quantity);
      totalInstruments.set(gear.name, (totalInstruments.get(gear.name) || 0) + sel.quantity);
    });
  });

  return (
    <Card className="bg-slate-800 border-slate-700">
      <CardHeader>
        <CardTitle className="text-slate-100 flex items-center gap-2">
          <Truck className="w-5 h-5 text-amber-400" />
          Détails - {vehicle.name}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Itineraire */}
        <div>
          <h3 className="text-sm font-semibold text-slate-300 mb-3">Itinéraire</h3>
          <div className="space-y-2">
            {legs.map((leg, idx) => (
              <div key={idx} className="flex items-center gap-3 text-xs">
                <div className="flex-1">
                  <p className="text-slate-300 font-medium">{leg.from}</p>
                  <p className="text-slate-500">↓</p>
                  <p className="text-slate-300 font-medium">{leg.to}</p>
                </div>
                <div className="text-right">
                  <p className="text-slate-400">{leg.distance.toFixed(1)}km</p>
                  <p className="text-slate-500">{leg.time.toFixed(0)}min</p>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Statistiques */}
        <div className="grid grid-cols-2 gap-2">
          <div className="bg-slate-900 rounded-lg p-3">
            <p className="text-xs text-slate-500">Distance totale</p>
            <p className="text-lg font-bold text-emerald-400">{totalDistance.toFixed(1)}km</p>
          </div>
          <div className="bg-slate-900 rounded-lg p-3">
            <p className="text-xs text-slate-500">Temps estimé</p>
            <p className="text-lg font-bold text-blue-400">{(totalTime / 60).toFixed(1)}h</p>
          </div>
        </div>

        {/* Instruments */}
        <div>
          <h3 className="text-sm font-semibold text-slate-300 mb-3">Instruments transportés</h3>
          <div className="space-y-2 max-h-56 overflow-y-auto">
            {Array.from(totalInstruments.entries()).map(([name, qty]) => (
              <div key={name} className="flex justify-between items-center p-2 bg-slate-900/50 rounded text-xs">
                <span className="text-slate-300">{name}</span>
                <span className="text-slate-500">x{qty}</span>
              </div>
            ))}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
