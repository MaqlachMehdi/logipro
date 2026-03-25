/* src/components/MapPlanner.tsx */
import { useEffect, useState } from 'react';
import { LeafletMap } from './LeafletMap';
import type { VehicleRoute, ConcertData } from './LeafletMap';
import type { Spot, Route } from '../types';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:5000';

interface MapPlannerProps {
	center?: [number, number];
	zoom?: number;
	spots?: Spot[];
	routes?: Route[];
	accessToken?: string;
	styleUrl?: string;
	onMapLoaded?: (map: any) => void;
}

export function MapPlanner({
	center = [48.8566, 2.3522],
	zoom = 11,
	spots = [],
	routes = [],
	onMapLoaded,
}: MapPlannerProps) {
	const [vehicleRoutes, setVehicleRoutes] = useState<VehicleRoute[] | undefined>(undefined);
	const [concertsData, setConcertsData] = useState<ConcertData[] | undefined>(undefined);

	useEffect(() => {
		fetch(`${API_URL}/api/solution/map-data`)
			.then((r) => r.json())
			.then((data) => {
				if (data.success) {
					setVehicleRoutes(data.vehicleRoutes);
					setConcertsData(data.concertsData);
				}
			})
			.catch(() => {
				// No solution yet — map still works without it
			});
	}, []);

	return (
		<div style={{ width: '100%', height: 500, borderRadius: 8, overflow: 'hidden' }}>
			<LeafletMap
				center={center}
				zoom={zoom}
				spots={spots}
				routes={routes}
				vehicleRoutes={vehicleRoutes}
				concertsData={concertsData}
				onMapLoaded={onMapLoaded}
			/>
		</div>
	);
}
