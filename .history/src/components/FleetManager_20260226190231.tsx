import { useState } from 'react';
import type { Vehicle, VehicleType } from '../types';
import { Card, CardContent, CardHeader, CardTitle } from './ui';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Button } from './ui/button';
import { ActionButtons } from './ui/ActionButtons';
import { Truck, Car, Van, Plus } from 'lucide-react';
import { useEditState } from '../hooks/useEditState';

interface FleetManagerProps {
  vehicles: Vehicle[];
  onChange: (vehicles: Vehicle[]) => void;
}

const VEHICLE_TYPES = [
  { value: 'car' as VehicleType, label: 'Voiture', icon: Car, defaultVolume: 3 },
  { value: 'van' as VehicleType, label: 'Camionette', icon: Van, defaultVolume: 15 },
  { value: 'truck' as VehicleType, label: 'Camion', icon: Truck, defaultVolume: 35 },
];

const COLORS = [
  'indigo-500', 'emerald-500', 'amber-500', 'rose-500', 
  'cyan-500', 'violet-500', 'orange-500', 'teal-500'
];

const getTypeColor = (type: VehicleType) => {
  switch (type) {
    case 'car': return 'text-blue-600 bg-blue-50';
    case 'van': return 'text-amber-600 bg-amber-50';
    case 'truck': return 'text-emerald-600 bg-emerald-50';
  }
};

export function FleetManager({ vehicles, onChange }: FleetManagerProps) {
  const [isAdding, setIsAdding] = useState(false);
  const editState = useEditState<Vehicle>();
  const [newVehicle, setNewVehicle] = useState({
    name: '',
    type: 'van' as VehicleType,
    capacity: 15,
  });

  const handleAdd = () => {
    if (!newVehicle.name) return;

    // Auto-assign color based on current count
    const colorIndex = vehicles.length % COLORS.length;
    
    const vehicle: Vehicle = {
      id: `v-${Date.now()}`,
      name: newVehicle.name,
      type: newVehicle.type,
      capacity: newVehicle.capacity,
      color: COLORS[colorIndex],
    };

    onChange([...vehicles, vehicle]);

    setNewVehicle({
      name: '',
      type: 'van',
      capacity: 15,
    });
    setIsAdding(false);
  };

  const handleDelete = (id: string) => {
    onChange(vehicles.filter(v => v.id !== id));
  };

  const handleUpdate = (updatedVehicle: Vehicle) => {
    const updatedVehicles = vehicles.map(v => 
      v.id === updatedVehicle.id ? updatedVehicle : v
    );
    onChange(updatedVehicles);
  };

  const handleTypeChange = (type: VehicleType) => {
    const typeConfig = VEHICLE_TYPES.find(t => t.value === type);
    setNewVehicle({
      ...newVehicle,
      type,
      capacity: typeConfig?.defaultVolume || 15,
    });
  };

  return (
    <Card className="bg-white border-gray-200">
      <CardHeader>
        <CardTitle className="text-gray-900 flex items-center gap-2">
          <Truck className="w-5 h-5 text-blue-600" />
          Flotte de Véhicules
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2">
          {vehicles.map((vehicle) => {
            const typeConfig = VEHICLE_TYPES.find(t => t.value === vehicle.type);
            const TypeIcon = typeConfig?.icon || Truck;
            const isEditing = editState.editingId === vehicle.id;

            if (isEditing && editState.editData) {
              const editType = (editState.editData.type || vehicle.type) as VehicleType;
              return (
                <div
                  key={vehicle.id}
                  className="bg-blue-50 rounded-lg p-4 border border-blue-500 space-y-3"
                >
                  <div className="flex items-center justify-between mb-4">
                    <h4 className="font-semibold text-gray-900">Modifier: {vehicle.name}</h4>
                    <button
                      onClick={() => editState.cancelEdit()}
                      className="text-gray-500 hover:text-gray-700 text-lg"
                    >
                      ×
                    </button>
                  </div>

                  <div>
                    <Label className="text-gray-600 text-xs">Plaque d'immatriculation</Label>
                    <Input
                      value={editState.editData.name || ''}
                      onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                        editState.updateEdit('name', e.target.value)
                      }
                      placeholder="Ex: AB-123-CD"
                      className="bg-white border-gray-300 text-gray-900 uppercase"
                    />
                  </div>

                  <div>
                    <Label className="text-gray-600 text-xs mb-2 block">Type de véhicule</Label>
                    <div className="grid grid-cols-3 gap-2">
                      {VEHICLE_TYPES.map((type) => {
                        const TypeEditIcon = type.icon;
                        return (
                          <button
                            key={type.value}
                            type="button"
                            onClick={() => {
                              editState.updateEdit('type', type.value);
                              editState.updateEdit('capacity', type.defaultVolume);
                            }}
                            className={`
                            p-2 rounded-lg border flex flex-col items-center gap-1 transition-all
                            ${editType === type.value
                              ? 'bg-blue-100 border-blue-500 text-blue-900'
                              : 'bg-white border-gray-200 text-gray-600 hover:border-blue-300'}
                            `}
                          >
                            <TypeEditIcon className="w-4 h-4" />
                            <span className="text-[10px]">{type.label}</span>
                          </button>
                        );
                      })}
                    </div>
                  </div>

                  <div>
                    <Label className="text-gray-600 text-xs">Volume disponible (m³)</Label>
                    <Input
                      type="number"
                      value={editState.editData.capacity || 0}
                      onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                        editState.updateEdit('capacity', parseInt(e.target.value) || 0)
                      }
                      className="bg-white border-gray-300 text-gray-900"
                    />
                  </div>

                  <div className="flex gap-2 pt-2">
                    <Button
                      size="sm"
                      className="flex-1 bg-green-600 hover:bg-green-700 !text-white"
                      onClick={() => editState.saveEdit(handleUpdate)}
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
                key={vehicle.id}
                className="p-3 rounded-lg border bg-gray-50 border-gray-200 hover:border-gray-300 transition-all"
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <TypeIcon className="w-4 h-4 text-gray-600" />
                      <h4 className="font-medium text-gray-900">{vehicle.name}</h4>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className={`text-[10px] px-2 py-0.5 rounded-full font-medium ${getTypeColor(vehicle.type)}`}>
                        {typeConfig?.label}
                      </span>
                      <span className="text-xs text-gray-600">
                        {vehicle.capacity}m³
                      </span>
                    </div>
                  </div>
                  <ActionButtons
                    onEdit={(e) => {
                      e.stopPropagation();
                      editState.startEdit(vehicle);
                    }}
                    onDelete={(e) => {
                      e.stopPropagation();
                      handleDelete(vehicle.id);
                    }}
                  />
                </div>
              </div>
            );
          })}
        </div>

        {isAdding ? (
          <div className="bg-gray-50 rounded-lg p-4 border border-gray-200 space-y-3">
            <div>
              <Label className="text-gray-600 text-xs">Plaque d'immatriculation</Label>
              <Input
                value={newVehicle.name}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => setNewVehicle({ ...newVehicle, name: e.target.value })}
                placeholder="Ex: AB-123-CD"
                className="bg-white border-gray-300 text-gray-900 uppercase"
              />
            </div>
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 mt-1">
                {VEHICLE_TYPES.map((type) => {
                    const TypeIcon = type.icon;
                    return (
                    <button
                        key={type.value}
                        type="button"
                        onClick={() => handleTypeChange(type.value)}
                        className={`
                        p-2 rounded-lg border flex flex-col items-center gap-1 transition-all
                        ${newVehicle.type === type.value
                            ? 'bg-blue-50 border-blue-500 text-blue-900'
                            : 'bg-white border-gray-200 text-gray-600 hover:border-blue-300'}
                        `}
                    >
                        <TypeIcon className="w-4 h-4" />
                        <span className="text-[10px]">{type.label}</span>
                    </button>
                    );
                })}
                </div>
            <div>
              <Label className="text-gray-600 text-xs">Volume disponible (m³)</Label>
              <Input
                type="number"
                value={newVehicle.capacity}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => setNewVehicle({ ...newVehicle, capacity: parseInt(e.target.value) || 0 })}
                className="bg-white border-gray-300 text-gray-900"
              />
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
            Ajouter un véhicule
          </Button>
        )}
      </CardContent>
    </Card>
  );
}
