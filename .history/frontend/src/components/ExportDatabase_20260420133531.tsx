import { Button } from './ui/button';
import { Download } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from './ui';
import * as XLSX from 'xlsx';
import { useState } from 'react';

interface Venue {
  id: string;
  name: string;
  address: string;
  timeWindow: [number, number];
  lat: number;
  lon: number;
  demand: number;
  instruments?: string;
  concertDuration?: number;
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
  const [loading, setLoading] = useState(false);
  const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:3001';

  /**
   * Appelle GET /api/export/all → télécharge base_complete.csv
   */
  const handleExportDatabaseCSV = async () => {
    try {
      setLoading(true);
      const response = await fetch(`${API_URL}/api/export/all`);
      if (!response.ok) throw new Error(`Erreur ${response.status}`);

      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `base_complete_${new Date().toISOString().split('T')[0]}.csv`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
    } catch (error) {
      console.error('❌ Export error:', error);
      alert('❌ Impossible de télécharger la base de données');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card className="bg-white border-gray-200">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Download className="w-5 h-5 text-blue-600" />
          Export Base de Données
        </CardTitle>
      </CardHeader>
      <CardContent>
        {/* ✅ Bouton unique CSV */}
        <Button
          size="sm"
          className="w-full bg-white border border-gray-300 hover:bg-gray-50 text-black"
          onClick={handleExportDatabaseCSV}
          disabled={loading}
        >
          <Download className="w-4 h-4 mr-2" />
          {loading ? 'Export en cours...' : 'Exporter en CSV'}
        </Button>
      </CardContent>
    </Card>
  );
}
