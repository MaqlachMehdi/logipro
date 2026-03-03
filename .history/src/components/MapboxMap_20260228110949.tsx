import React, { useRef, useEffect } from 'react';
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

    map.on('tileerror', (e) => {
      console.error('Mapbox tile error', e);
    });

    map.on('error', (e) => {
      console.error('Mapbox error event', e);
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

  return <div ref={mapContainer} style={{ width: '100%', height: '100%', minHeight: 400, borderRadius: 8, overflow: 'hidden' }} />;
};
