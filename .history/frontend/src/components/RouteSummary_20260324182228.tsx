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
  const [barWidths, setBarWidths] = useState<Record<string, number>>({});

  // Vérifier la santé du serveur au montage
  useEffect(() => {
    checkServerHealth().then(setServerHealth);
  }, []);

  // Animer les barres de chargement à leur valeur réelle
  useEffect(() => {
    if (routes.length === 0) return;
    setBarWidths({});
    const timer = setTimeout(() => {
      const widths: Record<string, number> = {};
      routes.forEach(r => { widths[r.vehicleId] = r.utilization; });
      setBarWidths(widths);
    }, 120);
    return () => clearTimeout(timer);
  }, [routes]);

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

  // Affichage du formulaire d'optimisation
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

        {/* Sélection de la configuration */}
        <div className="space-y-2">
          <label className="text-xs font-semibold text-gray-700 uppercase tracking-wider">
            Sélectionner une configuration
          </label>
          <div className="grid grid-cols-2 gap-2">
            {(Object.entries(CONFIGURATIONS) as [ConfigType, typeof CONFIGURATIONS['equilibre']][]).map(
              ([configKey, config]) => (
                <button
                  key={configKey}
                  onClick={() => setSelectedConfig(configKey)}
                  className={`p-3 rounded-lg border-2 transition-all text-left ${
                    selectedConfig === configKey
                      ? 'bg-emerald-50 border-emerald-500 shadow-sm'
                      : 'bg-gray-50 border-gray-200 hover:border-gray-300'
                  }`}
                >
                  <div className="font-semibold text-sm text-gray-900">{config.label}</div>
                  <div className="text-xs text-gray-600">{config.description}</div>
                </button>
              )
            )}
          </div>
        </div>

        {/* Bouton Optimiser */}
        <Button
          onClick={handleOptimize}
          disabled={isOptimizing || !spots.length || !vehicles.length}
          className="w-full bg-white hover:bg-gray-100 text-gray-500"
        >
          {isOptimizing ? (
            <>
              <Loader className="w-4 h-4 mr-2 animate-spin" />
              Optimisation en cours...
            </>
          ) : (
            <>
              <Zap className="w-4 h-4 mr-2" />
              {solution ? "Relancer l'optimisation" : "Lancer l'Optimisation"}
            </>
          )}
        </Button>

        {/* État avant optimisation */}
        {!solution && !isOptimizing && null}

        {/* Résultat d'optimisation (intégré, sans remplacer le formulaire) */}
        {solution && (() => {
          const formatted = formatSolution(solution);
          return (
            <div className="space-y-3 pt-2 border-t border-gray-200">
              <div className="text-xs font-semibold text-gray-700 uppercase tracking-wider flex items-center gap-2">
                <TrendingUp className="w-4 h-4 text-emerald-600" />
                Résultat d'optimisation
              </div>
              <div className="bg-gradient-to-r from-emerald-50 to-blue-50 rounded-lg p-3 border border-emerald-200">
                <h3 className="font-semibold text-sm text-gray-900 mb-2">{formatted.title}</h3>
                <div className="grid grid-cols-4 gap-2">
                  {formatted.stats.map((stat, idx) => (
                    <div key={idx} className="bg-white rounded p-2 text-center">
                      <div className="text-sm font-semibold text-emerald-600">{stat.value}</div>
                      <div className="text-xs text-gray-600">{stat.label}</div>
                    </div>
                  ))}
                </div>
              </div>
              <div className="space-y-2">
                {formatted.routes.map((route, idx) => (
                  <div key={idx} className="p-3 rounded-lg bg-gray-50 border border-gray-200">
                    <div className="flex items-center justify-between mb-1">
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
          );
        })()}

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
                const color = getColorHex(vehicle.color);
                const utilization = barWidths[route.vehicleId] ?? 0;

                return (
                  <div
                    key={route.vehicleId}
                    className={`rounded-xl border-2 cursor-pointer transition-all overflow-hidden ${
                      selectedVehicleId === route.vehicleId
                        ? 'border-blue-400 shadow-md shadow-blue-100'
                        : 'border-gray-100 hover:border-blue-200 hover:shadow-sm'
                    }`}
                    onClick={() => onSelectVehicle(
                      selectedVehicleId === route.vehicleId ? null : route.vehicleId
                    )}
                  >
                    {/* Bande de couleur en haut */}
                    <div className="h-1" style={{ backgroundColor: color }} />

                    <div className="p-3 bg-white">
                      {/* En-tête : nom + arrêts */}
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-2">
                          <div className="w-3 h-3 rounded-full flex-shrink-0" style={{ backgroundColor: color }} />
                          <span className="font-bold text-gray-900 text-sm">{vehicle.name}</span>
                        </div>
                        <span className="text-xs text-gray-500 bg-gray-100 px-2 py-0.5 rounded-full">
                          {route.stops.length} arrêts
                        </span>
                      </div>

                      {/* Stats volume + distance */}
                      <div className="flex items-center gap-4 text-xs text-gray-600 mb-3">
                        <span className="flex items-center gap-1">
                          <Package className="w-3 h-3" />
                          <span className="font-semibold text-gray-800">{route.totalVolume}m³</span>
                          <span className="text-gray-400">/ {vehicle.capacity}m³</span>
                        </span>
                        <span className="flex items-center gap-1">
                          <MapPin className="w-3 h-3" />
                          {route.totalDistance}km
                        </span>
                      </div>

                      {/* Barre de chargement animée */}
                      <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                        <div
                          className="h-full rounded-full"
                          style={{
                            width: `${utilization}%`,
                            background: `linear-gradient(90deg, ${color}cc, ${color})`,
                            transition: 'width 0.9s cubic-bezier(0.4,0,0.2,1)',
                          }}
                        />
                      </div>
                      <div className="flex justify-between mt-1">
                        <span className="text-xs text-gray-400">Chargement</span>
                        <span className="text-xs font-bold" style={{ color }}>{route.utilization}%</span>
                      </div>
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
