import { useState } from 'react';
import type { Spot } from '../types';
import { Card, CardContent, CardHeader, CardTitle } from './ui';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Button } from './ui/button';
import { ActionButtons } from './ui/ActionButtons';
import { MapPin, Clock, Plus, Music } from 'lucide-react';
import { useEditState } from '../hooks/useEditState';

interface SpotManagerProps {
  spots: Spot[];
  selectedSpotId: string | null;
  onSelectSpot: (id: string | null) => void;
  onAddSpot: (spot: Omit<Spot, 'id' | 'gearSelections'>) => void;
  onUpdateSpot: (spot: Spot) => void;
  onDeleteSpot: (id: string) => void;
}

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:5000';

// ✅ Remplace mockGeocode — utilise Nominatim via le backend
const geocodeAddress = async (address: string): Promise<{ lat: number; lon: number }> => {
  try {
    const response = await fetch(`${API_URL}/api/geocode`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ address }),
    });
    const data = await response.json();
    if (data.lat && data.lon) return { lat: data.lat, lon: data.lon };
  } catch (error) {
    console.error('❌ Géocodage échoué:', error);
  }
  return { lat: 0, lon: 0 }; // fallback
};

export function SpotManager({ 
  spots, 
  selectedSpotId, 
  onSelectSpot, 
  onAddSpot, 
  onUpdateSpot,
  onDeleteSpot 
}: SpotManagerProps) {
  const [isAdding, setIsAdding] = useState(false);
  const editState = useEditState<Spot>();
  const [newSpot, setNewSpot] = useState({
    name: '',
    address: '',
    openingTime: '08:00',
    closingTime: '23:00',
    concertTime: '20:00',
    concertDuration: 120,
    setupDuration: 30,
    teardownDuration: 30,
  });

  const handleSaveEdit = () => {
    editState.saveEdit((updatedSpot) => {
      onUpdateSpot(updatedSpot);
    });
  };

  // ✅ handleAdd utilise geocodeAddress
  const handleAdd = async () => {
    if (!newSpot.name || !newSpot.address) return;
    const coords = await geocodeAddress(newSpot.address);
    onAddSpot({ ...newSpot, ...coords });
    setNewSpot({ name: '', address: '', openingTime: '08:00', closingTime: '23:00', concertTime: '20:00', concertDuration: 120, setupDuration: 30, teardownDuration: 30 });
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
            const isEditing = editState.editingId === spot.id;
            
            if (isEditing && editState.editData) {
              return (
                <div
                  key={spot.id}
                  className="bg-blue-50 rounded-lg p-4 border border-blue-500 space-y-3"
                >
                  <div className="flex items-center justify-between mb-4">
                    <h4 className="font-semibold text-gray-900">Modifier: {spot.name}</h4>
                    <ActionButtons
                      onDelete={(e) => {
                        e.stopPropagation();
                        editState.cancelEdit();
                      }}
                      showDelete={true}
                    />
                  </div>

                  <div>
                    <Label className="text-gray-600 text-xs">Nom du lieu</Label>
                    <Input
                      value={editState.editData.name || ''}
                      onChange={(e: React.ChangeEvent<HTMLInputElement>) => 
                        editState.updateEdit('name', e.target.value)
                      }
                      className="bg-white border-gray-300 text-gray-900"
                    />
                  </div>

                  <div>
                    <Label className="text-gray-600 text-xs">Adresse</Label>
                    <Input
                      value={editState.editData.address || ''}
                      onChange={(e: React.ChangeEvent<HTMLInputElement>) => 
                        editState.updateEdit('address', e.target.value)
                      }
                      className="bg-white border-gray-300 text-gray-900"
                    />
                  </div>

                  <div className={`grid gap-2 ${isDepot ? 'grid-cols-2' : 'grid-cols-3'}`}>
                    <div>
                      <Label className="text-gray-600 text-xs">Ouverture</Label>
                      <Input
                        type="time"
                        value={editState.editData.openingTime || '08:00'}
                        onChange={(e: React.ChangeEvent<HTMLInputElement>) => 
                          editState.updateEdit('openingTime', e.target.value)
                        }
                        className="bg-white border-gray-300 text-gray-900"
                      />
                    </div>
                    {!isDepot && (
                      <div>
                        <Label className="text-gray-600 text-xs">Concert</Label>
                        <Input
                          type="time"
                          value={editState.editData.concertTime || '20:00'}
                          onChange={(e: React.ChangeEvent<HTMLInputElement>) => 
                            editState.updateEdit('concertTime', e.target.value)
                          }
                          className="bg-white border-gray-300 text-gray-900"
                        />
                      </div>
                    )}
                    {!isDepot && (
                      <div>
                        <Label className="text-gray-600 text-xs">Durée (min)</Label>
                        <Input
                          type="number"
                          min={0}
                          value={String(editState.editData.concertDuration ?? 120)}
                          onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                            editState.updateEdit('concertDuration', Number(e.target.value))
                          }
                          className="bg-white border-gray-300 text-gray-900"
                        />
                      </div>
                    )}
                    <div>
                      <Label className="text-gray-600 text-xs">Fermeture</Label>
                      <Input
                        type="time"
                        value={editState.editData.closingTime || '23:00'}
                        onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                          editState.updateEdit('closingTime', e.target.value)
                        }
                        className="bg-white border-gray-300 text-gray-900"
                      />
                    </div>
                    {!isDepot && (
                      <div>
                        <Label className="text-gray-600 text-xs">Installation (min)</Label>
                        <Input
                          type="number"
                          min={0}
                          value={String(editState.editData.setupDuration ?? 30)}
                          onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                            editState.updateEdit('setupDuration', Number(e.target.value))
                          }
                          className="bg-white border-gray-300 text-gray-900"
                        />
                      </div>
                    )}
                    {!isDepot && (
                      <div>
                        <Label className="text-gray-600 text-xs">Désinstallation (min)</Label>
                        <Input
                          type="number"
                          min={0}
                          value={String(editState.editData.teardownDuration ?? 30)}
                          onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                            editState.updateEdit('teardownDuration', Number(e.target.value))
                          }
                          className="bg-white border-gray-300 text-gray-900"
                        />
                      </div>
                    )}
                  </div>

                  <div className="flex gap-2 pt-2">
                    <Button
                      size="sm"
                      className="flex-1 bg-white hover:bg-gray-100 text-gray-500"
                      onClick={handleSaveEdit}
                    >
                      Enregistrer
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      className="flex-1 border-gray-300 text-gray-900 hover:bg-gray-100"
                      onClick={() => editState.cancelEdit()}
                    >
                      Annuler
                    </Button>
                  </div>
                </div>
              );
            }

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
                          {spot.concertTime && !isDepot && (
                            <span className="flex items-center gap-1">
                              <Clock className="w-3 h-3" />
                              {spot.concertTime}
                            </span>
                          )}
                          {spot.concertDuration !== undefined && !isDepot && (
                            <span className="flex items-center gap-1">
                              <Music className="w-3 h-3" />
                              {spot.concertDuration} min
                            </span>
                          )}
                      <span className="flex items-center gap-1">
                        <Music className="w-3 h-3" />
                        {spot.openingTime} - {spot.closingTime}
                      </span>
                    </div>
                  </div>
                  <ActionButtons
                    onEdit={(e) => {
                      e.stopPropagation();
                      editState.startEdit(spot);
                    }}
                    onDelete={(e) => {
                      e.stopPropagation();
                      onDeleteSpot(spot.id);
                    }}
                    showDelete={!isDepot}
                  />
                </div>
              </div>
            );
          })}
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
                <Label className="text-gray-600 text-xs">Durée (min)</Label>
                <Input
                  type="number"
                  min={0}
                  value={String(newSpot.concertDuration)}
                  onChange={(e: React.ChangeEvent<HTMLInputElement>) => setNewSpot({ ...newSpot, concertDuration: Number(e.target.value) })}
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
                className="flex-1 bg-white hover:bg-gray-100 text-gray-500"
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
