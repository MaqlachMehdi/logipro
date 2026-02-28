import { Button } from './ui/button';
import { Download } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from './ui';
import * as XLSX from 'xlsx';

interface Venue {
  id: string;
  name: string;
  address: string;
  timeWindow: [number, number];
  lat: number;
  lon: number;
  demand: number;
  instruments?: string;
}

interface Vehicle {
  id: string;
  name: string;
  capacity: number;
  type?: string;
}

interface Gear {
  id: string;
  name: string;
  volume: number;
}

interface RouteStop {
  venueId: string;
  type: string;
  time: string;
  volume: number;
}

interface Route {
  vehicleId: string;
  stops: RouteStop[];
  totalDistance: number;
  totalVolume: number;
}

interface ExportDatabaseProps {
  vehicles: Vehicle[];
  venues: Venue[];
  gearCatalog: Gear[];
  routes: Route[];
}

export function ExportDatabase({ vehicles, venues, gearCatalog, routes }: ExportDatabaseProps) {
  type SheetCell = string | number;

  const handleExport = () => {
    const wb = XLSX.utils.book_new();

    // --- 1. FEUILLE LIEUX ---
    const lieuxData: SheetCell[][] = [
      ["Id_Lieux", "Nom", "Adresse", "HeureTot", "HeureTard", "HeureConcert", "Instruments"]
    ];

    venues.forEach((venue, index) => {
      const startHour = venue.timeWindow[0];
      const endHour = venue.timeWindow[1];
      
      const formatTime = (h: number) => `${h.toString().padStart(2, '0')}:00`;

      lieuxData.push([
        index + 1,
        venue.name,
        venue.address,
        formatTime(startHour),
        formatTime(endHour),
        formatTime(endHour + 2),
        venue.instruments || ""
      ]);
    });

    lieuxData.push([
      0,
      "Dépôt",
      "32 allée du hêtre, 77340, Pontault-Combault, France",
      "", "", "", ""
    ]);

    const wsLieux = XLSX.utils.aoa_to_sheet(lieuxData);
    XLSX.utils.book_append_sheet(wb, wsLieux, "Lieux");

    // --- 2. FEUILLE MATÉRIEL ---
    const materielData: SheetCell[][] = [
      ["Id_Instruments", "Nom", "Volume"]
    ];

    gearCatalog.forEach((gear, index) => {
      materielData.push([
        index + 1,
        gear.name,
        gear.volume
      ]);
    });

    const wsMateriel = XLSX.utils.aoa_to_sheet(materielData);
    XLSX.utils.book_append_sheet(wb, wsMateriel, "Materiel");

    // --- 3. FEUILLE VÉHICULES ---
    const vehiclesData: SheetCell[][] = [
      ["Id_Vehicule", "Plaque", "Type", "Volume"]
    ];

    vehicles.forEach((vehicle, index) => {
      vehiclesData.push([
        index + 1,
        vehicle.name,
        vehicle.type || "Van",
        vehicle.capacity
      ]);
    });

    const wsVehicles = XLSX.utils.aoa_to_sheet(vehiclesData);
    XLSX.utils.book_append_sheet(wb, wsVehicles, "Vehicules");

    // --- 4. FEUILLE ROUTES ---
    const routesData: SheetCell[][] = [
      ["Vehicule", "Lieu", "Type", "Heure", "Volume", "Distance"]
    ];

    routes.forEach(route => {
      const vehicle = vehicles.find(v => v.id === route.vehicleId);
      if (!vehicle) return;

      route.stops.forEach((stop, idx) => {
        const venue = venues.find(v => v.id === stop.venueId);
        routesData.push([
          vehicle.name,
          venue?.name || "Unknown",
          stop.type,
          stop.time,
          stop.volume,
          idx === 0 ? route.totalDistance : ""
        ]);
      });
    });

    const wsRoutes = XLSX.utils.aoa_to_sheet(routesData);
    XLSX.utils.book_append_sheet(wb, wsRoutes, "Routes");

    // Télécharger
    XLSX.writeFile(wb, `tournees-${new Date().toISOString().split('T')[0]}.xlsx`);
  };

  return (
    <Card className="bg-white border-gray-200">
      <CardHeader>
        <CardTitle className="text-gray-900 flex items-center gap-2">
          <Download className="w-5 h-5 text-blue-600" />
          Export Base de Données
        </CardTitle>
      </CardHeader>
      <CardContent>
        <Button
          size="sm"
          className="w-full bg-blue-600 hover:bg-blue-700 text-white"
          onClick={handleExport}
        >
          <Download className="w-4 h-4 mr-2" />
          Exporter en Excel
        </Button>
      </CardContent>
    </Card>
  );
}
