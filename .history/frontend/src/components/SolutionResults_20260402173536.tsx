import { useState, useEffect } from 'react';
import type { GearItem, Spot, Vehicle } from '../types';
import type { VRPSolution } from '../utils/vrp-solver';
import { Card, CardContent, CardHeader, CardTitle } from './ui';
import { CalendarClock, Clock, MapPin, Navigation, Package, TrendingUp, X, Printer } from 'lucide-react';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:5000';

const downloadPdf = async () => {
  const res = await fetch(`${API_URL}/api/solution/pdf`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: 'Erreur inconnue' }));
    alert(`Impossible de générer le PDF : ${err.error ?? err}`);
    return;
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'resume_tournee.pdf';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
};

const DETAIL_PALETTE = [
  { bg: 'from-blue-50 to-violet-50', border: 'border-blue-200', accent: '#3b82f6', accentDark: '#1d4ed8' },
  { bg: 'from-violet-50 to-blue-50', border: 'border-violet-200', accent: '#7c3aed', accentDark: '#5b21b6' },
  { bg: 'from-indigo-50 to-blue-50', border: 'border-indigo-200', accent: '#4f46e5', accentDark: '#3730a3' },
  { bg: 'from-blue-50 to-indigo-50', border: 'border-blue-200', accent: '#2563eb', accentDark: '#1e40af' },
];

const minToHHMM = (min: number): string => {
  const h = Math.floor(min / 60) % 24;
  const m = Math.round(min % 60);
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`;
};

const addMinutesToTime = (time: string, minutesToAdd: number): string => {
  const [hours, minutes] = time.split(':').map(Number);
  if (Number.isNaN(hours) || Number.isNaN(minutes)) return time;
  const total = hours * 60 + minutes + minutesToAdd;
  const nextHours = Math.floor(total / 60) % 24;
  const nextMinutes = total % 60;
  return `${String(nextHours).padStart(2, '0')}:${String(nextMinutes).padStart(2, '0')}`;
};

const getColorHex = (color: string): string => {
  const colorMap: Record<string, string> = {
    'indigo-500': '#6366f1', 'emerald-500': '#10b981', 'amber-500': '#f59e0b',
    'rose-500': '#f43f5e', 'cyan-500': '#06b6d4', 'violet-500': '#8b5cf6',
    'orange-500': '#f97316', 'teal-500': '#14b8a6',
  };
  return colorMap[color] || '#60a5fa';
};

const hexToRgba = (hex: string, alpha: number): string => {
  const normalized = hex.replace('#', '');
  const value = normalized.length === 3
    ? normalized.split('').map((char) => char + char).join('')
    : normalized;

  const red = parseInt(value.slice(0, 2), 16);
  const green = parseInt(value.slice(2, 4), 16);
  const blue = parseInt(value.slice(4, 6), 16);

  return `rgba(${red}, ${green}, ${blue}, ${alpha})`;
};

const getVehicleMaxOccupancy = (vehicle: VRPSolution['details_vehicules'][number]) => {
  const capacity = vehicle.capacite_m3 || 0;
  let peakLoad = 0;

  for (const stop of vehicle.arrets ?? []) {
    const arrivalLoad = Math.max(0, stop.load_after ?? 0);
    const departureLoad = Math.max(0, arrivalLoad + (stop.volume_delta ?? 0));
    peakLoad = Math.max(peakLoad, arrivalLoad, departureLoad);
  }

  const boundedPeakLoad = capacity > 0 ? Math.min(peakLoad, capacity) : peakLoad;
  const peakPct = capacity > 0 ? Math.round((boundedPeakLoad / capacity) * 100) : 0;

  return {
    peakLoad: boundedPeakLoad,
    peakPct,
    capacity,
  };
};

interface SolutionResultsProps {
  solution: VRPSolution | null;
  vehicles: Vehicle[];
  spots: Spot[];
  gears: GearItem[];
  onSelectMapVehicle?: (plate: string | null) => void;
}

type SelectedPanel =
  | { type: 'vehicle'; index: number }
  | { type: 'concerts' }
  | null;

type ConcertSummaryItem = {
  id: string;
  name: string;
  concertTime: string;
  concertDuration: number;
  setupDuration: number;
  teardownDuration: number;
  instrumentsLabel: string;
};

export function SolutionResults({ solution, vehicles, spots, gears, onSelectMapVehicle }: SolutionResultsProps) {
  const [selectedPanel, setSelectedPanel] = useState<SelectedPanel>(null);
  const [barWidths, setBarWidths] = useState<Record<number, number>>({});

  useEffect(() => {
    setSelectedPanel(null);
    onSelectMapVehicle?.(null);
    if (!solution) { setBarWidths({}); return; }
    setBarWidths({});
    const maxTime = Math.max(...solution.details_vehicules.map(v => v.temps_min));
    const timer = setTimeout(() => {
      const widths: Record<number, number> = {};
      solution.details_vehicules.forEach((v, idx) => {
        widths[idx] = maxTime > 0 ? Math.round((v.temps_min / maxTime) * 100) : 0;
      });
      setBarWidths(widths);
    }, 120);
    return () => clearTimeout(timer);
  }, [solution]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!solution) return null;

  const availableVehicles = vehicles.filter((vehicle) => vehicle.isAvailable !== false);
  const usedVehicleCount = solution.nb_vehicules ?? solution.details_vehicules.length;
  const gearNameById = new Map(gears.map((gear) => [gear.id, gear.name]));
  const concerts: ConcertSummaryItem[] = [...spots]
    .filter((spot) => spot.id !== 'depot-permanent')
    .sort((left, right) => (left.concertTime ?? '').localeCompare(right.concertTime ?? ''))
    .map((spot) => {
      const instruments = spot.gearSelections
        .filter((selection) => selection.quantity > 0)
        .map((selection) => `${selection.quantity}x ${gearNameById.get(selection.gearId) ?? selection.gearId}`);

      return {
        id: spot.id,
        name: spot.name,
        concertTime: spot.concertTime ?? '--:--',
        concertDuration: spot.concertDuration ?? 0,
        setupDuration: spot.setupDuration ?? 0,
        teardownDuration: spot.teardownDuration ?? 0,
        instrumentsLabel: instruments.join('  |  '),
      };
    });

  const maxTime = Math.max(...solution.details_vehicules.map(v => v.temps_min), 1);
  const selectedVehicleIndex = selectedPanel?.type === 'vehicle' ? selectedPanel.index : null;
  const showConcertsPanel = selectedPanel?.type === 'concerts';
  const sv = selectedVehicleIndex !== null ? solution.details_vehicules[selectedVehicleIndex] : null;
  const palette = selectedVehicleIndex !== null ? DETAIL_PALETTE[selectedVehicleIndex % DETAIL_PALETTE.length] : DETAIL_PALETTE[0];
  const selectedVehicle = sv ? vehicles.find(v => v.name === sv.nom) : null;
  const selectedColor = selectedVehicle ? getColorHex(selectedVehicle.color) : '#60a5fa';

  const handleSelect = (idx: number, plate: string) => {
    const next = selectedVehicleIndex === idx ? null : { type: 'vehicle' as const, index: idx };
    setSelectedPanel(next);
    onSelectMapVehicle?.(next !== null ? plate : null);
  };

  const handleConcertsSelect = () => {
    const isOpen = selectedPanel?.type === 'concerts';
    setSelectedPanel(isOpen ? null : { type: 'concerts' });
    onSelectMapVehicle?.(null);
  };

  return (
    <>
      {/* ── Carte principale : liste des véhicules ── */}
      <Card className="bg-white border-gray-200">
        <CardHeader className="pb-2">
          <div className="flex items-center justify-between">
            <CardTitle className="text-gray-900 flex items-center gap-2 text-sm">
              <TrendingUp className="w-4 h-4 text-emerald-600" />
              Résultat d'optimisation
            </CardTitle>
            <button
              onClick={downloadPdf}
              className="flex items-center gap-1.5 text-xs text-gray-500 hover:text-gray-900 bg-gray-100 hover:bg-gray-200 px-2.5 py-1.5 rounded-lg transition-colors"
              title="Télécharger le résumé en PDF"
            >
              <Printer className="w-3.5 h-3.5" />
              Télécharger le résumé
            </button>
          </div>
        </CardHeader>
        <CardContent className="space-y-3 pt-0">

          {/* Stats globales */}
          <div className="rounded-2xl border border-gray-200 bg-gray-50 p-3">
            <h3 className="font-semibold text-sm text-gray-900 mb-2">{solution.label ?? 'Solution optimisée'}</h3>
            <div className="grid grid-cols-2 gap-2">
              {[
                { label: 'Véhicules utilisés', value: `${usedVehicleCount}/${availableVehicles.length}`, color: 'text-violet-700' },
                { label: 'Concerts', value: concerts.length, color: 'text-violet-600' },
                { label: 'Trajet total', value: `${solution.temps_total_min?.toFixed(0) ?? 0} min`, color: 'text-gray-900' },
                { label: 'Distance', value: `${solution.distance_totale_km?.toFixed(1) ?? 0} km`, color: 'text-gray-700' },
              ].map((stat, i) => (
                <div key={i} className="rounded-xl border border-gray-200 bg-white p-3 text-center shadow-sm">
                  <div className={`text-sm font-bold ${stat.color}`}>{stat.value}</div>
                  <div className="text-xs text-gray-500">{stat.label}</div>
                </div>
              ))}
            </div>
          </div>

          {/* Carte concerts + cartes véhicules */}
          <div className="grid grid-cols-2 gap-2">
            <div
              className="rounded-xl overflow-hidden border-2 cursor-pointer transition-all col-span-2"
              style={{
                borderColor: showConcertsPanel ? '#7c3aed' : '#e5e7eb',
                boxShadow: showConcertsPanel ? '0 0 0 1px rgba(124,58,237,0.22), 0 8px 24px rgba(124,58,237,0.12)' : undefined,
              }}
              onClick={handleConcertsSelect}
            >
              <div className="h-1 bg-violet-600" />
              <div className={`p-4 transition-colors ${showConcertsPanel ? 'bg-violet-50' : 'bg-gray-50 hover:bg-gray-100'}`}>
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <CalendarClock className="w-4 h-4 text-violet-700" />
                      <span className="font-bold text-gray-900 text-sm uppercase tracking-[0.18em]">Concerts</span>
                    </div>
                    <p className="mt-1 text-xs text-gray-600">
                      Vue par concert avec horaires, durees et instruments a livrer.
                    </p>
                  </div>
                  <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full ${showConcertsPanel ? 'bg-violet-100 text-violet-700' : 'bg-white text-gray-500 border border-gray-200'}`}>
                    {showConcertsPanel ? 'Ouvert' : 'Ouvrir'}
                  </span>
                </div>
                <div className="mt-3 flex flex-wrap items-center gap-2 text-xs">
                  <span className="rounded-full bg-white px-2.5 py-1 text-violet-700 border border-violet-200 font-semibold">
                    {concerts.length} concert{concerts.length > 1 ? 's' : ''}
                  </span>
                  <span className="rounded-full bg-white px-2.5 py-1 text-gray-600 border border-gray-200">
                    {concerts.reduce((sum, concert) => sum + (concert.instrumentsLabel ? concert.instrumentsLabel.split('  |  ').length : 0), 0)} lignes instrument
                  </span>
                </div>
              </div>
            </div>

            {solution.details_vehicules.map((v, idx) => {
              const vehicle = vehicles.find(veh => veh.name === v.nom);
              const color = vehicle ? getColorHex(vehicle.color) : '#60a5fa';
              const barPct = barWidths[idx] ?? 0;
              const targetPct = Math.round((v.temps_min / maxTime) * 100);
              const isSelected = selectedVehicleIndex === idx;
              const occupancy = getVehicleMaxOccupancy(v);

              return (
                <div
                  key={idx}
                  className="rounded-xl overflow-hidden border-2 cursor-pointer transition-all"
                  style={{
                    borderColor: isSelected ? color : '#f3f4f6',
                    boxShadow: isSelected ? `0 0 0 1px ${color}40, 0 2px 8px ${color}20` : undefined,
                  }}
                  onClick={() => handleSelect(idx, v.nom)}
                >
                  <div className="h-1" style={{ backgroundColor: color }} />
                  <div className={`p-3 transition-colors ${isSelected ? 'bg-gray-50' : 'bg-white hover:bg-gray-50'}`}>
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-2">
                        <div className="w-3 h-3 rounded-full flex-shrink-0" style={{ backgroundColor: color }} />
                        <span className="font-bold text-gray-900 text-sm">{v.nom}</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="text-xs text-gray-500 bg-gray-100 px-2 py-0.5 rounded-full">
                          {v.destinations.length} arrêt{v.destinations.length > 1 ? 's' : ''}
                        </span>
                        <span
                          className="text-[10px] font-semibold px-2 py-0.5 rounded-full transition-colors"
                          style={isSelected
                            ? { backgroundColor: `${color}20`, color }
                            : { backgroundColor: '#f3f4f6', color: '#9ca3af' }
                          }
                        >
                          {isSelected ? 'Sélectionné' : 'Détails'}
                        </span>
                      </div>
                    </div>
                    <div className="flex items-center gap-4 text-xs text-gray-600 mb-3">
                      <span className="flex items-center gap-1">
                        <Clock className="w-3 h-3" />
                        <span className="font-semibold text-gray-800">{v.temps_min.toFixed(1)} min</span>
                      </span>
                      <span className="flex items-center gap-1">
                        <MapPin className="w-3 h-3" />
                        {v.distance_km.toFixed(1)} km
                      </span>
                    </div>
                    <div className="space-y-2 mb-1">
                      <div>
                        <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                          <div
                            className="h-full rounded-full"
                            style={{
                              width: `${barPct}%`,
                              background: `linear-gradient(90deg, ${hexToRgba(color, 0.68)}, ${hexToRgba(color, 0.92)})`,
                              transition: 'width 0.9s cubic-bezier(0.4,0,0.2,1)',
                            }}
                          />
                        </div>
                        <div className="flex justify-between mt-1">
                          <span className="text-xs text-gray-400">Temps relatif</span>
                          <span className="text-xs font-bold" style={{ color }}>{targetPct}%</span>
                        </div>
                      </div>
                      <div>
                        <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                          <div
                            className="h-full rounded-full"
                            style={{
                              width: `${occupancy.peakPct}%`,
                              background: `linear-gradient(90deg, ${hexToRgba(color, 0.88)}, ${color})`,
                              transition: 'width 0.9s cubic-bezier(0.4,0,0.2,1)',
                            }}
                          />
                        </div>
                        <div className="flex justify-between mt-1">
                          <span className="text-xs text-gray-400">Occupation max</span>
                          <span className="text-xs font-bold" style={{ color }}>{occupancy.peakPct}%</span>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </CardContent>
      </Card>

      {/* ── Panneau détail : affiché en dessous de la carte quand un véhicule est sélectionné ── */}
      {showConcertsPanel && (
        <Card className="bg-white border-gray-200 overflow-hidden">
          <div className="h-1.5 bg-violet-600" />
          <CardHeader className="pb-2 pt-3 relative">
            <div className="flex items-center justify-between pr-8">
              <CardTitle className="text-gray-900 flex items-center gap-2 text-sm">
                <CalendarClock className="w-4 h-4 text-violet-700" />
                <span className="text-violet-700">Concerts</span>
                <span className="text-gray-400 font-normal text-xs">— Synthese des livraisons par date</span>
              </CardTitle>
              <button
                onClick={() => setSelectedPanel(null)}
                className="absolute right-3 top-3 p-1 rounded-full hover:bg-gray-100 text-gray-400 hover:text-gray-600 transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          </CardHeader>

          <CardContent className="pt-0 space-y-3 bg-gradient-to-b from-gray-50 to-white">
            {concerts.map((concert, index) => (
              <div key={concert.id} className="rounded-2xl border border-gray-200 bg-white px-4 py-4 shadow-sm">
                <div className="flex items-center gap-4">
                  <div className="w-36 shrink-0 self-center text-center text-sm font-bold text-violet-700">
                    {concert.concertTime}
                    {concert.concertDuration > 0 && (
                      <span className="text-violet-500 font-semibold block mt-0.5">{addMinutesToTime(concert.concertTime, concert.concertDuration)}</span>
                    )}
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-sm font-bold text-violet-700">[{index + 1}] {concert.name}</span>
                    </div>
                    <div className="mt-2 text-xs text-gray-500">
                      Duration: {concert.concertDuration}min &nbsp;|&nbsp; Setup: {concert.setupDuration}min &nbsp;|&nbsp; Teardown: {concert.teardownDuration}min
                    </div>
                    {concert.instrumentsLabel ? (
                      <div className="mt-3 text-sm font-semibold leading-6 text-violet-600 break-words">
                        {concert.instrumentsLabel}
                      </div>
                    ) : (
                      <div className="mt-3 text-sm text-gray-400 italic">Aucun instrument selectionne</div>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {sv && (
        <Card className="bg-white border-gray-200 overflow-hidden">
          {/* Bande couleur + en-tête */}
          <div className="h-1.5" style={{ backgroundColor: selectedColor }} />
          <CardHeader className="pb-2 pt-3 relative">
            <div className="flex items-center justify-between pr-8">
              <CardTitle className="text-gray-900 flex items-center gap-2 text-sm">
                <Navigation className="w-4 h-4" style={{ color: selectedColor }} />
                <span style={{ color: selectedColor }}>{sv.nom}</span>
                <span className="text-gray-400 font-normal text-xs">— Détail de la tournée</span>
              </CardTitle>
              <button
                onClick={() => { setSelectedPanel(null); onSelectMapVehicle?.(null); }}
                className="absolute right-3 top-3 p-1 rounded-full hover:bg-gray-100 text-gray-400 hover:text-gray-600 transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          </CardHeader>

          <CardContent className={`pt-0 space-y-2 bg-gradient-to-b ${palette.bg}`}>
            {sv.arrets && sv.arrets.map((arret, aIdx) => {
              const isDepot = arret.action === 'Departure' || arret.action === 'Return';
              const actionLabel: Record<string, string> = {
                Departure: 'Départ dépôt', Return: 'Retour dépôt',
                Delivery: 'Livraison', Recovery: 'Ramassage',
              };
              const actionColor: Record<string, string> = {
                Departure: 'bg-gray-200 text-gray-600', Return: 'bg-gray-200 text-gray-600',
                Delivery: 'bg-blue-100 text-blue-700', Recovery: 'bg-violet-100 text-violet-700',
              };

              return (
                <div key={aIdx} className={`rounded-xl overflow-hidden border ${isDepot ? 'border-gray-200 bg-white/60' : `${palette.border} bg-white/80`}`}>
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
                      {arret.address && <p className="text-[10px] text-gray-400 truncate">{arret.address}</p>}
                    </div>
                    {arret.arrival_time != null && (
                      <span className="text-xs font-bold flex-shrink-0" style={{ color: palette.accentDark }}>
                        {minToHHMM(arret.arrival_time)}
                      </span>
                    )}
                  </div>

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

                  {arret.time_window_start != null && arret.time_window_end != null && !isDepot && (
                    <div className="flex items-center gap-1.5 px-3 pb-1 text-[10px] text-gray-500">
                      <Clock className="w-3 h-3" />
                      <span>Fenêtre :</span>
                      <span className="font-medium text-gray-700">
                        {minToHHMM(arret.time_window_start)} – {minToHHMM(arret.time_window_end)}
                      </span>
                    </div>
                  )}

                  {!isDepot && arret.load_after != null && (
                    <div className="px-3 pb-2 space-y-1.5">
                      {(() => {
                        const cap = sv.capacite_m3;
                        // load_after from backend = load at ARRIVAL (before operation)
                        // actual departure load = load_after + volume_delta (volume_delta always negative)
                        const loadArrival   = arret.load_after;
                        const loadDeparture = arret.load_after + arret.volume_delta;
                        const ratioArrival  = cap > 0 ? Math.min((loadArrival  / cap) * 100, 100) : 0;
                        const ratioDeparture = cap > 0 ? Math.min((loadDeparture / cap) * 100, 100) : 0;
                        return (
                          <>
                            {/* Barre arrivée — bleu clair */}
                            <div>
                              <div className="flex justify-between text-[10px] mb-0.5">
                                <span className="text-blue-400 font-medium flex items-center gap-1">
                                  <Package className="w-2.5 h-2.5" /> Arrivée
                                </span>
                                <span className="font-bold text-blue-400">{ratioArrival.toFixed(0)}%</span>
                              </div>
                              <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
                                <div
                                  className="h-full rounded-full transition-all"
                                  style={{ width: `${ratioArrival}%`, backgroundColor: ratioArrival > 80 ? '#ef4444' : '#93c5fd' }}
                                />
                              </div>
                            </div>
                            {/* Barre départ — bleu foncé */}
                            <div>
                              <div className="flex justify-between text-[10px] mb-0.5">
                                <span className="text-blue-700 font-medium">Départ</span>
                                <span className="font-bold text-blue-700">{ratioDeparture.toFixed(0)}%</span>
                              </div>
                              <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
                                <div
                                  className="h-full rounded-full transition-all"
                                  style={{ width: `${ratioDeparture}%`, backgroundColor: ratioDeparture > 80 ? '#ef4444' : '#1d4ed8' }}
                                />
                              </div>
                            </div>
                          </>
                        );
                      })()}
                    </div>
                  )}

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
                        {arret.concert.setup_duration > 0 && <span>Installation : {arret.concert.setup_duration} min</span>}
                        {arret.concert.teardown_duration > 0 && <span>Démontage : {arret.concert.teardown_duration} min</span>}
                      </div>
                      {arret.concert.instruments.length > 0 && (
                        <div className="text-gray-600">
                          🎸 {arret.concert.instruments.length} instrument{arret.concert.instruments.length > 1 ? 's' : ''} :&nbsp;
                          {Object.entries(arret.concert.instrument_counts).map(([k, n]) => `${n}× ${k}`).join(', ')}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}

            {/* Total */}
            <div className={`flex justify-between items-center rounded-lg px-3 py-1.5 text-xs font-semibold border ${palette.border}`}
                 style={{ backgroundColor: `${palette.accent}18` }}>
              <span style={{ color: palette.accentDark }}>Total trajet</span>
              <div className="flex gap-3">
                <span style={{ color: palette.accent }}>{sv.temps_min.toFixed(0)} min</span>
                <span style={{ color: palette.accentDark }}>{sv.distance_km.toFixed(1)} km</span>
              </div>
            </div>
          </CardContent>
        </Card>
      )}
    </>
  );
}
