import { useState } from 'react';
import type { Spot } from '../types';
import { Card, CardContent, CardHeader, CardTitle } from './ui';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Button } from './ui/button';
import { MapPin, Clock, Plus, Trash2, Music } from 'lucide-react';

interface SpotManagerProps {
  spots: Spot[];
  selectedSpotId: string | null;
  onSelectSpot: (id: string | null) => void;
  onAddSpot: (spot: Omit<Spot, 'id' | 'gearSelections'>) => void;
  onDeleteSpot: (id: string) => void;
}

const mockGeocode = (address: string) => {
  let hash = 0;
  for (let i = 0; i < address.length; i++) {
    hash = address.charCodeAt(i) + ((hash << 5) - hash);
  }
  const lat = 48.8566 + (hash % 1000) / 10000; 
  const lon = 2.3522 + ((hash * 2) % 1000) / 10000;
  return { lat, lon };
};

export function SpotManager({ 
  spots, 
  selectedSpotId, 
  onSelectSpot, 
  onAddSpot, 
  onDeleteSpot 
}: SpotManagerProps) {
  const [isAdding, setIsAdding] = useState(false);
  const [newSpot, setNewSpot] = useState({
    name: '',
    address: '',
    openingTime: '08:00',
    closingTime: '23:00',
    concertTime: '20:00',
  });

  const handleAdd = () => {
    if (!newSpot.name || !newSpot.address) return;

    const coords = mockGeocode(newSpot.address);
    
    onAddSpot({
      ...newSpot,
      ...coords,
    });

    setNewSpot({
      name: '',
      address: '',
      openingTime: '08:00',
      closingTime: '23:00',
      concertTime: '20:00',
    });
    setIsAdding(false);
  };

  return (
    <Card className="bg-white border-gray-200">
      <CardHeader>
        <CardTitle className="text-gray-900 flex items-center gap-2">
          <MapPin className="w-5 h-5 text-red-600" />
          Lieux de Concert
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2">
          {spots.map((spot) => {
            const isDepot = spot.id === 'depot-permanent';
            return (
            <div
              key={spot.id}
              className={`p-3 rounded-lg border transition-all cursor-pointer ${
                isDepot
                  ? 'bg-red-50 border-red-500'
                  : selectedSpotId === spot.id
                  ? 'bg-blue-50 border-blue-500'
                  : 'bg-gray-50 border-gray-200 hover:border-gray-300'
              }`}
              onClick={() => onSelectSpot(spot.id)}
            >
              <div className="flex items-start justify-between">
                <div className="flex-1 min-w-0">
                  <h4 className={`font-medium truncate ${
                    isDepot ? 'text-blue-600' : 'text-gray-900'
                  }`}>{spot.name}</h4>
                  <p className="text-xs text-gray-600 truncate mt-1">{spot.address}</p>
                  <div className="flex items-center gap-3 mt-2 text-xs text-gray-600">
                    <span className="flex items-center gap-1">
                      <Clock className="w-3 h-3" />
                      {spot.concertTime}
                    </span>
                    <span className="flex items-center gap-1">
                      <Music className="w-3 h-3" />
                      {spot.openingTime} - {spot.closingTime}
                    </span>
                  </div>
                </div>
                {!isDepot && (
                  <Button
                    variant="ghost"
                    size="sm"
                    className="text-gray-500 hover:text-red-600 hover:bg-red-50 h-8 w-8 p-0"
                    onClick={(e: React.MouseEvent<HTMLButtonElement>) => {
                      e.stopPropagation();
                      onDeleteSpot(spot.id);
                    }}
                  >
                    <Trash2 className="w-4 h-4" />
                  </Button>
                )}
              </div>
            </div>
            );
          })
        </div>

        {isAdding ? (
          <div className="bg-gray-50 rounded-lg p-4 border border-gray-200 space-y-3">
            <div>
              <Label className="text-gray-600 text-xs">Nom du lieu</Label>
              <Input
                value={newSpot.name}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => setNewSpot({ ...newSpot, name: e.target.value })}
                placeholder="Ex: Accor Arena"
                className="bg-white border-gray-300 text-gray-900"
              />
            </div>
            <div>
              <Label className="text-gray-600 text-xs">Adresse</Label>
              <Input
                value={newSpot.address}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => setNewSpot({ ...newSpot, address: e.target.value })}
                placeholder="Ex: 8 Bd de Bercy, 75012 Paris"
                className="bg-white border-gray-300 text-gray-900"
              />
            </div>
            <div className="grid grid-cols-3 gap-2">
              <div>
                <Label className="text-gray-600 text-xs">Ouverture</Label>
                <Input
                  type="time"
                  value={newSpot.openingTime}
                  onChange={(e: React.ChangeEvent<HTMLInputElement>) => setNewSpot({ ...newSpot, openingTime: e.target.value })}
                  className="bg-white border-gray-300 text-gray-900"
                />
              </div>
              <div>
                <Label className="text-gray-600 text-xs">Concert</Label>
                <Input
                  type="time"
                  value={newSpot.concertTime}
                  onChange={(e: React.ChangeEvent<HTMLInputElement>) => setNewSpot({ ...newSpot, concertTime: e.target.value })}
                  className="bg-white border-gray-300 text-gray-900"
                />
              </div>
              <div>
                <Label className="text-gray-600 text-xs">Fermeture</Label>
                <Input
                  type="time"
                  value={newSpot.closingTime}
                  onChange={(e: React.ChangeEvent<HTMLInputElement>) => setNewSpot({ ...newSpot, closingTime: e.target.value })}
                  className="bg-white border-gray-300 text-gray-900"
                />
              </div>
            </div>
            <div className="flex gap-2 pt-2">
              <Button
                size="sm"
                className="flex-1 bg-blue-600 hover:bg-blue-700 !text-black"
                onClick={handleAdd}
              >
                Ajouter
              </Button>
              <Button
                size="sm"
                variant="outline"
                className="border-gray-300 text-gray-900 hover:bg-gray-100"
                onClick={() => setIsAdding(false)}
              >
                Annuler
              </Button>
            </div>
          </div>
        ) : (
          <Button
            variant="outline"
            size="sm"
            className="w-full border-dashed border-gray-300 text-gray-600 hover:text-gray-900 hover:border-blue-400 hover:bg-blue-50"
            onClick={() => setIsAdding(true)}
          >
            <Plus className="w-4 h-4 mr-2" />
            Ajouter un lieu
          </Button>
        )}
      </CardContent>
    </Card>
  );
}
