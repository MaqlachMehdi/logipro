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
    
    // Add 3D buildings layer when possible (uses 'composite' source typical of Mapbox styles)
    map.on('style.load', () => {
      try {
        const style = map.getStyle && map.getStyle();
        const hasComposite = style && style.sources && style.sources['composite'];
        if (!hasComposite) return;

        // avoid adding twice
        if (map.getLayer && map.getLayer('3d-buildings')) return;

        // find a good insertion point (below the first label layer)
        let labelLayerId = null;
        if (style && Array.isArray(style.layers)) {
          for (let i = 0; i < style.layers.length; i++) {
            const l = style.layers[i];
            if (l.type === 'symbol' && l.layout && l.layout['text-field']) {
              labelLayerId = l.id;
              break;
            }
          }
        }

        map.addLayer(
          {
            id: '3d-buildings',
            source: 'composite',
            'source-layer': 'building',
            filter: ['==', 'extrude', 'true'],
            type: 'fill-extrusion',
            minzoom: 15,
            paint: {
              'fill-extrusion-color': ['step', ['get', 'height'], '#dddddd', 20, '#d0d0d0', 60, '#c8c8c8'],
              'fill-extrusion-height': ['coalesce', ['get', 'height'], 0],
              'fill-extrusion-base': ['coalesce', ['get', 'min_height'], 0],
              'fill-extrusion-opacity': 0.7
            }
          },
          labelLayerId
        );
      } catch (err) {
        console.error('Erreur ajout couche 3D bâtiments', err);
      }
    });

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
