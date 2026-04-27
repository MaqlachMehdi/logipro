import { useState, useEffect } from 'react';
import type { Route, Vehicle, Spot, GearItem } from '../types';
import {
  callVRPSolver,
  checkServerHealth,
  type VRPSolution,
} from '../utils/vrp-solver';
import { Card, CardContent, CardHeader, CardTitle } from './ui';
import { Button } from './ui/button';
import { MapPin, TrendingUp, Zap, AlertCircle, Loader, Clock } from 'lucide-react';
import { getVehicleColor, hexToRgba } from '../config/vehicle-colors';

interface RouteSummaryProps {
  routes: Route[];
  vehicles: Vehicle[];
  spots: Spot[];
  gears: GearItem[];
  selectedVehicleId: string | null;
  onSelectVehicle: (id: string | null) => void;
  hasSolution?: boolean;
  onSolutionChange?: (solution: VRPSolution | null) => void;
}

type ConfigType = 'equilibre' | 'economie_vehicules' | 'rapidite' | 'distance_min';

const CONFIGURATIONS: Record<ConfigType, { label: string; description: string }> = {
  equilibre:          { label: 'Équilibré',          description: 'Bon compromis' },
  economie_vehicules: { label: 'Économie Véhicules', description: 'Minimiser véhicules' },
  rapidite:           { label: 'Rapidité',           description: 'Minimiser temps' },
  distance_min:       { label: 'Distance Min',       description: 'Minimiser km' },
};


export function RouteSummary({
  routes,
  vehicles,
  spots,
  gears,
  selectedVehicleId,
  onSelectVehicle,
  hasSolution = false,
  onSolutionChange,
}: RouteSummaryProps) {
  const [selectedConfig, setSelectedConfig] = useState<ConfigType>('equilibre');
  const [isOptimizing, setIsOptimizing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [serverHealth, setServerHealth] = useState<boolean | null>(null);
  const [barWidths, setBarWidths] = useState<Record<string, number>>({});

  useEffect(() => { checkServerHealth().then(setServerHealth); }, []);

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
    if (!spots.length || !vehicles.length) { setError('Au moins 1 lieu et 1 véhicule requis'); return; }
    setError(null);
    setIsOptimizing(true);
    try {
      const response = await callVRPSolver(spots, vehicles, gears, selectedConfig);
      if (response.success && response.solution) {
        onSolutionChange?.(response.solution);
      } else {
        setError(response.error || "Erreur lors de l'optimisation");
        onSolutionChange?.(null);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erreur inconnue');
      onSolutionChange?.(null);
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
        <CardTitle className="flex items-center gap-2">
          <TrendingUp className="w-5 h-5 text-emerald-600" />
          Optimisation
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">

        {/* Serveur indisponible */}
        {serverHealth === false && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-3 flex items-start gap-3">
            <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
            <div className="text-sm">
              <p className="font-semibold text-red-900">Serveur indisponible</p>
              <p className="text-red-800 text-xs">Le serveur d'optimisation n'est pas accessible. Vérifiez que le backend est démarré.</p>
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

        {/* Sélection configuration */}
        <div className="space-y-2">
          <label className="app-text-eyebrow">
            Sélectionner une configuration
          </label>
          <div className="grid grid-cols-2 gap-2">
            {(Object.entries(CONFIGURATIONS) as [ConfigType, typeof CONFIGURATIONS['equilibre']][]).map(([key, cfg]) => (
              <button
                key={key}
                onClick={() => setSelectedConfig(key)}
                className={`p-3 rounded-lg border-2 transition-all text-left ${
                  selectedConfig === key
                    ? 'bg-emerald-50 border-emerald-500 shadow-sm'
                    : 'bg-gray-50 border-gray-200 hover:border-gray-300'
                }`}
              >
                <div className="app-title-subsection">{cfg.label}</div>
                <div className="sub_title_subsection">{cfg.description}</div>
              </button>
            ))}
          </div>
        </div>

        {/* Bouton Optimiser */}
        <Button
          onClick={handleOptimize}
          disabled={isOptimizing || !spots.length || !vehicles.length}
          className="bouton_add w-full bg-white hover:bg-gray-100 text-gray-900"
        >
          {isOptimizing ? (
            <><Loader className="w-4 h-4 mr-2 animate-spin" />Optimisation en cours...</>
          ) : (
            <><Zap className="w-4 h-4 mr-2" />{hasSolution ? "Relancer l'optimisation" : "Lancer l'Optimisation"}</>
          )}
        </Button>

        {/* Résumé tournées existantes (avant optimisation) */}
        {routes.length > 0 && !hasSolution && (
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
              <div className="app-text-eyebrow">Détails par véhicule</div>
              {routes.map((route) => {
                const vehicle = vehicles.find(v => v.id === route.vehicleId);
                if (!vehicle) return null;
                const vc = getVehicleColor(vehicle.color);
                const color = vc.hex;
                const utilization = barWidths[route.vehicleId] ?? 0;
                const isSelected = selectedVehicleId === route.vehicleId;

                return (
                  <div
                    key={route.vehicleId}
                    className="rounded-xl border-2 cursor-pointer transition-all overflow-hidden"
                    style={{
                      borderColor: isSelected ? color : '#f3f4f6',
                      boxShadow: isSelected ? `0 0 0 1px ${hexToRgba(color, 0.25)}, 0 4px 12px ${hexToRgba(color, 0.12)}` : undefined,
                    }}
                    onClick={() => onSelectVehicle(isSelected ? null : route.vehicleId)}
                  >
                    <div className="h-1" style={{ backgroundColor: color }} />
                    <div className="p-3 bg-white">
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-2">
                          <div className="w-3 h-3 rounded-full flex-shrink-0" style={{ backgroundColor: color }} />
                          <span className="app-title-subsection">{vehicle.name}</span>
                        </div>
                        <span className="text-xs text-gray-500 bg-gray-100 px-2 py-0.5 rounded-full">
                          {route.stops.length} arrêt{route.stops.length > 1 ? 's' : ''}
                        </span>
                      </div>
                      <div className="flex items-center gap-4 text-xs text-gray-600 mb-3">
                        <span className="number_subtitle">
                          <Clock />
                          {route.totalDistance.toFixed(1)} km
                        </span>
                        <span className="flex items-center gap-1">
                          <MapPin className="w-3 h-3" />
                          {route.utilization}%
                        </span>
                      </div>
                      <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                        <div
                          className="h-full rounded-full transition-all duration-700"
                          style={{
                            width: `${utilization}%`,
                            background: `linear-gradient(90deg, ${hexToRgba(color, 0.75)}, ${color})`,
                          }}
                        />
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
