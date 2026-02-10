import { Card, CardContent, CardHeader, CardTitle } from './ui';
import { Button } from './ui/button';
import type { Route, Vehicle, Spot } from '../types';
import { Download, Copy } from 'lucide-react';

interface ExportPanelProps {
  routes: Route[];
  vehicles: Vehicle[];
  spots: Spot[];
}

export function ExportPanel({ routes, vehicles, spots }: ExportPanelProps) {
  const generateCSV = () => {
    let csv = 'Vehicle ID,Vehicle Name,Stop Type,Venue,Address,Time,Volume,Order\n';
    
    routes.forEach(route => {
      const vehicle = vehicles.find(v => v.id === route.vehicleId);
      if (!vehicle) return;

      route.stops.forEach((stop, index) => {
        const spot = spots.find(v => v.id === stop.venueId);
        csv += `${vehicle.id},${vehicle.name},${stop.type},"${spot?.name || 'Unknown'}","${spot?.address || 'Unknown'}",${stop.time},${stop.volume},${index + 1}\n`;
      });
    });

    return csv;
  };

  const downloadCSV = () => {
    const csv = generateCSV();
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `regietour-routes-${new Date().toISOString().split('T')[0]}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const generateCSharpCode = () => {
    let code = `using System.Collections.Generic;\n\nnamespace RegieTour.Models\n{\n    public class RoutePlan\n    {\n        public string VehicleId { get; set; }\n        public string VehicleName { get; set; }\n        public List<Stop> Stops { get; set; }\n    }\n\n    public class Stop\n    {\n        public string VenueId { get; set; }\n        public string VenueName { get; set; }\n        public string StopType { get; set; }\n        public string Time { get; set; }\n        public double Volume { get; set; }\n    }\n\n    public class RouteCollection\n    {\n        public List<RoutePlan> Routes { get; set; } = new List<RoutePlan>();\n`;
    
    routes.forEach(route => {
      const vehicle = vehicles.find(v => v.id === route.vehicleId);
      if (!vehicle) return;

      code += `        public RoutePlan Route_${vehicle.id.replace('-', '_')} { get; set; } = new RoutePlan\n`;
      code += `        {\n`;
      code += `            VehicleId = "${vehicle.id}",\n`;
      code += `            VehicleName = "${vehicle.name}",\n`;
      code += `            Stops = new List<Stop>\n`;
      code += `            {\n`;
      
      route.stops.forEach(stop => {
        const spot = spots.find(v => v.id === stop.venueId);
        code += `                new Stop { VenueId = "${stop.venueId}", VenueName = "${spot?.name || ''}", StopType = "${stop.type}", Time = "${stop.time}", Volume = ${stop.volume} },\n`;
      });
      
      code += `            }\n`;
      code += `        };\n`;
    });

    code += `    }\n}`;
    return code;
  };

  const copyCSharpCode = () => {
    const code = generateCSharpCode();
    navigator.clipboard.writeText(code);
  };

  return (
    <Card className="bg-white border-gray-200">
      <CardHeader>
        <CardTitle className="text-gray-900 flex items-center gap-2">
          <Download className="w-5 h-5 text-blue-600" />
          Export
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <Button
          variant="outline"
          size="sm"
          className="w-full border-gray-300 text-gray-900 hover:bg-gray-100 justify-start"
          onClick={downloadCSV}
        >
          <Download className="w-4 h-4 mr-2" />
          Télécharger CSV
        </Button>
        <Button
          variant="outline"
          size="sm"
          className="w-full border-gray-300 text-gray-900 hover:bg-gray-100 justify-start"
          onClick={copyCSharpCode}
        >
          <Copy className="w-4 h-4 mr-2" />
          Copier Code C#
        </Button>
      </CardContent>
    </Card>
  );
}
