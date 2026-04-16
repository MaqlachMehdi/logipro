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

        {/* Formulaire d'ajout (affiché si isAdding) */}
        {isAdding && (
          <div className="grid grid-cols-1 gap-3 p-3 bg-gray-50 rounded-lg border border-gray-200">
            <div className="space-y-1">
              <Label htmlFor="gear-name" className="text-xs text-gray-600">Nom d'instrument</Label>
              <Input
                id="gear-name"
                placeholder="Ex: Synthétiseur"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                className="bg-white border-gray-300 text-gray-900 focus:ring-blue-500"
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="gear-volume" className="text-xs text-gray-600">Volume par instrument (m³)</Label>
              <Input
                id="gear-volume"
                type="number"
                step="0.1"
                placeholder="Ex: 1.5"
                value={newVolume}
                onChange={(e) => setNewVolume(e.target.value)}
                className="bg-white border-gray-300 text-gray-900 focus:ring-blue-500"
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="gear-category" className="text-xs text-gray-600">Catégorie</Label>
              <Input
                id="gear-category"
                placeholder="Ex: Clavier"
                value={newCategory}
                onChange={(e) => setNewCategory(e.target.value)}
                className="bg-white border-gray-300 text-gray-900 focus:ring-blue-500"
              />
            </div>
            <div className="flex gap-2">
              <Button
                onClick={handleAdd}
                className="flex-1 bg-blue-600 hover:bg-blue-700 text-white"
              >
                Confirmer
              </Button>
              <Button
                variant="ghost"
                onClick={() => { setIsAdding(false); setNewName(''); setNewVolume(''); setNewCategory(''); }}
                className="flex-1 border border-gray-300 text-gray-700"
              >
                Annuler
              </Button>
            </div>
          </div>
        )}

        {/* Bouton ajouter un instrument */}
        {!isAdding && (
          <div style={{ padding: '0.2em' }}>
            <Button
              variant="ghost"
              size="sm"
              className="bouton_add w-full text-gray-900"
              style={{ borderStyle: 'solid', borderWidth: '1px', borderColor: '#d1d5db', transition: 'border-color 150ms, border-width 150ms' }}
              onMouseEnter={(e) => { e.currentTarget.style.borderColor = '#000'; e.currentTarget.style.borderWidth = '2px'; }}
              onMouseLeave={(e) => { e.currentTarget.style.borderColor = '#d1d5db'; e.currentTarget.style.borderWidth = '1px'; }}
              onClick={() => setIsAdding(true)}
            >
              <Plus className="w-4 h-4 mr-2" />
              + ajouter un instrument
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
