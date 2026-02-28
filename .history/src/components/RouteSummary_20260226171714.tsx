import { useState, useEffect } from 'react';
import type { Route, Vehicle, Spot, GearItem } from '../types';
import {
  callVRPSolver,
  formatSolution,
  checkServerHealth,
  type VRPSolution
} from '../utils/vrp-solver';
import { Card, CardContent, CardHeader, CardTitle } from './ui';
import { Button } from './ui/button';
import { Truck, MapPin, Package, TrendingUp, Zap, AlertCircle, Loader } from 'lucide-react';

interface RouteSummaryProps {
  routes: Route[];
  vehicles: Vehicle[];
  spots: Spot[];
  gears: GearItem[];
  selectedVehicleId: string | null;
  onSelectVehicle: (id: string | null) => void;
}

type ConfigType = 'equilibre' | 'economie' | 'rapidite' | 'distance';

const CONFIGURATIONS: Record<ConfigType, { label: string; description: string }> = {
  equilibre: { label: 'Équilibré', description: 'Bon compromis' },
  economie: { label: 'Économie Véhicules', description: 'Minimiser véhicules' },
  rapidite: { label: 'Rapidité', description: 'Minimiser temps' },
  distance: { label: 'Distance Min', description: 'Minimiser km' }
};

export function RouteSummary({
  routes,
  vehicles,
  spots,
  gears,
  selectedVehicleId,
  onSelectVehicle
}: RouteSummaryProps) {
  const [selectedConfig, setSelectedConfig] = useState<ConfigType>('equilibre');
  const [isOptimizing, setIsOptimizing] = useState(false);
  const [solution, setSolution] = useState<VRPSolution | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [serverHealth, setServerHealth] = useState<boolean | null>(null);

  // Vérifier la santé du serveur au montage
  useEffect(() => {
    checkServerHealth().then(setServerHealth);
  }, []);

  const handleOptimize = async () => {
    if (!spots.length || !vehicles.length) {
      setError('Au moins 1 lieu et 1 véhicule requis');
      return;
    }

    setError(null);
    setIsOptimizing(true);

    try {
      const response = await callVRPSolver(spots, vehicles, gears, selectedConfig);

      if (response.success && response.solution) {
        setSolution(response.solution);
      } else {
        setError(response.error || 'Erreur lors de l\'optimisation');
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Erreur inconnue';
      setError(errorMessage);
      console.error('Erreur optimisation:', err);
    } finally {
      setIsOptimizing(false);
    }
  };

  const totalDistance = routes.reduce((sum, r) => sum + r.totalDistance, 0);
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

        {/* Résumé des tournées existantes */}
        {routes.length > 0 && !solution && (
          <>
            <div className="grid grid-cols-3 gap-2">
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
                        {route.totalVolume}m³
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
