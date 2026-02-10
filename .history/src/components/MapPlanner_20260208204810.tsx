/* src/components/MapPlanner.tsx */
import { useMemo } from 'react';
import type { Route, Vehicle, Spot } from '../types';
import { Card, CardContent } from './ui';
import { MapPin } from 'lucide-react';

interface MapPlannerProps {
  routes: Route[];
  vehicles: Vehicle[];
  spots: Spot[];
  selectedVehicleId: string | null;
  showLoadIn: boolean;
  showLoadOut: boolean;
}

export function MapPlanner({
  routes,
  vehicles,
  spots,
  selectedVehicleId,
  showLoadIn,
  showLoadOut,
}: MapPlannerProps) {
  /* -------------------------------------------------
   * 1️⃣  Calcul du facteur de zoom & des offsets.
   * ------------------------------------------------- */
  const { scale, offsetX, offsetY } = useMemo(() => {
    if (spots.length === 0) {
      return { scale: 10000, offsetX: 0, offsetY: 0 };
    }

    const lats = spots.map((v) => v.lat);
    const lons = spots.map((v) => v.lon);
    const minLat = Math.min(...lats) - 0.02;
    const maxLat = Math.max(...lats) + 0.02;
    const minLon = Math.min(...lons) - 0.02;
    const maxLon = Math.max(...lons) + 0.02;

    const padding = 60;
    const width = 800 - padding * 2;
    const height = 600 - padding * 2;

    const latRange = maxLat - minLat;
    const lonRange = maxLon - minLon;

    const scale = Math.min(width / lonRange, height / latRange);

    const offsetX = padding + (width - lonRange * scale) / 2 - minLon * scale;
    const offsetY = padding + (height - latRange * scale) / 2 + maxLat * scale;

    return { scale, offsetX, offsetY };
  }, [spots]);

  /* -------------------------------------------------
   * 2️⃣  Projection géographique → coordonnées SVG.
   * ------------------------------------------------- */
  const project = (lat: number, lon: number) => ({
    x: lon * scale + offsetX,
    y: offsetY - lat * scale,
  });

  /* -------------------------------------------------
   * 3️⃣  Conversion couleur Tailwind → hexadécimal.
   * ------------------------------------------------- */
  const getColorHex = (color: string) => {
    const colorMap: Record<string, string> = {
      'indigo-500': '#6366f1',
      'emerald-500': '#10b981',
      'amber-500': '#f59e0b',
      'rose-500': '#f43f5e',
      'cyan-500': '#06b6d4',
      'violet-500': '#8b5cf6',
    };
    return colorMap[color] ?? '#64748b';
  };

  /* -------------------------------------------------
   * 4️⃣  Filtrage (si un véhicule est sélectionné).
   * ------------------------------------------------- */
  const filteredRoutes = selectedVehicleId
    ? routes.filter((r) => r.vehicleId === selectedVehicleId)
    : routes;

  /* -------------------------------------------------
   * 5️⃣  Liste plate de tous les arrêts (pour les
   *    marqueurs IN/OUT et la légende véhicule).
   * ------------------------------------------------- */
  const allStops = filteredRoutes.flatMap((route) => {
    const vehicle = vehicles.find((v) => v.id === route.vehicleId);
    return route.stops.map((stop: any) => ({
      ...stop,
      vehicleId: route.vehicleId,
      vehicleColor: vehicle?.color || 'slate-500',
      vehicleCapacity: vehicle?.capacity || 0,
    }));
  });

  /* -------------------------------------------------
   * 6️⃣  Rendu du composant.
   * ------------------------------------------------- */
  return (
    <Card className="bg-white border-gray-200 overflow-hidden w-full">
      <CardContent className="p-0">
        {/* Wrapper qui garantit qu’aucun débordement horizontal n’apparaît */}
        <div className="relative w-full h-full min-h-[300px] sm:min-h-[500px] overflow-hidden bg-white">
          <svg
            viewBox="0 0 800 600"
            className="w-full h-full max-w-full"
            preserveAspectRatio="xMidYMid meet"
          >
            {/* -------------------------------------------------
                 | Grille de fond
                 ------------------------------------------------- */}
            <defs>
              <pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">
                <path d="M 40 0 L 0 0 0 40" fill="none" stroke="#e5e7eb" strokeWidth="0.5" />
              </pattern>
            </defs>
            <rect width="800" height="600" fill="url(#grid)" />

            {/* -------------------------------------------------
                 | Dépôt (centre de Paris)
                 ------------------------------------------------- */}
            {(() => {
              const center = project(48.8566, 2.3522);
              return (
                <g>
                  <circle cx={center.x} cy={center.y} r="8" fill="#3b82f6" opacity="0.3" />
                  <circle cx={center.x} cy={center.y} r="4" fill="#3b82f6" />
                  <text
                    x={center.x + 12}
                    y={center.y + 4}
                    fill="#3b82f6"
                    fontSize="10"
                    fontWeight="600"
                  >
                    Dépôt
                  </text>
                </g>
              );
            })()}

            {/* -------------------------------------------------
                 | Lignes de route
                 ------------------------------------------------- */}
            {filteredRoutes.map((route) => {
              const vehicle = vehicles.find((v) => v.id === route.vehicleId);
              if (!vehicle) return null;

              const color = getColorHex(vehicle.color);
              const points = [
                [48.8566, 2.3522],
                ...route.stops.map((stop: any) => {
                  const spot = spots.find((v) => v.id === stop.venueId);
                  return spot ? [spot.lat, spot.lon] : null;
                }).filter(Boolean),
              ];

              const pathData = points
                .map((point, i) => {
                  if (!point) return '';
                  const projected = project(point[0], point[1]);
                  return `${i === 0 ? 'M' : 'L'} ${projected.x} ${projected.y}`;
                })
                .join(' ');

              return (
                <path
                  key={route.vehicleId}
                  d={pathData}
                  fill="none"
                  stroke={color}
                  strokeWidth="3"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  opacity="0.8"
                />
              );
            })}

            {/* -------------------------------------------------
                 | Marqueurs des lieux (IN / OUT + nom)
                 ------------------------------------------------- */}
            {spots.map((spot) => {
              const pos = project(spot.lat, spot.lon);
              const spotStops = allStops.filter((s) => s.venueId === spot.id);
              if (spotStops.length === 0) return null;

              return (
                <g key={spot.id}>
                  {/* Load‑in */}
                  {showLoadIn && spotStops.some((s) => s.type === 'load-in') && (
                    <g>
                      <circle
                        cx={pos.x}
                        cy={pos.y - 8}
                        r="8"
                        fill="#10b981"
                        stroke="#ffffff"
                        strokeWidth="2"
                        className="cursor-pointer hover:r-10 transition-all"
                      />
                      <text
                        x={pos.x}
                        y={pos.y - 5}
                        textAnchor="middle"
                        fill="white"
                        fontSize="10"
                        fontWeight="bold"
                      >
                        IN
                      </text>
                    </g>
                  )}

                  {/* Load‑out */}
                  {showLoadOut && spotStops.some((s) => s.type === 'load-out') && (
                    <g>
                      <circle
                        cx={pos.x}
                        cy={pos.y + 8}
                        r="8"
                        fill="#f43f5e"
                        stroke="#ffffff"
                        strokeWidth="2"
                        className="cursor-pointer hover:r-10 transition-all"
                      />
                      <text
                        x={pos.x}
                        y={pos.y + 11}
                        textAnchor="middle"
                        fill="white"
                        fontSize="10"
                        fontWeight="bold"
                      >
                        OUT
                      </text>
                    </g>
                  )}

                  {/* Nom du lieu */}
                  <text
                    x={pos.x}
                    y={pos.y + 28}
                    textAnchor="middle"
                    fill="#6b7280"
                    fontSize="11"
                    fontWeight="500"
                  >
                    {spot.name}
                  </text>
                </g>
              );
            })}
          </svg>
        </div>
      </CardContent>
    </Card>
  );
}
