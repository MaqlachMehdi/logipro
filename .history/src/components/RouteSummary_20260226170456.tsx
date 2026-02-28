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

export function RouteSummary({
  routes,
  vehicles,
  spots,
  gears,
  selectedVehicleId,
  onSelectVehicle
}: RouteSummaryProps) {
  const [isOptimizing, setIsOptimizing] = useState(false);
  const [solutions, setSolutions] = useState<VRPSolution[]>([]);
  const [selectedSolution, setSelectedSolution] = useState<VRPSolution | null>(null);
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
      const response = await callVRPSolver(spots, vehicles, gears);

      if (response.success && response.solutions) {
        setSolutions(response.solutions);
        setSelectedSolution(response.best_solution || response.solutions[0]);
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
  const avgUtilization = routes.length > 0
    ? Math.round(routes.reduce((sum, r) => sum + r.utilization, 0) / routes.length)
    : 0;

  // Afficher les solutions du solveur
  if (selectedSolution) {
    const formatted = formatSolution(selectedSolution);

    return (
      <Card className="bg-white border-gray-200">
        <CardHeader>
          <CardTitle className="text-gray-900 flex items-center justify-between">
            <span className="flex items-center gap-2">
              <TrendingUp className="w-5 h-5 text-emerald-600" />
              Résultats d'Optimisation
            </span>
            <Button
              onClick={() => setSelectedSolution(null)}
              variant="outline"
              size="sm"
            >
              Nouvelles solutions
            </Button>
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Titre et stats de la solution */}
          <div className="bg-gradient-to-r from-emerald-50 to-blue-50 rounded-lg p-4 border border-emerald-200">
            <h3 className="font-bold text-lg text-gray-900 mb-3">{formatted.title}</h3>
            <div className="grid grid-cols-4 gap-2">
              {formatted.stats.map((stat, idx) => (
                <div key={idx} className="bg-white rounded p-2 text-center">
                  <div className="text-sm font-semibold text-emerald-600">
                    {stat.value}
                  </div>
                  <div className="text-xs text-gray-600">{stat.label}</div>
                </div>
              ))}
            </div>
          </div>

          {/* Liste des routes */}
          <div>
            <div className="text-xs font-semibold text-gray-700 uppercase tracking-wider mb-2">
              Routes détaillées
            </div>
            <div className="space-y-2">
              {formatted.routes.map((route, idx) => (
                <div key={idx} className="p-3 rounded-lg bg-gray-50 border border-gray-200">
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-medium text-gray-900 text-sm">{route.vehicle}</span>
                    <span className="text-xs text-gray-600">{route.stops}</span>
                  </div>
                  <div className="flex items-center gap-4 text-xs text-gray-700">
                    <span>⏱️ {route.time}</span>
                    <span>🛣️ {route.distance}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Autres solutions */}
          {solutions.length > 1 && (
            <div>
              <div className="text-xs font-semibold text-gray-700 uppercase tracking-wider mb-2">
                Autres solutions ({solutions.length - 1})
              </div>
              <div className="space-y-2">
                {solutions
                  .filter(s => s.id !== selectedSolution.id)
                  .map(sol => (
                    <button
                      key={sol.id}
                      onClick={() => setSelectedSolution(sol)}
                      className="w-full p-3 rounded-lg bg-gray-50 border border-gray-200 hover:border-blue-500 hover:bg-blue-50 transition-all text-left"
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-medium text-sm text-gray-900">{sol.label}</span>
                        <span className="text-xs text-gray-600">
                          {sol.nb_vehicules} véh. | {sol.distance_totale_km.toFixed(0)} km
                        </span>
                      </div>
                    </button>
                  ))}
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    );
  }

  // Affichage avant optimisation
  return (
    <Card className="bg-white border-gray-200">
      <CardHeader>
        <CardTitle className="text-gray-900 flex items-center gap-2">
          <TrendingUp className="w-5 h-5 text-emerald-600" />
          Résumé des Tournées
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Vérification du serveur */}
        {serverHealth === false && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-3 flex items-start gap-3">
            <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
            <div className="text-sm">
              <p className="font-semibold text-red-900">Serveur indisponible</p>
              <p className="text-red-800 text-xs">
                Le serveur d'optimisation (http://localhost:5000) n'est pas accessible.
              </p>
            </div>
          </div>
        )}

        {/* Erreur */}
        {error && (
          <div className="bg-orange-50 border border-orange-200 rounded-lg p-3 flex items-start gap-3">
            <AlertCircle className="w-5 h-5 text-orange-600 flex-shrink-0 mt-0.5" />
            <div className="text-sm">
              <p className="font-semibold text-orange-900">Erreur</p>
              <p className="text-orange-800 text-xs">{error}</p>
            </div>
          </div>
        )}

        {/* Bouton Optimiser */}
        <Button
          onClick={handleOptimize}
          disabled={isOptimizing || !spots.length || !vehicles.length}
          className="w-full bg-emerald-600 hover:bg-emerald-700 text-white"
        >
          {isOptimizing ? (
            <>
              <Loader className="w-4 h-4 mr-2 animate-spin" />
              Optimisation en cours...
            </>
          ) : (
            <>
              <Zap className="w-4 h-4 mr-2" />
              Lancer l'Optimisation
            </>
          )}
        </Button>

        {/* État avant optimisation */}
        {!solutions.length && !isOptimizing && (
          <div className="text-center py-8">
            <div className="flex items-center justify-center gap-2 mb-3">
              <Truck className="w-8 h-8 text-gray-400" />
              <MapPin className="w-8 h-8 text-gray-400" />
              <Package className="w-8 h-8 text-gray-400" />
            </div>
            <p className="text-gray-600 text-sm mb-1">Prêt pour optimisation</p>
            <p className="text-xs text-gray-500">
              {spots.length} lieu{spots.length !== 1 ? 'x' : ''} • {vehicles.length} véhicule{vehicles.length !== 1 ? 's' : ''}
            </p>
          </div>
        )}

        {/* Résumé des tournées existantes */}
        {routes.length > 0 && !solutions.length && (
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
