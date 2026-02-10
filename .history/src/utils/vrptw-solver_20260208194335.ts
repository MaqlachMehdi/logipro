import { Vehicle, Spot, Route, Stop } from '../types';

// Parse time string to minutes from midnight
function timeToMinutes(time: string | undefined): number {
  if (!time) return 0;
  const [hours, minutes] = time.split(':').map(Number);
  return hours * 60 + minutes;
}

// Format minutes back to time string
function minutesToTime(minutes: number): string {
  const hours = Math.floor(minutes / 60);
  const mins = minutes % 60;
  return `${hours.toString().padStart(2, '0')}:${mins.toString().padStart(2, '0')}`;
}

// Calculate distance using Haversine formula
function calculateDistance(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const R = 6371; // Earth's radius in km
  const dLat = (lat2 - lat1) * Math.PI / 180;
  const dLon = (lon2 - lon1) * Math.PI / 180;
  const a = 
    Math.sin(dLat/2) * Math.sin(dLat/2) +
    Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
    Math.sin(dLon/2) * Math.sin(dLon/2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
  return R * c;
}

interface UnassignedStop {
  spotId: string;
  spot: Spot;
  type: 'load-in' | 'load-out';
  earliest: number;
  latest: number;
  volume: number;
}

export function solveVRPTW(vehicles: Vehicle[], spots: Spot[], showLoadIn: boolean = true, showLoadOut: boolean = true): Route[] {
  const routes: Route[] = [];
  
  // Create unassigned stops from spots
  const unassignedStops: UnassignedStop[] = [];
  
  spots.forEach(spot => {
    // Calculate total volume for this spot from gear selections
    const spotVolume = spot.gearSelections.reduce((sum, sel) => {
      const gearItem = require('../utils/volume-data').GEAR_CATALOG.find((g: any) => g.id === sel.gearId);
      return sum + (gearItem?.volume || 0) * sel.quantity;
    }, 0);
    
    // Load-in stop
    if (showLoadIn) {
      unassignedStops.push({
        spotId: spot.id,
        spot,
        type: 'load-in',
        earliest: timeToMinutes(spot.openingTime),
        latest: timeToMinutes(spot.concertTime),
        volume: spotVolume,
      });
    }
    
    // Load-out stop
    if (showLoadOut) {
      unassignedStops.push({
        spotId: spot.id,
        spot,
        type: 'load-out',
        earliest: timeToMinutes(spot.concertTime),
        latest: timeToMinutes(spot.closingTime),
        volume: spotVolume,
      });
    }
  });

  // Sort by earliest time (greedy approach)
  unassignedStops.sort((a, b) => a.earliest - b.earliest);

  // Assign stops to vehicles
  const availableVehicles = [...vehicles];
  const centerLat = 48.8566;
  const centerLon = 2.3522;
  
  while (unassignedStops.length > 0 && availableVehicles.length > 0) {
    const vehicle = availableVehicles.shift();
    if (!vehicle) break;

    const stops: Stop[] = [];
    let currentVolume = 0;
    let currentTime = 8 * 60; // Start at 8:00 AM
    let totalDistance = 0;
    
    let lastLat = centerLat;
    let lastLon = centerLon;

    // Try to assign stops to this vehicle
    for (let i = unassignedStops.length - 1; i >= 0; i--) {
      const stop = unassignedStops[i];
      
      // Check capacity
      if (currentVolume + stop.volume > vehicle.capacity) {
        continue;
      }
      
      // Calculate travel time (assume 30km/h average speed in city)
      const distance = calculateDistance(lastLat, lastLon, stop.spot.lat, stop.spot.lon);
      const travelTime = (distance / 30) * 60; // minutes
      const arrivalTime = currentTime + travelTime;
      
      // Check time window
      if (arrivalTime > stop.latest) {
        continue;
      }
      
      // Assign stop
      const serviceTime = 30; // 30 minutes for loading/unloading
      stops.push({
        venueId: stop.spotId,
        type: stop.type,
        time: minutesToTime(Math.max(arrivalTime, stop.earliest)),
        volume: stop.volume,
      });
      
      currentVolume += stop.volume;
      currentTime = Math.max(arrivalTime, stop.earliest) + serviceTime;
      totalDistance += distance;
      lastLat = stop.spot.lat;
      lastLon = stop.spot.lon;
      
      // Remove from unassigned
      unassignedStops.splice(i, 1);
    }
    
    // Return to depot
    const returnDistance = calculateDistance(lastLat, lastLon, centerLat, centerLon);
    totalDistance += returnDistance;
    
    if (stops.length > 0) {
      routes.push({
        vehicleId: vehicle.id,
        stops,
        totalDistance: Math.round(totalDistance * 10) / 10,
        totalVolume: Math.round(currentVolume * 10) / 10,
        utilization: Math.round((currentVolume / vehicle.capacity) * 100),
      });
    }
  }

  return routes;
}
