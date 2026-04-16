import { useState } from 'react';
import { Plus } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { ActionButtons } from './ui/ActionButtons';

interface Gear {
  id: string;
  name: string;
  volume: number;
}

interface GearManagerProps {
  gearCatalog: Gear[];
  onAddGear: (gear: Omit<Gear, 'id'>) => void;
  onDeleteGear: (id: string) => void;
}

export function GearManager({ gearCatalog, onAddGear, onDeleteGear }: GearManagerProps) {
  const [newName, setNewName] = useState('');
  const [newVolume, setNewVolume] = useState('');
  const [newCategory, setNewCategory] = useState('');
  const [isAdding, setIsAdding] = useState(false);

  const handleAdd = () => {
    if (!newName.trim() || !newVolume) return;

    const volume = parseFloat(newVolume);
    if (isNaN(volume) || volume <= 0) return;

    onAddGear({
      name: newName,
      volume: volume
    });

    setNewName('');
    setNewVolume('');
    setNewCategory('');
    setIsAdding(false);
  };

  return (
    <Card className="bg-white border-gray-200 text-gray-900">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <span className="bg-blue-500 p-1 rounded-md">
            <Plus className="h-4 w-4 text-white" />
          </span>
          Gestion du Matériel
        </CardTitle>
        <CardDescription className="text-gray-600">
          Ajoutez des instruments et définissez leur volume.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">

        {/* Liste existante */}
        <div className="space-y-2 max-h-60 overflow-y-auto pr-1">
          <Label className="text-xs text-gray-600 uppercase tracking-wider">Catalogue actuel</Label>
          {gearCatalog.length === 0 ? (
            <p className="text-sm text-gray-600 italic text-center py-2">Aucun matériel.</p>
          ) : (
            gearCatalog.map((gear) => (
              <div 
                key={gear.id} 
                className="flex items-center justify-between p-2 rounded bg-gray-50 border border-gray-200 hover:border-gray-300 transition-colors"
              >
                <div className="min-w-0">
                  <span className="text-sm text-gray-800 block truncate">{gear.name}</span>
                  <span className="number_subtitle block">{gear.volume}m³</span>
                </div>
                <ActionButtons onDelete={() => onDeleteGear(gear.id)} />
              </div>
            ))
          )}
        </div>
      </CardContent>
    </Card>
  );
}
