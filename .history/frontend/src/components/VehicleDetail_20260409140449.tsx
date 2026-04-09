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
    <Card className="bg-white border-gray-200">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Truck className="w-5 h-5 text-blue-600" />
          Détails - {vehicle.name}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Itineraire */}
        <div>
          <h3 className="app-title-subsection mb-3 text-gray-800">Itinéraire</h3>
          <div className="space-y-2">
            {legs.map((leg, idx) => (
              <div key={idx} className="flex items-center gap-3 text-xs">
                <div className="flex-1">
                  <p className="app-title-subsection text-gray-800">{leg.from}</p>
                  <p className="text-gray-600">↓</p>
                  <p className="app-title-subsection text-gray-800">{leg.to}</p>
                </div>
                <div className="text-right">
                  <p className="text-gray-700">{leg.distance.toFixed(1)}km</p>
                  <p className="text-gray-600">{leg.time.toFixed(0)}min</p>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Statistiques */}
        <div className="grid grid-cols-2 gap-2">
          <div className="bg-gray-50 rounded-lg p-3">
            <p className="text-xs text-gray-600">Distance totale</p>
            <p className="text-lg font-bold text-emerald-600">{totalDistance.toFixed(1)}km</p>
          </div>
          <div className="bg-gray-50 rounded-lg p-3">
            <p className="text-xs text-gray-600">Temps estimé</p>
            <p className="text-lg font-bold text-blue-600">{(totalTime / 60).toFixed(1)}h</p>
          </div>
        </div>

        {/* Instruments */}
        <div>
          <h3 className="app-title-subsection mb-3 text-gray-800">Instruments transportés</h3>
          <div className="space-y-2 max-h-56 overflow-y-auto">
            {Array.from(totalInstruments.entries()).map(([name, qty]) => (
              <div key={name} className="flex justify-between items-center p-2 bg-gray-50 rounded text-xs">
                <span className="text-gray-800">{name}</span>
                <span className="text-gray-600">x{qty}</span>
              </div>
            ))}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
