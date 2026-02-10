import { useState } from 'react';
import { Plus, Trash2 } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../ui';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Label } from '../ui/label';

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
  };

  return (
    <Card className="bg-slate-800 border-slate-700 text-slate-100">
      <CardHeader>
        <CardTitle className="text-lg flex items-center gap-2">
          <span className="bg-indigo-500 p-1 rounded-md">
            <Plus className="h-4 w-4 text-white" />
          </span>
          Gestion du Matériel
        </CardTitle>
        <CardDescription className="text-slate-400">
          Ajoutez des instruments et définissez leur volume.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        
        {/* Formulaire d'ajout */}
        <div className="grid grid-cols-1 gap-3 p-3 bg-slate-900/50 rounded-lg border border-slate-700/50">
          <div className="space-y-1">
            <Label htmlFor="gear-name" className="text-xs text-slate-400">Nom / Catégorie</Label>
            <Input
              id="gear-name"
              placeholder="Ex: Synthétiseur"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              className="bg-slate-950 border-slate-700 text-white focus:ring-indigo-500"
            />
          </div>
          
          <div className="space-y-1">
            <Label htmlFor="gear-volume" className="text-xs text-slate-400">Volume (m³)</Label>
            <Input
              id="gear-volume"
              type="number"
              step="0.1"
              placeholder="Ex: 1.5"
              value={newVolume}
              onChange={(e) => setNewVolume(e.target.value)}
              className="bg-slate-950 border-slate-700 text-white focus:ring-indigo-500"
            />
          </div>

          <Button 
            onClick={handleAdd}
            className="w-full bg-indigo-600 hover:bg-indigo-700 text-white"
          >
            Ajouter l'instrument
          </Button>
        </div>

        {/* Liste existante */}
        <div className="space-y-2 max-h-60 overflow-y-auto pr-1">
          <Label className="text-xs text-slate-500 uppercase tracking-wider">Catalogue actuel</Label>
          {gearCatalog.length === 0 ? (
            <p className="text-sm text-slate-500 italic text-center py-2">Aucun matériel.</p>
          ) : (
            gearCatalog.map((gear) => (
              <div 
                key={gear.id} 
                className="flex items-center justify-between p-2 rounded bg-slate-900 border border-slate-700/50 hover:border-slate-600 transition-colors"
              >
                <span className="text-sm text-slate-300">{gear.name}</span>
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-6 w-6 p-0 text-slate-500 hover:text-red-400"
                  onClick={() => onDeleteGear(gear.id)}
                >
                  <Trash2 className="w-3 h-3" />
                </Button>
              </div>
            ))
          )}
        </div>
      </CardContent>
    </Card>
  );
}
