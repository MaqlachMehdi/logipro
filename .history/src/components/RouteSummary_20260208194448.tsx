import type { Route, Vehicle } from '../../types';
import { Card, CardContent, CardHeader, CardTitle } from '../ui';
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
    <Card className="bg-slate-800 border-slate-700">
      <CardHeader>
        <CardTitle className="text-slate-100 flex items-center gap-2">
          <TrendingUp className="w-5 h-5 text-emerald-400" />
          Résumé des Tournées
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {routes.length === 0 ? (
          <div className="text-center py-8">
            <MapPin className="w-12 h-12 text-slate-600 mx-auto mb-3" />
            <p className="text-slate-500 text-sm">
              Cliquez sur "Optimiser" pour générer les tournées
            </p>
          </div>
        ) : (
          <>
            <div className="grid grid-cols-3 gap-2">
              <div className="bg-slate-900 rounded-lg p-3 text-center">
                <div className="text-2xl font-bold text-indigo-400">{routes.length}</div>
                <div className="text-xs text-slate-500">Véhicules</div>
              </div>
              <div className="bg-slate-900 rounded-lg p-3 text-center">
                <div className="text-2xl font-bold text-emerald-400">{totalDistance.toFixed(0)}</div>
                <div className="text-xs text-slate-500">km Total</div>
              </div>
              <div className="bg-slate-900 rounded-lg p-3 text-center">
                <div className="text-2xl font-bold text-amber-400">{avgUtilization}%</div>
                <div className="text-xs text-slate-500">Utilisation</div>
              </div>
            </div>

            <div className="space-y-2">
              <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
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
                        ? 'bg-slate-700 border-indigo-500'
                        : 'bg-slate-900 border-slate-700 hover:border-slate-600'
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
                        <span className="font-medium text-slate-200 text-sm">
                          {vehicle.name}
                        </span>
                      </div>
                      <span className="text-xs text-slate-500">
                        {route.stops.length} arrêts
                      </span>
                    </div>
                    <div className="flex items-center gap-4 text-xs">
                      <span className="text-slate-400">
                        <Package className="w-3 h-3 inline mr-1" />
                        {route.totalVolume}m³ / {vehicle.capacity}m³
                      </span>
                      <span className="text-slate-400">
                        <Truck className="w-3 h-3 inline mr-1" />
                        {route.totalDistance}km
                      </span>
                    </div>
                    <div className="mt-2 h-1.5 bg-slate-700 rounded-full overflow-hidden">
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
