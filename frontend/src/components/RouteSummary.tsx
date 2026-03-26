import { useState, useEffect } from 'react';
import type { Route, Vehicle, Spot, GearItem } from '../types';
import {
  callVRPSolver,
  checkServerHealth,
  type VRPSolution,
} from '../utils/vrp-solver';
import { Card, CardContent, CardHeader, CardTitle } from './ui';
import { Button } from './ui/button';
import { MapPin, Package, TrendingUp, Zap, AlertCircle, Loader, Clock, ChevronDown, ChevronUp, Navigation } from 'lucide-react';

interface RouteSummaryProps {
  routes: Route[];
  vehicles: Vehicle[];
  spots: Spot[];
  gears: GearItem[];
  selectedVehicleId: string | null;
  onSelectVehicle: (id: string | null) => void;
  onSolutionReady?: () => void;
}

type ConfigType = 'equilibre' | 'economie' | 'rapidite' | 'distance';

const CONFIGURATIONS: Record<ConfigType, { label: string; description: string }> = {
  equilibre: { label: 'Équilibré', description: 'Bon compromis' },
  economie: { label: 'Économie Véhicules', description: 'Minimiser véhicules' },
  rapidite: { label: 'Rapidité', description: 'Minimiser temps' },
  distance: { label: 'Distance Min', description: 'Minimiser km' }
};

/** Convert minutes-from-midnight to "HH:MM" */
const minToHHMM = (min: number): string => {
  const h = Math.floor(min / 60) % 24;
  const m = Math.round(min % 60);
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`;
};

// Palette blue/violet for vehicle detail panels
const DETAIL_PALETTE = [
  { bg: 'from-blue-50 to-violet-50', border: 'border-blue-200', accent: '#3b82f6', accentDark: '#1d4ed8', row: 'bg-blue-50/60' },
  { bg: 'from-violet-50 to-blue-50', border: 'border-violet-200', accent: '#7c3aed', accentDark: '#5b21b6', row: 'bg-violet-50/60' },
  { bg: 'from-indigo-50 to-blue-50', border: 'border-indigo-200', accent: '#4f46e5', accentDark: '#3730a3', row: 'bg-indigo-50/60' },
  { bg: 'from-blue-50 to-indigo-50', border: 'border-blue-200', accent: '#2563eb', accentDark: '#1e40af', row: 'bg-blue-50/60' },
];

export function RouteSummary({
  routes,
  vehicles,
  spots,
  gears,
  selectedVehicleId,
  onSelectVehicle,
  onSolutionReady,
}: RouteSummaryProps) {
  const [selectedConfig, setSelectedConfig] = useState<ConfigType>('equilibre');
  const [isOptimizing, setIsOptimizing] = useState(false);
  const [solution, setSolution] = useState<VRPSolution | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [serverHealth, setServerHealth] = useState<boolean | null>(null);
  const [barWidths, setBarWidths] = useState<Record<string, number>>({});
  const [solutionBarWidths, setSolutionBarWidths] = useState<Record<number, number>>({});
  const [expandedIdx, setExpandedIdx] = useState<number | null>(null);

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

  useEffect(() => {
    if (!solution) { setSolutionBarWidths({}); return; }
    setSolutionBarWidths({});
    const maxTime = Math.max(...solution.details_vehicules.map(v => v.temps_min));
    const timer = setTimeout(() => {
      const widths: Record<number, number> = {};
      solution.details_vehicules.forEach((v, idx) => {
        widths[idx] = maxTime > 0 ? Math.round((v.temps_min / maxTime) * 100) : 0;
      });
      setSolutionBarWidths(widths);
    }, 120);
    return () => clearTimeout(timer);
  }, [solution]);

  const handleOptimize = async () => {
    if (!spots.length || !vehicles.length) { setError('Au moins 1 lieu et 1 véhicule requis'); return; }
    setError(null);
    setIsOptimizing(true);
    setExpandedIdx(null);
    try {
      const response = await callVRPSolver(spots, vehicles, gears, selectedConfig);
      if (response.success && response.solution) {
        setSolution(response.solution);
        onSolutionReady?.();
      } else {
        setError(response.error || "Erreur lors de l'optimisation");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erreur inconnue');
    } finally {
      setIsOptimizing(false);
    }
  };

  const getColorHex = (color: string) => {
    const colorMap: Record<string, string> = {
      'indigo-500': '#6366f1', 'emerald-500': '#10b981', 'amber-500': '#f59e0b',
      'rose-500': '#f43f5e', 'cyan-500': '#06b6d4', 'violet-500': '#8b5cf6',
      'orange-500': '#f97316', 'teal-500': '#14b8a6',
    };
    return colorMap[color] || '#60a5fa';
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

        {/* Serveur indisponible */}
        {serverHealth === false && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-3 flex items-start gap-3">
            <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
            <div className="text-sm">
              <p className="font-semibold text-red-900">Serveur indisponible</p>
              <p className="text-red-800 text-xs">Le serveur d'optimisation (http://localhost:5000) n'est pas accessible.</p>
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
          <label className="text-xs font-semibold text-gray-700 uppercase tracking-wider">
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
                <div className="font-semibold text-sm text-gray-900">{cfg.label}</div>
                <div className="text-xs text-gray-600">{cfg.description}</div>
              </button>
            ))}
          </div>
        </div>

        {/* Bouton Optimiser */}
        <Button
          onClick={handleOptimize}
          disabled={isOptimizing || !spots.length || !vehicles.length}
          className="w-full bg-white hover:bg-gray-100 text-gray-500"
        >
          {isOptimizing ? (
            <><Loader className="w-4 h-4 mr-2 animate-spin" />Optimisation en cours...</>
          ) : (
            <><Zap className="w-4 h-4 mr-2" />{solution ? "Relancer l'optimisation" : "Lancer l'Optimisation"}</>
          )}
        </Button>

        {/* Résultats */}
        {solution && (() => {
          const maxTime = Math.max(...solution.details_vehicules.map(v => v.temps_min), 1);

          return (
            <div className="space-y-3 pt-2 border-t border-gray-200">
              <div className="text-xs font-semibold text-gray-700 uppercase tracking-wider flex items-center gap-2">
                <TrendingUp className="w-4 h-4 text-emerald-600" />
                Résultat d'optimisation
              </div>

              {/* Stats globales */}
              <div className="bg-gradient-to-r from-blue-50 to-violet-50 rounded-lg p-3 border border-blue-200">
                <h3 className="font-semibold text-sm text-gray-900 mb-2">{solution.label ?? 'Solution optimisée'}</h3>
                <div className="grid grid-cols-4 gap-2">
                  {[
                    { label: 'Véhicules', value: solution.nb_vehicules, color: 'text-blue-600' },
                    { label: 'Trajet total', value: `${solution.temps_total_min?.toFixed(0) ?? 0} min`, color: 'text-violet-600' },
                    { label: 'Distance', value: `${solution.distance_totale_km?.toFixed(1) ?? 0} km`, color: 'text-blue-700' },
                    { label: 'Score', value: solution.objectif?.toFixed(2) ?? '0', color: 'text-violet-700' },
                  ].map((stat, i) => (
                    <div key={i} className="bg-white rounded p-2 text-center shadow-sm">
                      <div className={`text-sm font-bold ${stat.color}`}>{stat.value}</div>
                      <div className="text-xs text-gray-500">{stat.label}</div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Cartes véhicules cliquables */}
              <div className="space-y-1">
                {solution.details_vehicules.map((sv, idx) => {
                  const vehicle = vehicles.find(v => v.name === sv.nom);
                  const color = vehicle ? getColorHex(vehicle.color) : '#60a5fa';
                  const barPct = solutionBarWidths[idx] ?? 0;
                  const targetPct = Math.round((sv.temps_min / maxTime) * 100);
                  const isExpanded = expandedIdx === idx;
                  const palette = DETAIL_PALETTE[idx % DETAIL_PALETTE.length];

                  return (
                    <div key={idx} className="rounded-xl border-2 border-gray-100 overflow-hidden transition-all">
                      {/* Bande couleur + card header — cliquable */}
                      <div
                        className="cursor-pointer hover:bg-gray-50 transition-colors"
                        onClick={() => setExpandedIdx(isExpanded ? null : idx)}
                      >
                        <div className="h-1" style={{ backgroundColor: color }} />
                        <div className="p-3 bg-white">
                          <div className="flex items-center justify-between mb-2">
                            <div className="flex items-center gap-2">
                              <div className="w-3 h-3 rounded-full flex-shrink-0" style={{ backgroundColor: color }} />
                              <span className="font-bold text-gray-900 text-sm">{sv.nom}</span>
                            </div>
                            <div className="flex items-center gap-2">
                              <span className="text-xs text-gray-500 bg-gray-100 px-2 py-0.5 rounded-full">
                                {sv.destinations.length} arrêt{sv.destinations.length > 1 ? 's' : ''}
                              </span>
                              {isExpanded
                                ? <ChevronUp className="w-4 h-4 text-gray-400" />
                                : <ChevronDown className="w-4 h-4 text-gray-400" />
                              }
                            </div>
                          </div>
                          <div className="flex items-center gap-4 text-xs text-gray-600 mb-3">
                            <span className="flex items-center gap-1">
                              <Clock className="w-3 h-3" />
                              <span className="font-semibold text-gray-800">{sv.temps_min.toFixed(1)} min</span>
                            </span>
                            <span className="flex items-center gap-1">
                              <MapPin className="w-3 h-3" />
                              {sv.distance_km.toFixed(1)} km
                            </span>
                          </div>
                          <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                            <div
                              className="h-full rounded-full"
                              style={{
                                width: `${barPct}%`,
                                background: `linear-gradient(90deg, ${color}cc, ${color})`,
                                transition: 'width 0.9s cubic-bezier(0.4,0,0.2,1)',
                              }}
                            />
                          </div>
                          <div className="flex justify-between mt-1">
                            <span className="text-xs text-gray-400">Temps relatif</span>
                            <span className="text-xs font-bold" style={{ color }}>{targetPct}%</span>
                          </div>
                        </div>
                      </div>

                      {/* Panneau détail — visible si expanded */}
                      {isExpanded && sv.arrets && sv.arrets.length > 0 && (
                        <div className={`bg-gradient-to-br ${palette.bg} border-t ${palette.border} p-3 space-y-2`}>
                          <div className="flex items-center gap-1.5 mb-1">
                            <Navigation className="w-3.5 h-3.5" style={{ color: palette.accent }} />
                            <span className="text-xs font-semibold" style={{ color: palette.accentDark }}>
                              Détail de la tournée
                            </span>
                          </div>

                          {sv.arrets.map((arret, aIdx) => {
                            const isDepot = arret.action === 'Departure' || arret.action === 'Return';
                            const actionLabel: Record<string, string> = {
                              Departure: 'Départ dépôt', Return: 'Retour dépôt',
                              Delivery: 'Livraison', Recovery: 'Ramassage',
                            };
                            const actionColor: Record<string, string> = {
                              Departure: 'bg-gray-200 text-gray-600',
                              Return: 'bg-gray-200 text-gray-600',
                              Delivery: 'bg-blue-100 text-blue-700',
                              Recovery: 'bg-violet-100 text-violet-700',
                            };
                            const chargeRatio = sv.capacite_m3 > 0 && arret.load_after != null
                              ? (arret.load_after / sv.capacite_m3) * 100 : null;

                            return (
                              <div key={aIdx} className={`rounded-xl overflow-hidden border ${isDepot ? 'border-gray-200 bg-white/60' : `${palette.border} bg-white/80`}`}>
                                {/* En-tête stop */}
                                <div className="flex items-center gap-2 px-3 py-2">
                                  <span
                                    className="w-5 h-5 rounded-full flex items-center justify-center text-white font-bold flex-shrink-0 text-[10px]"
                                    style={{ backgroundColor: isDepot ? '#94a3b8' : palette.accent }}
                                  >
                                    {arret.step}
                                  </span>
                                  <div className="flex-1 min-w-0">
                                    <div className="flex items-center gap-1.5 flex-wrap">
                                      <span className="font-semibold text-xs text-gray-900 truncate">{arret.label}</span>
                                      <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${actionColor[arret.action]}`}>
                                        {actionLabel[arret.action]}
                                      </span>
                                    </div>
                                    {arret.address && (
                                      <p className="text-[10px] text-gray-400 truncate">{arret.address}</p>
                                    )}
                                  </div>
                                  {arret.arrival_time != null && (
                                    <span className="text-xs font-bold flex-shrink-0" style={{ color: palette.accentDark }}>
                                      {minToHHMM(arret.arrival_time)}
                                    </span>
                                  )}
                                </div>

                                {/* Trajet depuis précédent */}
                                {arret.travel_time_from_prev != null && arret.travel_time_from_prev > 0 && (
                                  <div className="flex items-center gap-2 px-3 pb-1 text-[10px] text-gray-500">
                                    <span>↑ trajet :</span>
                                    <span className="font-medium" style={{ color: palette.accent }}>
                                      {arret.travel_time_from_prev.toFixed(0)} min
                                    </span>
                                    {arret.distance_from_prev != null && (
                                      <span className="text-gray-400">· {arret.distance_from_prev.toFixed(1)} km</span>
                                    )}
                                  </div>
                                )}

                                {/* Fenêtre horaire */}
                                {arret.time_window_start != null && arret.time_window_end != null && !isDepot && (
                                  <div className="flex items-center gap-1.5 px-3 pb-1 text-[10px] text-gray-500">
                                    <Clock className="w-3 h-3" />
                                    <span>Fenêtre :</span>
                                    <span className="font-medium text-gray-700">
                                      {minToHHMM(arret.time_window_start)} – {minToHHMM(arret.time_window_end)}
                                    </span>
                                  </div>
                                )}

                                {/* Volume + charge */}
                                {!isDepot && arret.load_after != null && (
                                  <div className="px-3 pb-2 space-y-1">
                                    <div className="flex items-center justify-between text-[10px]">
                                      <div className="flex items-center gap-2 text-gray-600">
                                        <Package className="w-3 h-3" />
                                        <span>
                                          {arret.volume_delta !== 0 && (
                                            <span className="font-medium">
                                              {arret.volume_delta < 0 ? `−${Math.abs(arret.volume_delta).toFixed(2)}` : `+${arret.volume_delta.toFixed(2)}`} m³
                                            </span>
                                          )}
                                          {' '}→ charge : <span className="font-semibold text-gray-800">{arret.load_after.toFixed(2)} m³</span>
                                        </span>
                                      </div>
                                      {chargeRatio != null && (
                                        <span className="font-bold" style={{ color: chargeRatio > 80 ? '#ef4444' : palette.accent }}>
                                          {chargeRatio.toFixed(0)}%
                                        </span>
                                      )}
                                    </div>
                                    {chargeRatio != null && (
                                      <div className="h-1 bg-gray-100 rounded-full overflow-hidden">
                                        <div
                                          className="h-full rounded-full transition-all"
                                          style={{
                                            width: `${Math.min(chargeRatio, 100)}%`,
                                            backgroundColor: chargeRatio > 80 ? '#ef4444' : palette.accent,
                                          }}
                                        />
                                      </div>
                                    )}
                                  </div>
                                )}

                                {/* Concert info */}
                                {arret.concert && (
                                  <div className="mx-3 mb-2 rounded-lg p-2 text-[10px] space-y-0.5"
                                       style={{ backgroundColor: `${palette.accent}14`, border: `1px solid ${palette.accent}30` }}>
                                    <div className="font-semibold flex items-center gap-1" style={{ color: palette.accentDark }}>
                                      🎵 Concert — {minToHHMM(arret.concert.concert_start)}
                                      {arret.concert.concert_duration > 0 && (
                                        <span className="font-normal text-gray-500">({arret.concert.concert_duration} min)</span>
                                      )}
                                    </div>
                                    <div className="flex gap-3 text-gray-600">
                                      {arret.concert.setup_duration > 0 && (
                                        <span>Installation : {arret.concert.setup_duration} min</span>
                                      )}
                                      {arret.concert.teardown_duration > 0 && (
                                        <span>Démontage : {arret.concert.teardown_duration} min</span>
                                      )}
                                    </div>
                                    {arret.concert.instruments.length > 0 && (
                                      <div className="text-gray-600">
                                        🎸 {arret.concert.instruments.length} instrument{arret.concert.instruments.length > 1 ? 's' : ''} :&nbsp;
                                        {Object.entries(arret.concert.instrument_counts)
                                          .map(([k, n]) => `${n}× ${k}`)
                                          .join(', ')}
                                      </div>
                                    )}
                                  </div>
                                )}
                              </div>
                            );
                          })}

                          {/* Totaux */}
                          <div className={`flex justify-between items-center rounded-lg px-3 py-1.5 text-xs font-semibold border ${palette.border}`}
                               style={{ backgroundColor: `${palette.accent}18` }}>
                            <span style={{ color: palette.accentDark }}>Total trajet</span>
                            <div className="flex gap-3">
                              <span style={{ color: palette.accent }}>{sv.temps_min.toFixed(0)} min</span>
                              <span style={{ color: palette.accentDark }}>{sv.distance_km.toFixed(1)} km</span>
                            </div>
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          );
        })()}

        {/* Résumé tournées existantes (avant optimisation) */}
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
              <div className="text-xs font-semibold text-gray-700 uppercase tracking-wider">Détails par véhicule</div>
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
                    onClick={() => onSelectVehicle(selectedVehicleId === route.vehicleId ? null : route.vehicleId)}
                  >
                    <div className="h-1" style={{ backgroundColor: color }} />
                    <div className="p-3 bg-white">
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-2">
                          <div className="w-3 h-3 rounded-full flex-shrink-0" style={{ backgroundColor: color }} />
                          <span className="font-bold text-gray-900 text-sm">{vehicle.name}</span>
                        </div>
                        <span className="text-xs text-gray-500 bg-gray-100 px-2 py-0.5 rounded-full">
                          {route.stops.length} arrêts
                        </span>
                      </div>
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
