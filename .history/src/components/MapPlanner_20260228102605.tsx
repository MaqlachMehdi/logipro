/* src/components/MapPlanner.tsx */
import React from 'react';
import { MapboxMap } from './MapboxMap';

interface MapPlannerProps {
	accessToken: string;
	styleUrl?: string;
	center?: [number, number];
	zoom?: number;
	terrain?: boolean;
	theme?: 'light' | 'dark';
	onMapLoaded?: (map: any) => void;
}

export function MapPlanner({
	accessToken,
	styleUrl,
	center = [2.3522, 48.8566],
	zoom = 11,
	terrain = false,
	theme = 'light',
	onMapLoaded,
}: MapPlannerProps) {
	return (
		<div style={{ width: '100%', height: 500, borderRadius: 8, overflow: 'hidden' }}>
			<MapboxMap
				accessToken={accessToken}
				styleUrl={styleUrl || (theme === 'dark' ? 'mapbox://styles/mapbox/dark-v11' : 'mapbox://styles/mapbox/light-v11')}
				center={center}
				zoom={zoom}
				terrain={terrain}
				theme={theme}
				onMapLoaded={onMapLoaded}
			/>
		</div>
	);
}
