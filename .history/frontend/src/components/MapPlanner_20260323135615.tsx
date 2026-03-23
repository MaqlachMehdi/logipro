/* src/components/MapPlanner.tsx */
import React from 'react';
import { LeafletMap } from './LeafletMap';
import type { Spot, Route } from '../types';

interface MapPlannerProps {
	center?: [number, number];
	zoom?: number;
	spots?: Spot[];
	routes?: Route[];
	onMapLoaded?: (map: any) => void;
}

export function MapPlanner({
	center = [48.8566, 2.3522],
	zoom = 11,
	spots = [],
	routes = [],
	onMapLoaded,
}: MapPlannerProps) {
	return (
		<div style={{ width: '100%', height: 500, borderRadius: 8, overflow: 'hidden' }}>
			<LeafletMap center={center} zoom={zoom} spots={spots} routes={routes} onMapLoaded={onMapLoaded} />
		</div>
	);
}
