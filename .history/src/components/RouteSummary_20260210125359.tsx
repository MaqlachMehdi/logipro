import type { Route, Vehicle } from '../types';
import { Card, CardContent, CardHeader, CardTitle } from './ui';
import { Truck, MapPin, Package, TrendingUp } from 'lucide-react';

interface RouteSummaryProps {
  routes: Route[];
  vehicles: Vehicle[];
  selectedVehicleId: string | null;
  onSelectVehicle: (id: string | null) => void;
}

export function RouteSummary({ 
  routes, 
  vehicles, 
  selectedVehicleId, 
  onSelectVehicle 
}: RouteSummaryProps) {
  const getColorHex = (color: string) => {
    const colorMap: Record<string, string> = {
      'indigo-500': '#6366f1',
      'emerald-500': '#10b981',
      'amber-500': '#f59e0b',
      'rose-500': '#f43f5e',
      'cyan-500': '#06b6d4',
      'violet-500': '#8b5cf6',
      'orange-500': '#f97316',
      'teal-500': '#14b8a6',
    };
    return colorMap[color] || '#64748b';
  };

  const totalDistance = routes.reduce((sum, r) => sum + r.totalDistance, 0);
  const totalVolume = routes.reduce((sum, r) => sum + r.totalVolume, 0);
  const avgUtilization = routes.length > 0 
    ? Math.round(routes.reduce((sum, r) => sum + r.utilization, 0) / routes.length)
    : 0;

  return (
    <Card className="bg-white border-gray-200">
      <CardHeader>
        <CardTitle className="text-gray-900 flex items-center gap-2">
          <TrendingUp className="w-5 h-5 text-emerald-600" />
          Résumé des Tournées
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {routes.length === 0 ? (
          <div className="text-center py-8">
            <MapPin className="w-12 h-12 text-gray-300 mx-auto mb-3" />
            <p className="text-gray-600 text-sm">
              Cliquez sur "Optimiser" pour générer les tournées
            </p>
          </div>
        ) : (
          <>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                <div className="bg-gray-50 rounded-lg p-3 text-center">
                    <div className="text-2xl font-bold text-blue-600">{routes.length}</div>
                    <div className="text-xs text-gray-600">Véhicules</div>
                </div>
                <div className="bg-gray-50 rounded-lg p-3 text-center">
                    <div className="text-2xl font-bold text-emerald-600">{totalDistance.toFixed(0)}</div>
                    <div className="text-xs text-gray-600">km Total</div>
                </div>
                <div className="bg-gray-50 rounded-lg p-3 text-center">
                    <div className="text-2xl font-bold text-amber-600">{avgUtilization}%</div>
                    <div className="text-xs text-gray-600">Utilisation</div>
                </div>
                </div>

            <div className="space-y-2">
              <div className="text-xs font-semibold text-gray-700 uppercase tracking-wider">
                Détails par véhicule
              </div>
              {routes.map((route) => {
                const vehicle = vehicles.find(v => v.id === route.vehicleId);
                if (!vehicle) return null;

                return (
                  <div
                    key={route.vehicleId}
                    className={`p-3 rounded-lg border cursor-pointer transition-all ${
                      selectedVehicleId === route.vehicleId
                        ? 'bg-blue-50 border-blue-500'
                        : 'bg-gray-50 border-gray-200 hover:border-gray-300'
                    }`}
                    onClick={() => onSelectVehicle(
                      selectedVehicleId === route.vehicleId ? null : route.vehicleId
                    )}
                  >
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-2">
                        <div 
                          className="w-3 h-3 rounded-full"
                          style={{ backgroundColor: getColorHex(vehicle.color) }}
                        />
                        <span className="font-medium text-gray-900 text-sm">
                          {vehicle.name}
                        </span>
                      </div>
                      <span className="text-xs text-gray-600">
                        {route.stops.length} arrêts
                      </span>
                    </div>
                    <div className="flex items-center gap-4 text-xs">
                      <span className="text-gray-700">
                        <Package className="w-3 h-3 inline mr-1" />
                        {route.totalVolume}m³ / {vehicle.capacity}m³
                      </span>
                      <span className="text-gray-700">
                        <Truck className="w-3 h-3 inline mr-1" />
                        {route.totalDistance}km
                      </span>
                    </div>
                    <div className="mt-2 h-1.5 bg-gray-200 rounded-full overflow-hidden">
                      <div 
                        className="h-full rounded-full transition-all"
                        style={{ 
                          width: `${route.utilization}%`,
                          backgroundColor: getColorHex(vehicle.color)
                        }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}
