import { useState, useEffect } from 'react';
import type { GearItem, Spot, Vehicle } from '../types';
import type { VRPSolution } from '../utils/vrp-solver';
import { Card, CardContent, CardHeader, CardTitle } from './ui';
import { CalendarClock, Clock, MapPin, Navigation, TrendingUp, X, Printer } from 'lucide-react';
import { getVehicleColor, hexToRgba, type VehicleColor } from '../config/vehicle-colors';

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
  const [animReady, setAnimReady] = useState(false);
  const [detailAnimReady, setDetailAnimReady] = useState(false);

  useEffect(() => {
    setDetailAnimReady(false);
    if (selectedPanel?.type === 'vehicle') {
      const t = setTimeout(() => setDetailAnimReady(true), 80);
      return () => clearTimeout(t);
    }
  }, [selectedPanel]);

  useEffect(() => {
    setSelectedPanel(null);
    onSelectMapVehicle?.(null);
    if (!solution) { setBarWidths({}); setAnimReady(false); return; }
    setBarWidths({});
    setAnimReady(false);
    const maxTime = Math.max(...solution.details_vehicules.map(v => v.temps_min));
    const timer = setTimeout(() => {
      const widths: Record<number, number> = {};
      solution.details_vehicules.forEach((v, idx) => {
        widths[idx] = maxTime > 0 ? Math.round((v.temps_min / maxTime) * 100) : 0;
      });
      setBarWidths(widths);
      setAnimReady(true);
    }, 180);
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
  const selectedVehicle = sv ? vehicles.find(v => v.name === sv.nom) : null;
  const selectedVc: VehicleColor = selectedVehicle ? getVehicleColor(selectedVehicle.color) : getVehicleColor('');
  const selectedColor = selectedVc.hex;

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
        <CardHeader className="pb-4">
          <div className="flex items-start justify-between w-full" style={{ paddingRight: '1em' }}>
            <CardTitle className="flex items-center gap-2">
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
          <div className="rounded-2xl p-3" style={{ paddingBottom: '0.5em' }}>
            <h3 className="app-title-subsection uppercase text-center" style={{ paddingTop: '0.5em', paddingBottom: '0.3em' }}>{(solution.label ?? 'Solution optimisée').toUpperCase()}</h3>
            <div className="grid grid-cols-2 gap-2">
              {[
                { label: 'Véhicules utilisés', value: `${usedVehicleCount}/${availableVehicles.length}`, color: 'text-violet-700' },
                { label: 'Concerts', value: concerts.length, color: 'text-violet-600' },
                { label: 'Trajet total', value: `${solution.temps_total_min?.toFixed(0) ?? 0} min`, color: 'text-gray-900' },
                { label: 'Distance', value: `${solution.distance_totale_km?.toFixed(1) ?? 0} km`, color: 'text-gray-700' },
              ].map((stat, i) => (
                <div key={i} className="rounded-xl border border-gray-200 p-3 text-center shadow-sm">
                  <div className={`text-sm font-bold ${stat.color}`}>{stat.value}</div>
                  <div className="app-title-subsection text-gray-500">{stat.label}</div>
                </div>
              ))}
            </div>
          </div>

          {/* Cartes concerts + véhicules – défilement horizontal */}
          <div className="flex gap-2 overflow-x-auto pb-1" style={{ scrollSnapType: 'x mandatory', scrollBehavior: 'smooth', WebkitOverflowScrolling: 'touch' }}>

            {/* Card Concerts */}
            <div
              className="rounded-xl overflow-hidden border-2 cursor-pointer transition-all flex-shrink-0"
              style={{
                width: 'calc(0.80 * (50% - 4px))',
                scrollSnapAlign: 'start',
                borderColor: showConcertsPanel ? '#7c3aed' : '#e5e7eb',
                boxShadow: showConcertsPanel ? '0 0 0 1px rgba(124,58,237,0.22), 0 8px 24px rgba(124,58,237,0.12)' : undefined,
                backgroundColor: showConcertsPanel ? '#f5f3ff' : '#f9fafb',
              }}
              onClick={handleConcertsSelect}
            >
              <div className="h-1 bg-violet-600" />
              <div className={`p-3 transition-colors ${showConcertsPanel ? 'bg-violet-50' : 'bg-gray-50 hover:bg-gray-100'}`}>
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <CalendarClock className="text-violet-700 flex-shrink-0" style={{ width: '1.3em', height: '1.3em' }} />
                      <span className="app-title-subsection uppercase tracking-[0.18em]">Concerts</span>
                    </div>
                    <p className="app-text-meta mt-1" style={{ paddingLeft: '0.5em' }}>
                      Vue par concert avec horaires, durees et instruments a livrer.
                    </p>
                  </div>
                  <div className="flex flex-col items-end gap-1" style={{ paddingTop: '0.5em', paddingRight: '0.5em' }}>
                    <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full ${showConcertsPanel ? 'bg-violet-100 text-violet-700' : 'bg-white text-gray-500 border border-gray-200'}`}>
                      {showConcertsPanel ? 'Ouvert' : 'Ouvrir'}
                    </span>
                    <span className="text-[10px] font-semibold text-violet-700">
                      {concerts.length} concert{concerts.length > 1 ? 's' : ''}
                    </span>
                    <span className="text-[10px] text-gray-500">
                      {concerts.reduce((sum, concert) => sum + (concert.instrumentsLabel ? concert.instrumentsLabel.split('  |  ').length : 0), 0)} lignes instrument
                    </span>
                  </div>
                </div>
              </div>
            </div>
            {solution.details_vehicules.map((v, idx) => {
              const vehicle = vehicles.find(veh => veh.name === v.nom);
              const vc = vehicle ? getVehicleColor(vehicle.color) : getVehicleColor('');
              const color = vc.hex;
              const barPct = barWidths[idx] ?? 0;
              const targetPct = Math.round((v.temps_min / maxTime) * 100);
              const isSelected = selectedVehicleIndex === idx;
              const occupancy = getVehicleMaxOccupancy(v);

              return (
                <div
                  key={idx}
                  className="rounded-xl overflow-hidden border-2 cursor-pointer transition-all flex-shrink-0"
                  style={{
                    width: 'calc(50% - 4px)',
                    scrollSnapAlign: 'start',
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
                        <span className="app-title-subsection">{v.nom}</span>
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
                      <span className="number_subtitle">
                        <Clock />
                        {v.temps_min.toFixed(1)} min
                      </span>
                      <span className="number_subtitle">
                        <MapPin />
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
                              transition: 'width 2.4s cubic-bezier(0.16, 1, 0.3, 1)',
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
                              width: `${animReady ? occupancy.peakPct : 0}%`,
                              background: `linear-gradient(90deg, ${hexToRgba(color, 0.88)}, ${color})`,
                              transition: 'width 2.8s cubic-bezier(0.16, 1, 0.3, 1)',
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
        <div className="rounded-xl overflow-hidden border border-gray-200 bg-white w-full">
          <div className="h-1.5 bg-violet-600" />
          <div className="px-4 pt-5 pb-3 flex items-center justify-between">
            <div className="flex items-center justify-between gap-3 w-full">
              <CardTitle className="flex items-center gap-2">
                <CalendarClock className="w-4 h-4 text-violet-700" />
                <span className="text-violet-700">Concerts</span>
                <span className="text-gray-400 font-normal text-xs">— Synthese des livraisons par date</span>
              </CardTitle>
              <button
                onClick={() => setSelectedPanel(null)}
                className="shrink-0 p-1 rounded-full hover:bg-gray-100 text-gray-400 hover:text-gray-600 transition-colors"
                aria-label="Fermer la synthese des concerts"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          </div>

          <div className="p-4 flex flex-col flex-grow pt-0 space-y-3 bg-gradient-to-b from-gray-50 to-white">
            {concerts.map((concert, index) => (
              <div key={concert.id} className="rounded-2xl border border-gray-200 bg-white px-4 py-4 shadow-sm">
                <div className="flex items-center gap-4">
                  <div className="w-36 shrink-0 self-center flex flex-col items-center justify-center text-sm font-bold text-violet-700">
                    <span>{concert.concertTime}</span>
                    {concert.concertDuration > 0 && (
                      <>
                        <div className="w-1.5 h-1.5 rounded-full my-1 bg-violet-400 " />
                        <span className="text-violet-500 font-semibold">{addMinutesToTime(concert.concertTime, concert.concertDuration)}</span>
                      </>
                    )}
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="app-title-subsection text-violet-700">[{index + 1}] {concert.name}</span>
                    </div>
                    <div className="app-text-meta mt-2">
                      Durée : {concert.concertDuration}min &nbsp;|&nbsp; Installation : {concert.setupDuration}min &nbsp;|&nbsp; Désinstallation : {concert.teardownDuration}min
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
          </div>
        </div>
      )}

      {sv && (
        <div className="rounded-xl overflow-hidden border border-gray-200 bg-white w-full">
          {/* Bande couleur véhicule */}
          <div className="h-1.5" style={{ backgroundColor: selectedColor }} />
          <CardHeader className="pb-2 pt-3 relative">
            <div className="flex items-center justify-between pr-8">
              <CardTitle className="flex items-center gap-2">
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

          <CardContent className="pt-0 pb-4">
            {sv.arrets && sv.arrets.map((arret, aIdx) => {
              const isDepot = arret.action === 'Departure' || arret.action === 'Return';
              const actionLabel: Record<string, string> = {
                Departure: 'Départ dépôt', Return: 'Retour dépôt',
                Delivery: 'Livraison', Recovery: 'Ramassage',
              };
              const isLast = aIdx === (sv.arrets?.length ?? 0) - 1;

              return (
                <div key={aIdx}>
                  {/* ── Ligne principale : pastille | contenu | heure ── */}
                  <div className="flex items-start gap-3 px-2 py-3">
                    {/* Pastille étape */}
                    <span
                      className="w-7 h-7 rounded-full flex items-center justify-center text-white font-bold flex-shrink-0 text-xs mt-0.5"
                      style={{ backgroundColor: isDepot ? '#94a3b8' : selectedVc.hex }}
                    >
                      {isDepot ? 'D' : arret.step}
                    </span>

                    {/* Contenu central */}
                    <div className="flex-1 min-w-0 space-y-1.5">
                      {/* Nom + badge action */}
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="font-bold text-sm text-gray-900">{arret.label}</span>
                        <span
                          className="text-[10px] px-1.5 py-0.5 rounded font-semibold"
                          style={isDepot
                            ? { backgroundColor: '#e5e7eb', color: '#4b5563' }
                            : { backgroundColor: selectedVc.light, color: selectedVc.dark }
                          }
                        >
                          {actionLabel[arret.action]}
                        </span>
                      </div>

                      {/* Adresse */}
                      {arret.address && (
                        <p className="text-xs text-gray-400 leading-tight">{arret.address}</p>
                      )}

                      {/* Trajet + fenêtre (une seule ligne compacte) */}
                      {(!isDepot && (arret.travel_time_from_prev || arret.time_window_start != null)) && (
                        <div className="flex items-center gap-3 text-[11px] text-gray-500 flex-wrap">
                          {arret.travel_time_from_prev != null && arret.travel_time_from_prev > 0 && (
                            <span>
                              <span style={{ color: selectedVc.hex }}>&#8599;</span>{' '}
                              {arret.travel_time_from_prev.toFixed(0)} min
                              {arret.distance_from_prev != null && <> · {arret.distance_from_prev.toFixed(1)} km</>}
                            </span>
                          )}
                          {arret.time_window_start != null && arret.time_window_end != null && (
                            <span className="flex items-center gap-1">
                              <Clock className="w-3 h-3 text-gray-400" />
                              Fenêtre : {minToHHMM(arret.time_window_start)} – {minToHHMM(arret.time_window_end)}
                            </span>
                          )}
                        </div>
                      )}

                      {/* Barres chargement arrivée / départ */}
                      {!isDepot && arret.load_after != null && (() => {
                        const cap = sv.capacite_m3;
                        const loadArrival = arret.load_after;
                        const loadDeparture = arret.load_after + arret.volume_delta;
                        const ratioArrival = cap > 0 ? Math.min((loadArrival / cap) * 100, 100) : 0;
                        const ratioDeparture = cap > 0 ? Math.min((loadDeparture / cap) * 100, 100) : 0;
                        return (
                          <div className="space-y-1" style={{ paddingTop: '0.8em', paddingBottom: '0.8em' }}>
                            <div className="flex items-center gap-2">
                              <span className="text-[10px] text-gray-400 w-12 flex-shrink-0">Arrivée</span>
                              <div className="flex-1 h-2 bg-gray-100 rounded-full overflow-hidden">
                                <div
                                  className="h-full rounded-full"
                                  style={{
                                    width: `${detailAnimReady ? ratioArrival : 0}%`,
                                    background: `linear-gradient(90deg, ${hexToRgba(selectedColor, 0.35)}, ${hexToRgba(selectedColor, 0.6)})`,
                                    transition: 'width 2s cubic-bezier(0.16, 1, 0.3, 1)',
                                  }}
                                />
                              </div>
                              <span className="text-[10px] font-bold w-8 text-right" style={{ color: hexToRgba(selectedColor, 0.7) }}>{ratioArrival.toFixed(0)}%</span>
                            </div>
                            <div className="flex items-center gap-2">
                              <span className="text-[10px] text-gray-400 w-12 flex-shrink-0">Départ</span>
                              <div className="flex-1 h-2 bg-gray-100 rounded-full overflow-hidden">
                                <div
                                  className="h-full rounded-full"
                                  style={{
                                    width: `${detailAnimReady ? ratioDeparture : 0}%`,
                                    background: `linear-gradient(90deg, ${hexToRgba(selectedColor, 0.55)}, ${hexToRgba(selectedColor, 0.85)})`,
                                    transition: 'width 2.4s cubic-bezier(0.16, 1, 0.3, 1)',
                                  }}
                                />
                              </div>
                              <span className="text-[10px] font-bold w-8 text-right" style={{ color: selectedColor }}>{ratioDeparture.toFixed(0)}%</span>
                            </div>
                          </div>
                        );
                      })()}

                      {/* Encart concert */}
                      {arret.concert && (
                        <div
                          className="rounded-lg mt-1 text-[11px] space-y-0.5"
                          style={{
                            backgroundColor: selectedVc.light,
                            borderLeft: `5px solid ${selectedVc.hex}`,
                            padding: '0.8em',
                            marginLeft: '2.5em',
                          }}
                        >
                          <div className="font-semibold" style={{ color: selectedVc.dark }}>
                            Concert — <span className="font-bold">{minToHHMM(arret.concert.concert_start)}</span>
                            {arret.concert.concert_duration > 0 && (
                              <span className="font-normal text-gray-500"> · {arret.concert.concert_duration} min</span>
                            )}
                            {arret.concert.setup_duration > 0 && (
                              <span className="font-normal text-gray-500"> · Installation : {arret.concert.setup_duration} min</span>
                            )}
                            {arret.concert.teardown_duration > 0 && (
                              <span className="font-normal text-gray-500"> · Démontage : {arret.concert.teardown_duration} min</span>
                            )}
                          </div>
                          {arret.concert.instruments.length > 0 && (
                            <div className="text-gray-600">
                              {arret.concert.instruments.length} instrument{arret.concert.instruments.length > 1 ? 's' : ''} :{' '}
                              {Object.entries(arret.concert.instrument_counts).map(([k, n]) => `${n}× ${k}`).join(', ')}
                            </div>
                          )}
                        </div>
                      )}
                    </div>

                    {/* Heure d'arrivée — alignée à droite */}
                    {arret.arrival_time != null && (
                      <span className="text-sm font-bold flex-shrink-0 tabular-nums" style={{ color: selectedVc.dark }}>
                        {minToHHMM(arret.arrival_time)}
                      </span>
                    )}
                  </div>

                  {/* Séparateur entre arrêts */}
                  {!isLast && (
                    <div className="flex justify-center py-0.5 text-gray-300">
                      <span className="text-sm">&#8595;</span>
                    </div>
                  )}
                </div>
              );
            })}

            {/* Total */}
            <div
              className="flex justify-between items-center rounded-lg mt-3 text-xs font-semibold border"
              style={{
                borderColor: hexToRgba(selectedVc.hex, 0.3),
                backgroundColor: hexToRgba(selectedVc.hex, 0.1),
                padding: '0.5em',
                paddingLeft: '1em',
                paddingRight: '1em',
                marginLeft: '0.8em',
              }}
            >
              <span className="app-title-subsection" style={{ color: selectedVc.dark, 
                paddingTop :'0.2em' , 
                paddingBottom : '0.2em'}
              }>Total trajet</span>
              <div className="flex gap-3">
                <span style={{ color: selectedVc.hex }}>{sv.temps_min.toFixed(0)} min</span>
                <span style={{ color: selectedVc.dark }}>{sv.distance_km.toFixed(1)} km</span>
              </div>
            </div>
          </CardContent>
        </div>
      )}
    </>
  );
}
