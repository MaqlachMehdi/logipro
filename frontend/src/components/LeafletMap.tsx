import React, { useEffect, useRef } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
// plugin attaches to global L
import 'leaflet-polylinedecorator';

import type { Spot, Route } from '../types';

interface LeafletMapProps {
  center?: [number, number];
  zoom?: number;
  spots?: Spot[];
  routes?: Route[];
  className?: string;
  onMapLoaded?: (map: L.Map) => void;
}

export const LeafletMap: React.FC<LeafletMapProps> = ({
  center = [48.8566, 2.3522],
  zoom = 11,
  spots = [],
  routes = [],
  className,
  onMapLoaded,
}) => {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<L.Map | null>(null);
  const markersRef = useRef<L.LayerGroup | null>(null);
  const routesRef = useRef<L.LayerGroup | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;
    if (mapRef.current) return;

    const map = L.map(containerRef.current, { preferCanvas: true }).setView([center[0], center[1]], zoom);

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; OpenStreetMap contributors'
    }).addTo(map);

    markersRef.current = L.layerGroup().addTo(map);
    routesRef.current = L.layerGroup().addTo(map);

    mapRef.current = map;
    if (onMapLoaded) onMapLoaded(map);

    return () => {
      try { map.remove(); } catch (e) {}
      mapRef.current = null;
    };
  }, [center, zoom, onMapLoaded]);

  // update markers when spots change
  useEffect(() => {
    const map = mapRef.current;
    const markers = markersRef.current;
    if (!map || !markers) return;

    markers.clearLayers();

    for (const s of spots) {
      // skip depot without coords
      if (typeof s.lat !== 'number' || typeof s.lon !== 'number') continue;

      const isDepot = s.id === 'depot-permanent';
      const markerEl = L.divIcon({
        className: isDepot ? 'vehicle-marker' : 'concert-marker',
        iconSize: isDepot ? [28, 28] : [12, 12]
      });

      const m = L.marker([s.lat, s.lon], { icon: markerEl });
      const title = `<strong>${s.name}</strong><br/>${s.address || ''}<br/>${s.concertTime || ''} ${s.concertDuration ? ('(' + s.concertDuration + ' min)') : ''}`;
      m.bindPopup(title);
      markers.addLayer(m);
    }

    // fit bounds if we have points
    const coords = spots.filter(s => typeof s.lat === 'number' && typeof s.lon === 'number').map(s => [s.lat, s.lon] as [number, number]);
    try {
      if (coords.length >= 2) {
        map.fitBounds(coords as L.LatLngExpression[], { padding: [40, 40] });
      } else if (coords.length === 1) {
        map.setView(coords[0], Math.max(map.getZoom(), 12));
      }
    } catch (e) {
      console.warn('Leaflet fit/center error', e);
    }
  }, [spots]);

  // update routes when routes change
  useEffect(() => {
    const map = mapRef.current;
    const routesLayer = routesRef.current;
    if (!map || !routesLayer) return;

    routesLayer.clearLayers();

    for (const r of routes) {
      const latlngs: L.LatLngExpression[] = [];
      for (const stop of r.stops) {
        // try to resolve stop coordinates from stop.venueId if needed
        if (typeof (stop as any).lat === 'number' && typeof (stop as any).lon === 'number') {
          latlngs.push([(stop as any).lat, (stop as any).lon]);
        } else {
          // stop may refer to venue id; skip if no coords
        }
      }

      if (latlngs.length < 2) continue;

      const poly = L.polyline(latlngs, { color: '#8b5cf6', weight: 4, opacity: 0.9 }).addTo(routesLayer);

      // add decorator arrows if plugin present
      try {
        // @ts-ignore
        if (L.polylineDecorator) {
          // @ts-ignore
          L.polylineDecorator(poly, {
            patterns: [{ offset: 12, repeat: 40, symbol: L.Symbol.arrowHead({ pixelSize: 8, polygon: false, pathOptions: { stroke: true, color: '#8b5cf6' } }) }]
          }).addTo(routesLayer);
        }
      } catch (e) {
        // ignore
      }

      poly.bindTooltip(`${r.vehicleId} — ${r.totalDistance ?? ''} km`, { className: 'route-tooltip' });
    }
  }, [routes]);

  return <div ref={containerRef} className={className || 'map-container'} style={{ width: '100%', height: '100%' }} />;
};

export default LeafletMap;
