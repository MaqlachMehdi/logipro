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

// Retourne { lat, lon } si trouvé, ou { error: string } si introuvable
const geocodeAddress = async (address: string): Promise<{ lat: number; lon: number } | { error: string }> => {
  try {
    const response = await fetch(`${API_URL}/api/geocode`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ address }),
    });
    const data = await response.json();
    if (typeof data.lat === 'number' && typeof data.lon === 'number') return { lat: data.lat, lon: data.lon };
    return { error: data.error || 'Adresse introuvable' };
  } catch {
    return { error: 'Impossible de joindre le serveur de géocodage' };
  }
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
  const [geocodeError, setGeocodeError] = useState<string | null>(null);
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

  const handleAdd = async () => {
    if (!newSpot.name || !newSpot.address) return;
    setGeocodeError(null);
    const result = await geocodeAddress(newSpot.address);
    if ('error' in result) {
      setGeocodeError(result.error);
      return;
    }
    onAddSpot({ ...newSpot, ...result });
    setNewSpot({ name: '', address: '', openingTime: '08:00', closingTime: '23:00', concertTime: '20:00', concertDuration: 120, setupDuration: 30, teardownDuration: 30 });
    setIsAdding(false);
  };

  return (
    <Card className="bg-white border-gray-200">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <MapPin className="w-5 h-5 text-red-600" />
          Lieux de Concert
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid grid-cols-2 gap-2">
          {spots.map((spot) => {
            const isDepot = spot.id === 'depot-permanent';
            const isEditing = editState.editingId === spot.id;

            if (isEditing && editState.editData) {
              return (
                <div
                  key={spot.id}
                  className="col-span-2 bg-blue-50 rounded-lg p-4 border border-blue-500 space-y-3"
                >
                  <div className="flex items-center justify-between mb-4">
                    <h4 className="app-title-subsection">Modifier: {spot.name}</h4>
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
                    ? 'col-span-2'
                    : selectedSpotId === spot.id
                    ? 'bg-blue-50 border-blue-500'
                    : 'bg-gray-50 border-gray-200 hover:border-gray-300'
                }`}
                style={
                  isDepot
                    ? { backgroundColor: 'var(--color-R-light)', borderColor: 'var(--color-R)' }
                    : undefined
                }
                onClick={() => onSelectSpot(spot.id)}
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1 min-w-0">
                    <h4 className={`app-title-subsection truncate ${
                      isDepot ? 'text-blue-600' : 'text-gray-900'
                    }`}>{spot.name}</h4>
                    <p className="text-xs text-gray-600 truncate mt-1" style={{ paddingLeft: '1em' }}>{spot.address}</p>
                    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 mt-2">
                          {spot.concertTime && !isDepot && (
                            <span className="number_subtitle">
                              <Clock />
                              {spot.concertTime}
                            </span>
                          )}
                          {spot.concertDuration !== undefined && !isDepot && (
                            <span className="number_subtitle">
                              <Music />
                              {spot.concertDuration} min
                            </span>
                          )}
                      <span className="number_subtitle">
                        <Music />
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
              <div>
                <Label className="text-gray-600 text-xs">Installation (min)</Label>
                <Input
                  type="number"
                  min={0}
                  value={String(newSpot.setupDuration)}
                  onChange={(e: React.ChangeEvent<HTMLInputElement>) => setNewSpot({ ...newSpot, setupDuration: Number(e.target.value) })}
                  className="bg-white border-gray-300 text-gray-900"
                />
              </div>
              <div>
                <Label className="text-gray-600 text-xs">Désinstallation (min)</Label>
                <Input
                  type="number"
                  min={0}
                  value={String(newSpot.teardownDuration)}
                  onChange={(e: React.ChangeEvent<HTMLInputElement>) => setNewSpot({ ...newSpot, teardownDuration: Number(e.target.value) })}
                  className="bg-white border-gray-300 text-gray-900"
                />
              </div>
            </div>
            {geocodeError && (
              <p className="text-red-500 text-xs px-1">{geocodeError}</p>
            )}
            <div className="flex gap-2 pt-2">
              <Button
                size="sm"
                className="bouton_add flex-1 bg-white hover:bg-gray-100 text-gray-900"
                onClick={handleAdd}
              >
                Ajouter
              </Button>
              <Button
                size="sm"
                variant="outline"
                className="bouton_add border-gray-300 text-gray-900 hover:bg-gray-100"
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
            className="bouton_add w-full border-dashed border-gray-300 text-gray-900 hover:text-gray-900 hover:border-blue-400 hover:bg-blue-50"
            onClick={() => { setIsAdding(true); setGeocodeError(null); }}
          >
            <Plus className="w-4 h-4 mr-2" />
            Ajouter un lieu
          </Button>
        )}
      </CardContent>
    </Card>
  );
}
