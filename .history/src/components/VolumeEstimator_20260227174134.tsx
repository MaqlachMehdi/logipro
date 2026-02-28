import { useState } from 'react';
import type { GearSelection } from '../types';
import { Card, CardContent, CardHeader, CardTitle } from './ui';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { ChevronDown, ChevronRight, Package, Plus, Trash2 } from 'lucide-react';
import type { GearItem } from '../types';

interface VolumeEstimatorProps {
  selections: GearSelection[];
  onChange: (selections: GearSelection[]) => void;
  spotName: string;
  gears: GearItem[];
  onAddGear: (gear: Omit<GearItem, 'id'>) => Promise<void> | void;
}

const DEFAULT_CATEGORY_SUGGESTIONS = ['Percussion', 'Guitares', 'Claviers', 'Sonorisation', 'Accessoires'];

export function VolumeEstimator({ selections, onChange, spotName, gears, onAddGear }: VolumeEstimatorProps) {
  const [openCategories, setOpenCategories] = useState<Set<string>>(new Set(['Percussion', 'Guitares']));
  const [isAddMenuOpen, setIsAddMenuOpen] = useState(false);
  const [newGearName, setNewGearName] = useState('');
  const [newGearVolume, setNewGearVolume] = useState('');
  const [newGearCategory, setNewGearCategory] = useState('');
  const [addError, setAddError] = useState('');

  const toggleCategory = (category: string) => {
    const newOpen = new Set(openCategories);
    if (newOpen.has(category)) {
      newOpen.delete(category);
    } else {
      newOpen.add(category);
    }
    setOpenCategories(newOpen);
  };

  const updateQuantity = (gearId: string, quantity: number) => {
    const existing = selections.find(s => s.gearId === gearId);
    let newSelections: GearSelection[];
    
    if (quantity <= 0) {
      newSelections = selections.filter(s => s.gearId !== gearId);
    } else if (existing) {
      newSelections = selections.map(s => 
        s.gearId === gearId ? { ...s, quantity } : s
      );
    } else {
      newSelections = [...selections, { gearId, quantity }];
    }
    
    onChange(newSelections);
  };

  const totalVolume = selections.reduce((sum, sel) => {
    const gear = gears.find((g: any) => g.id === sel.gearId);
    return sum + (gear?.volume || 0) * sel.quantity;
  }, 0);

  const categories = [...new Set(gears.map((g: any) => g.category).filter(Boolean))] as string[];
  const categorySuggestions = [...new Set([...DEFAULT_CATEGORY_SUGGESTIONS, ...categories])];

  const handleAddGear = async () => {
    const name = newGearName.trim();
    const category = newGearCategory.trim();
    const volume = parseFloat(newGearVolume);

    if (!name) {
      setAddError('Le nom de l’instrument est requis.');
      return;
    }

    if (!category) {
      setAddError('La catégorie est requise.');
      return;
    }

    if (Number.isNaN(volume) || volume <= 0) {
      setAddError('Le volume par instrument doit être un nombre > 0.');
      return;
    }

    const duplicateExists = gears.some(
      (g) => g.name.trim().toLowerCase() === name.toLowerCase() && g.category.trim().toLowerCase() === category.toLowerCase(),
    );

    if (duplicateExists) {
      setAddError('Cet instrument existe déjà dans cette catégorie.');
      return;
    }

    try {
      await onAddGear({
        name,
        category,
        volume,
      });
      setNewGearName('');
      setNewGearVolume('');
      setNewGearCategory('');
      setAddError('');
      setIsAddMenuOpen(false);
    } catch {
      setAddError('Impossible d’ajouter l’instrument pour le moment.');
    }
  };

  return (
    <Card className="bg-white border-gray-200">
      <CardHeader className="pb-3">
        <CardTitle className="text-gray-900 text-sm flex items-center justify-between">
          <span className="flex items-center gap-2">
            <Package className="w-4 h-4 text-blue-600" />
            Matériel : {spotName}
          </span>
          <div className="flex items-center gap-2">
            {selections.length > 0 && (
              <Button
                variant="ghost"
                size="sm"
                className="h-6 px-2 text-xs text-red-600 hover:text-red-700 hover:bg-red-50"
                onClick={() => onChange([])}
              >
                <Trash2 className="w-3 h-3 mr-1" />
                Tout supprimer
              </Button>
            )}
            <div className="relative ml-2">
              <Button
                size="sm"
                className="h-6 w-6 p-0 !bg-white !hover:bg-gray-100 !text-black border border-gray-300"
                onClick={() => {
                  setIsAddMenuOpen((prev) => !prev);
                  setAddError('');
                }}
                aria-label="Ajouter un instrument"
              >
                <Plus className="w-3 h-3" />
              </Button>

              {isAddMenuOpen && (
                <div className="absolute left-full ml-2 top-0 z-20 w-72 rounded-lg border border-gray-200 bg-white p-3 shadow-lg">
                <div className="space-y-2">
                  <div className="space-y-1">
                    <Label htmlFor="new-gear-name" className="text-xs text-gray-600">Nom de l’instrument</Label>
                    <Input
                      id="new-gear-name"
                      value={newGearName}
                      onChange={(e) => setNewGearName(e.target.value)}
                      placeholder="Ex: Grosse caisse"
                      className="h-8"
                    />
                  </div>

                  <div className="space-y-1">
                    <Label htmlFor="new-gear-volume" className="text-xs text-gray-600">Volume par instrument (m³)</Label>
                    <Input
                      id="new-gear-volume"
                      type="number"
                      min="0"
                      step="0.1"
                      value={newGearVolume}
                      onChange={(e) => setNewGearVolume(e.target.value)}
                      placeholder="Ex: 1.2"
                      className="h-8"
                    />
                  </div>

                  <div className="space-y-1">
                    <Label htmlFor="new-gear-category" className="text-xs text-gray-600">Catégorie</Label>
                    <Input
                      id="new-gear-category"
                      list="gear-categories-list"
                      value={newGearCategory}
                      onChange={(e) => setNewGearCategory(e.target.value)}
                      placeholder="Ex: Percussion"
                      className="h-8"
                    />
                    <datalist id="gear-categories-list">
                      {categorySuggestions.map((category) => (
                        <option key={category} value={category} />
                      ))}
                    </datalist>
                  </div>

                  {addError && <p className="text-xs text-red-600">{addError}</p>}

                  <div className="flex items-center gap-2 pt-1">
                    <Button size="sm" className="h-8 flex-1 !bg-white !hover:bg-gray-100 !text-black border border-gray-300" onClick={handleAddGear}>
                      Ajouter
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      className="h-8"
                      onClick={() => {
                        setIsAddMenuOpen(false);
                        setAddError('');
                      }}
                    >
                      Annuler
                    </Button>
                  </div>
                </div>
                </div>
              )}
            </div>
            <span className="text-blue-600 font-bold">{totalVolume.toFixed(1)} m³</span>
          </div>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-2 max-h-[48vh] overflow-y-auto pr-2">
        {categories.map((category: string) => (
          <div key={category} className="border border-gray-200 rounded-lg overflow-visible bg-gray-50">
            <div
              role="button"
              tabIndex={0}
              onClick={() => toggleCategory(category)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault();
                  toggleCategory(category);
                }
              }}
              className="w-full px-3 py-2 flex items-center justify-between hover:bg-gray-100 transition-colors cursor-pointer"
              aria-expanded={openCategories.has(category)}
            >
              <span className="text-sm font-medium text-gray-800">{category}</span>
              {openCategories.has(category) ? (
                <ChevronDown className="w-4 h-4 text-gray-500" />
              ) : (
                <ChevronRight className="w-4 h-4 text-gray-500" />
              )}
            </div>
            
            {openCategories.has(category) && (
              <div className="p-2 space-y-2 border-t border-gray-200 bg-white">
                {gears
                  .filter((g: any) => g.category === category)
                  .map((gear: any) => {
                    const selection = selections.find(s => s.gearId === gear.id);
                    const quantity = selection?.quantity || 0;
                    
                    return (
                      <div key={gear.id} className="flex items-center gap-2">
                        <div className="flex-1 min-w-0">
                          <Label className="text-xs text-gray-600 truncate block">{gear.name}</Label>
                          <span className="text-[10px] text-gray-500">{gear.volume}m³</span>
                        </div>
                        <div className="flex items-center gap-1">
                          <Button
                            variant="ghost"
                            size="sm"
                            className="h-7 w-7 p-0 text-gray-500 hover:text-gray-900 hover:bg-blue-100"
                            onClick={() => updateQuantity(gear.id, quantity - 1)}
                          >
                            -
                          </Button>
                          <Input
                            type="number"
                            min="0"
                            value={quantity}
                            onChange={(e: React.ChangeEvent<HTMLInputElement>) => updateQuantity(gear.id, parseInt(e.target.value) || 0)}
                            className="h-7 w-14 text-center bg-white border-gray-300 text-gray-900 text-sm"
                          />
                          <Button
                            variant="ghost"
                            size="sm"
                            className="h-7 w-7 p-0 text-gray-500 hover:text-gray-900 hover:bg-blue-100"
                            onClick={() => updateQuantity(gear.id, quantity + 1)}
                          >
                            +
                          </Button>
                        </div>
                      </div>
                    );
                  })}
              </div>
            )}
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
