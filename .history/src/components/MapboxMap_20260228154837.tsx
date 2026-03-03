import React, { useRef, useEffect, useState } from 'react';
import mapboxgl from 'mapbox-gl';
import 'mapbox-gl/dist/mapbox-gl.css';

interface MapboxMapProps {
  accessToken: string;
  styleUrl: string;
  center?: [number, number];
  zoom?: number;
  terrain?: boolean;
  theme?: 'light' | 'dark';
  onMapLoaded?: (map: mapboxgl.Map) => void;
}

export const MapboxMap: React.FC<MapboxMapProps> = ({
  accessToken,
  styleUrl,
  center = [2.3522, 48.8566],
  zoom = 11,
  terrain = false,
  theme = 'light',
  onMapLoaded,
}) => {
  const mapContainer = useRef<HTMLDivElement>(null);
  const mapRef = useRef<mapboxgl.Map | null>(null);
  const [useFallback, setUseFallback] = useState(false);

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

    if (terrain) {
      map.on('style.load', () => {
        map.addSource('mapbox-dem', {
          type: 'raster-dem',
          url: 'mapbox://mapbox.mapbox-terrain-dem-v1',
          tileSize: 512,
          maxzoom: 14,
        });
        map.setTerrain({ source: 'mapbox-dem', exaggeration: 1.5 });
      });
    }

    map.on('load', () => {
      console.log('Mapbox map load event');
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

    // Apply muted green/blue palette and hide minor labels on style load
    map.on('style.load', () => {
      try {
        const st = map.getStyle ? map.getStyle() : null;
        if (!st || !Array.isArray(st.layers)) return;

        // background
        const bgLayer = st.layers.find((l: any) => l.type === 'background');
        if (bgLayer && bgLayer.id) {
          try { map.setPaintProperty(bgLayer.id, 'background-color', '#f2f7f9'); } catch (e) {}
        }

        // iterate layers and apply muted tones
        for (const layer of st.layers) {
          const id = layer.id || '';
          try {
            // water
            if (/water/i.test(id) || (layer['source-layer'] && /water/i.test(layer['source-layer']))) {
              if (layer.type === 'fill') {
                map.setPaintProperty(id, 'fill-color', '#d7eef6');
                map.setPaintProperty(id, 'fill-opacity', 0.95);
              }
            }

            // parks / green areas
            if (/park|landuse|grass|leisure|recreation/i.test(id) || (layer['source-layer'] && /park|landuse|grass|leisure|recreation/i.test(layer['source-layer']))) {
              if (layer.type === 'fill') {
                map.setPaintProperty(id, 'fill-color', '#e6f4ea');
                map.setPaintProperty(id, 'fill-opacity', 0.95);
              }
            }

            // roads - muted gray/blue
            if (/road|street|motorway|trunk|primary|secondary|tertiary|bridge/i.test(id) || (layer['source-layer'] && /road/i.test(layer['source-layer']))) {
              if (layer.type === 'line') {
                map.setPaintProperty(id, 'line-color', '#cfd8e3');
                map.setPaintProperty(id, 'line-opacity', 0.9);
              }
            }

            // reduce label clutter: hide minor POI/label layers but keep major place labels
            if (layer.type === 'symbol' && layer.layout && layer.layout['text-field']) {
              const isMajorPlace = /place-(city|town|village|country|state)/i.test(id) || /place_label|place-city|place-town/i.test(id);
              const isMinorLabel = /poi|poi_label|poi_point|poi_overlay|label|road-label|airport|rail|shield/i.test(id);
              if (isMinorLabel && !isMajorPlace) {
                try { map.setLayoutProperty(id, 'visibility', 'none'); } catch (e) {}
              }
            }
          } catch (e) {
            // ignore per-layer failures
          }
        }
      } catch (err) {
        console.error('Error applying muted palette and hiding labels', err);
      }
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
      map.remove();
      mapRef.current = null;
    };
  }, [accessToken, styleUrl, center, zoom, terrain, theme, onMapLoaded]);
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
