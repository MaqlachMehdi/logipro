import React, { useRef, useEffect, useState } from 'react';
import mapboxgl from 'mapbox-gl';
import 'mapbox-gl/dist/mapbox-gl.css';
import type { Spot } from '../types';
import type { VehicleRoute } from './LeafletMap';

interface MapboxMapProps {
  accessToken: string;
  styleUrl: string;
  center?: [number, number];
  zoom?: number;
  terrain?: boolean;
  theme?: 'light' | 'dark';
  spots?: Spot[];
  vehicleRoutes?: VehicleRoute[];
  filterPlate?: string | null;
  onMapLoaded?: (map: mapboxgl.Map) => void;
}

export const MapboxMap: React.FC<MapboxMapProps> = ({
  accessToken,
  styleUrl,
  center = [2.3522, 48.8566],
  zoom = 11,
  terrain = false,
  theme = 'light',
  spots = [],
  vehicleRoutes = [],
  filterPlate = null,
  onMapLoaded,
}) => {
  const mapContainer = useRef<HTMLDivElement>(null);
  const mapRef = useRef<mapboxgl.Map | null>(null);
  const markersRef = useRef<mapboxgl.Marker[]>([]);
  const [useFallback, setUseFallback] = useState(false);
  const [isMapLoaded, setIsMapLoaded] = useState(false);

  useEffect(() => {
    mapboxgl.accessToken = accessToken;
    console.log('Initializing mapbox with token', !!accessToken);
    if (!mapContainer.current) return;
    if (mapRef.current) return;

    const style = styleUrl || (theme === 'dark'
      ? 'mapbox://styles/mapbox/dark-v11'
      : 'mapbox://styles/mapbox/light-v11');

    const map = new mapboxgl.Map({
      container: mapContainer.current,
      style,
      center,
      zoom,
      antialias: true,
      pitch: terrain ? 60 : 0,
      bearing: 0,
    });
    mapRef.current = map;

    map.on('style.load', () => {
      try {
        map.setProjection({ name: 'globe' });
      } catch {
        // Keep default projection if globe isn't available for a given style/runtime.
      }

      try {
        map.setFog({
          color: 'rgb(235, 245, 255)',
          'high-color': 'rgb(220, 235, 255)',
          'horizon-blend': 0.1,
          'space-color': 'rgb(10, 15, 25)',
          'star-intensity': 0.15,
        });
      } catch {
        // Fog can fail on some styles; ignore safely.
      }

      if (terrain) {
        if (!map.getSource('mapbox-dem')) {
          map.addSource('mapbox-dem', {
            type: 'raster-dem',
            url: 'mapbox://mapbox.mapbox-terrain-dem-v1',
            tileSize: 512,
            maxzoom: 14,
          });
        }
        map.setTerrain({ source: 'mapbox-dem', exaggeration: 1.2 });
      }
    });

    map.on('load', () => {
      console.log('Mapbox map load event');
      setIsMapLoaded(true);
      if (onMapLoaded) onMapLoaded(map);
    });

    map.on('idle', () => {
      console.log('Mapbox map idle — likely finished loading tiles');
      try {
        const style = map.getStyle ? map.getStyle() : null;
        console.log('Map style info:', style && style.name ? style.name : '(no style name)', 'sources:', style ? Object.keys(style.sources || {}).length : 0);
      } catch (e) {
        console.error('Error reading style info', e);
      }
    });

    map.on('styledata', () => {
      console.log('Mapbox styledata event');
    });

    map.on('tileerror', (e) => {
      console.error('Mapbox tile error', e);
      setUseFallback(true);
    });

    map.on('error', (e) => {
      console.error('Mapbox error event', e);
      setUseFallback(true);
    });

    // After a short delay, report whether the style is considered loaded
    setTimeout(() => {
      try {
        const loaded = typeof map.loaded === 'function' ? map.loaded() : !!map.isStyleLoaded && map.isStyleLoaded();
        console.log('Map loaded() =>', loaded);
        if (map.getStyle) {
          const st = map.getStyle();
          console.log('Style sources keys:', Object.keys(st.sources || {}));
        }
      } catch (err) {
        console.error('Error checking map loaded state', err);
      }
    }, 1500);

    return () => {
      markersRef.current.forEach((marker) => marker.remove());
      markersRef.current = [];
      map.remove();
      mapRef.current = null;
      setIsMapLoaded(false);
    };
  }, [accessToken, styleUrl, center, zoom, terrain, theme, onMapLoaded]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !isMapLoaded) return;

    markersRef.current.forEach((marker) => marker.remove());
    markersRef.current = [];

    const bounds = new mapboxgl.LngLatBounds();

    for (const spot of spots) {
      if (typeof spot.lat !== 'number' || typeof spot.lon !== 'number') continue;

      const isDepot = spot.id === 'depot-permanent';
      const el = document.createElement('div');
      el.style.width = isDepot ? '18px' : '12px';
      el.style.height = isDepot ? '18px' : '12px';
      el.style.borderRadius = '9999px';
      el.style.background = isDepot ? 'var(--color-M, #6D66B7)' : 'var(--color-accent-spots, #f43f5e)';
      el.style.border = '2px solid #fff';
      el.style.boxShadow = '0 2px 8px rgba(0,0,0,0.25)';

      const marker = new mapboxgl.Marker({ element: el })
        .setLngLat([spot.lon, spot.lat])
        .setPopup(
          new mapboxgl.Popup({ offset: 16 }).setHTML(
            `<strong>${spot.name}</strong><br/>${spot.address || ''}`,
          ),
        )
        .addTo(map);

      markersRef.current.push(marker);
      bounds.extend([spot.lon, spot.lat]);
    }

    if (!bounds.isEmpty()) {
      map.fitBounds(bounds, { padding: 64, duration: 700, maxZoom: 13 });
    }
  }, [spots, isMapLoaded]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !isMapLoaded) return;

    const routesToDisplay = filterPlate
      ? vehicleRoutes.filter((route) => route.plate === filterPlate)
      : vehicleRoutes;

    const features = routesToDisplay.flatMap((route) =>
      route.segments
        .filter((segment) =>
          Array.isArray(segment.coords) &&
          segment.coords.length === 2 &&
          typeof segment.coords[0][0] === 'number' &&
          typeof segment.coords[0][1] === 'number' &&
          typeof segment.coords[1][0] === 'number' &&
          typeof segment.coords[1][1] === 'number',
        )
        .map((segment) => ({
          type: 'Feature' as const,
          properties: {
            plate: route.plate,
            color: route.color,
            from: segment.from,
            to: segment.to,
          },
          geometry: {
            type: 'LineString' as const,
            coordinates: [
              [segment.coords[0][1], segment.coords[0][0]],
              [segment.coords[1][1], segment.coords[1][0]],
            ],
          },
        })),
    );

    const geojson = {
      type: 'FeatureCollection' as const,
      features,
    };

    const sourceId = 'vrp-routes-source';
    const layerId = 'vrp-routes-layer';

    if (map.getSource(sourceId)) {
      const source = map.getSource(sourceId) as mapboxgl.GeoJSONSource;
      source.setData(geojson);
    } else {
      map.addSource(sourceId, {
        type: 'geojson',
        data: geojson,
      });

      map.addLayer({
        id: layerId,
        type: 'line',
        source: sourceId,
        layout: {
          'line-cap': 'round',
          'line-join': 'round',
        },
        paint: {
          'line-color': ['coalesce', ['get', 'color'], '#2563eb'],
          'line-width': 4,
          'line-opacity': 0.85,
        },
      });
    }
  }, [vehicleRoutes, filterPlate, isMapLoaded]);
  if (useFallback) {
    // Simple OpenStreetMap embed as fallback when Mapbox fails
    const lat = center[1];
    const lon = center[0];
    const delta = 0.03; // bbox padded around center
    const minLon = (lon - delta).toFixed(6);
    const minLat = (lat - delta).toFixed(6);
    const maxLon = (lon + delta).toFixed(6);
    const maxLat = (lat + delta).toFixed(6);
    const marker = `${lat.toFixed(6)}%2C${lon.toFixed(6)}`;
    const src = `https://www.openstreetmap.org/export/embed.html?bbox=${minLon}%2C${minLat}%2C${maxLon}%2C${maxLat}&layer=mapnik&marker=${marker}`;

    return (
      <div style={{ width: '100%', height: '100%', minHeight: 400, borderRadius: 8, overflow: 'hidden' }}>
        <div style={{ position: 'relative', width: '100%', height: '100%' }}>
          <iframe
            title="OSM fallback"
            src={src}
            style={{ border: 0, width: '100%', height: '100%' }}
            loading="lazy"
          />
          <div style={{ position: 'absolute', left: 8, bottom: 8, background: 'rgba(255,255,255,0.9)', padding: '4px 8px', borderRadius: 6, fontSize: 12 }}>
            Carte OpenStreetMap (fallback)
          </div>
        </div>
      </div>
    );
  }

  return <div ref={mapContainer} style={{ width: '100%', height: '100%', minHeight: 400, borderRadius: 8, overflow: 'hidden' }} />;
};
