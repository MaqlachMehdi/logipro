/* src/components/MapPlanner.tsx */
import { useEffect, useState } from 'react';
import { LeafletMap } from './LeafletMap';
import type { VehicleRoute, ConcertData } from './LeafletMap';
import type { Spot, Route, Vehicle } from '../types';

import { getVehicleHex } from '../config/vehicle-colors';

const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:5000';

interface MapPlannerProps {
	center?: [number, number];
	zoom?: number;
	spots?: Spot[];
	routes?: Route[];
	vehicles?: Vehicle[];
	accessToken?: string;
	styleUrl?: string;
	onMapLoaded?: (map: any) => void;
	solutionVersion?: number;
	filterPlate?: string | null;
}

export function MapPlanner({
	center = [48.8566, 2.3522],
	zoom = 11,
	spots = [],
	routes = [],
	vehicles = [],
	onMapLoaded,
	solutionVersion = 0,
	filterPlate,
}: MapPlannerProps) {
	const [vehicleRoutes, setVehicleRoutes] = useState<VehicleRoute[] | undefined>(undefined);
	const [concertsData, setConcertsData] = useState<ConcertData[] | undefined>(undefined);

	useEffect(() => {
		// solutionVersion === 0 means no optimization has run yet in this session.
		// Skip the fetch so that a stale summary.html from a previous session
		// doesn't show old routes on startup.
		if (solutionVersion === 0) return;

		fetch(`${API_URL}/api/solution/map-data`)
			.then((r) => r.json())
			.then((data) => {
				if (!data.success) return;

				// Replace Python-assigned colors with the Fleet Manager vehicle colors.
				// route.plate === vehicle.name (set in server.js line: plate: v.name)
				const remapped: VehicleRoute[] = (data.vehicleRoutes ?? []).map(
					(route: VehicleRoute) => {
						const match = vehicles.find((v) => v.name === route.plate);
						return match ? { ...route, color: getVehicleHex(match.color) } : route;
					},
				);

				setVehicleRoutes(remapped);
				setConcertsData(data.concertsData ?? []);
			})
			.catch(() => {
				// No solution yet — map still works without it
			});
	}, [solutionVersion]); // eslint-disable-line react-hooks/exhaustive-deps

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
				filterPlate={filterPlate}
			/>
		</div>
	);
}
