import React, { useRef, useEffect } from 'react';
import mapboxgl from 'mapbox-gl';

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

    if (onMapLoaded) {
      map.on('load', () => onMapLoaded(map));
    }

    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, [accessToken, styleUrl, center, zoom, terrain, theme, onMapLoaded]);

  return <div ref={mapContainer} style={{ width: '100%', height: '100%', minHeight: 400, borderRadius: 8, overflow: 'hidden' }} />;
};
