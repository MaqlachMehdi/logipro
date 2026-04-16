import { useEffect, useState } from 'react';
import type { GearSelection } from '../types';
import { Card, CardContent, CardHeader, CardTitle } from './ui';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { ChevronDown, ChevronRight, Package, Plus, Trash2 } from 'lucide-react';
import type { GearItem } from '../types';
import { ActionButtons } from './ui/ActionButtons';

interface VolumeEstimatorProps {
  selections: GearSelection[];
  onChange: (selections: GearSelection[]) => void;
  spotName: string;
  gears: GearItem[];
  onAddGear: (gear: Omit<GearItem, 'id'>) => Promise<void> | void;
  onDeleteGear: (gearId: string) => Promise<void> | void;
}

const CUSTOM_CATEGORIES_KEY = 'regietour_custom_gear_categories';

export function VolumeEstimator({ selections, onChange, spotName, gears, onAddGear, onDeleteGear }: VolumeEstimatorProps) {
  const [openCategories, setOpenCategories] = useState<Set<string>>(new Set(['Percussion', 'Guitares']));
  const [isAddMenuOpen, setIsAddMenuOpen] = useState(false);
  
  const [customCategories, setCustomCategories] = useState<string[]>(() => {
    try {
      const raw = localStorage.getItem(CUSTOM_CATEGORIES_KEY);
      if (!raw) return [];
      const parsed = JSON.parse(raw);
      if (!Array.isArray(parsed)) return [];
      return parsed.filter((item) => typeof item === 'string' && item.trim().length > 0);
    } catch {
      return [];
    }
  });
  const [newGearName, setNewGearName] = useState('');
  const [newGearVolume, setNewGearVolume] = useState('');
  const [newGearCategory, setNewGearCategory] = useState('');
  const [addError, setAddError] = useState('');

  useEffect(() => {
    localStorage.setItem(CUSTOM_CATEGORIES_KEY, JSON.stringify(customCategories));
  }, [customCategories]);

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

  // Catégories réellement présentes dans la DB (hors dummy)
  const categories = [...new Set(
    gears
      .filter((g: any) => g.name !== '__dummy__')
      .map((g: any) => g.category)
      .filter(Boolean)
      .concat(customCategories)
  )] as string[];

  // Suggestions = uniquement les Catégories existantes (plus aucune Catégorie supprimée)
  const categorySuggestions = categories;

  const handleAddGear = async () => {
    const name = newGearName.trim();
    const category = newGearCategory.trim();
    const volume = parseFloat(newGearVolume);

    if (!name) {
      setAddError("Le nom de l'instrument est requis.");
      return;
    }

    if (!category) {
      setAddError('La Catégorie est requise.');
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
      setAddError('Cet instrument existe déjà  dans cette Catégorie.');
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
      setAddError("Impossible d'ajouter l'instrument pour le moment.");
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
                className="app-title-subsection px-2 text-red-600 hover:text-red-700 hover:bg-red-50"
                style={{ color: undefined, transform: 'none' }}
                onClick={() => onChange([])}
              >
                <Trash2 style={{ width: '1.15rem', height: '1.15rem', marginRight: '0.25rem', flexShrink: 0 }} />
                Tout supprimer
              </Button>
            )}
            <span className="text-blue-600 font-bold">{totalVolume.toFixed(1)} m³</span>
          </div>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-2 overflow-y-auto pr-2 max-h-[40vh]">
        {categories.map((category: string) => (
          <div key={category} className="border border-gray-200 rounded-lg overflow-visible bg-gray-50">
            <div className="w-full px-3 py-2 flex items-center justify-between hover:bg-gray-100 transition-colors cursor-pointer">
              <ActionButtons
                onDelete={async () => {
                  setCustomCategories((prev) => prev.filter((c) => c !== category));
                  setOpenCategories((prev) => {
                    const next = new Set(prev);
                    next.delete(category);
                    return next;
                  });
                  if (typeof onDeleteGear === 'function') {
                    const gearsToDelete = gears.filter((g) => g.category === category);
                    for (const gear of gearsToDelete) {
                      await onDeleteGear(gear.id);
                    }
                  }
                }}
                showDelete={true}
              />
              <div className="flex items-center gap-2 min-w-0 flex-1" role="button" tabIndex={0}
                onClick={() => toggleCategory(category)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    toggleCategory(category);
                  }
                }}
                aria-expanded={openCategories.has(category)}>
                <span className="text-sm font-medium text-gray-800 truncate">{category}</span>
                {openCategories.has(category) ? (
                  <ChevronDown className="w-4 h-4 text-gray-500" />
                ) : (
                  <ChevronRight className="w-4 h-4 text-gray-500" />
                )}
              </div>
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
                            className="h-7 w-7 p-0 text-gray-500 hover:text-gray-900 hover:bg-blue-100 font-bold"
                            onClick={() => updateQuantity(gear.id, quantity - 1)}
                          >
                            -
                          </Button>
                          <input
                            type="number"
                            min="0"
                            value={quantity}
                            onChange={(e: React.ChangeEvent<HTMLInputElement>) => updateQuantity(gear.id, parseInt(e.target.value) || 0)}
                            style={{ width: '3rem', height: '1.75rem', textAlign: 'center', border: '1px solid #d1d5db', borderRadius: '0.375rem', fontSize: '0.875rem', color: '#111827', background: 'white', minWidth: '0', padding: '0' }}
                          />
                          <Button
                            variant="ghost"
                            size="sm"
                            className="h-7 w-7 p-0 text-gray-500 hover:text-gray-900 hover:bg-blue-100 font-bold"
                            onClick={() => updateQuantity(gear.id, quantity + 1)}
                          >
                            +
                          </Button>
                          <ActionButtons onDelete={() => onDeleteGear(gear.id)} showDelete={true} />
                        </div>
                      </div>
                    );
                  })}
                {gears.filter((g: any) => g.category === category).length === 0 && (
                  <p className="text-xs text-gray-500 italic">Aucun instrument dans cette Catégorie.</p>
                )}
              </div>
            )}
          </div>
        ))}
      </CardContent>

      {/* Zone fixe en bas — formulaire ou bouton, toujours visible */}
      <div style={{ padding: '0.5em', borderTop: '1px solid #e5e7eb' }}>
        {isAddMenuOpen ? (
          <div className="rounded-lg border border-gray-200 space-y-3" style={{ padding: '0.5em' }}>
            <div style={{ paddingBottom: '0.4em', paddingLeft: '0.5em', paddingRight: '0.5em' }}>
              <Label htmlFor="new-gear-name" style={{ display: 'block', paddingBottom: '0.3em', fontSize: '0.85rem', fontWeight: 'bold', color: '#000' }}>Nom d&apos;instrument</Label>
              <Input
                id="new-gear-name"
                value={newGearName}
                onChange={(e) => setNewGearName(e.target.value)}
                placeholder="Ex: Grosse caisse"
                className="bg-white border-gray-300 text-gray-900"
              />
            </div>
            <div style={{ paddingBottom: '0.4em', paddingLeft: '0.5em', paddingRight: '0.5em' }}>
              <Label htmlFor="new-gear-volume" style={{ display: 'block', paddingBottom: '0.3em', fontSize: '0.85rem', fontWeight: 'bold', color: '#000' }}>Volume par instrument (m³)</Label>
              <Input
                id="new-gear-volume"
                type="number"
                min="0"
                step="0.1"
                value={newGearVolume}
                onChange={(e) => setNewGearVolume(e.target.value)}
                placeholder="Ex: 1.2"
                className="bg-white border-gray-300 text-gray-900"
              />
            </div>
            <div style={{ paddingBottom: '0.4em', paddingLeft: '0.5em', paddingRight: '0.5em' }}>
              <Label htmlFor="new-gear-category" style={{ display: 'block', paddingBottom: '0.3em', fontSize: '0.85rem', fontWeight: 'bold', color: '#000' }}>Catégorie</Label>
              <Input
                id="new-gear-category"
                list="gear-categories-list"
                value={newGearCategory}
                onChange={(e) => setNewGearCategory(e.target.value)}
                placeholder="Ex: Percussion"
                className="bg-white border-gray-300 text-gray-900"
              />
              <datalist id="gear-categories-list">
                {categorySuggestions.map((cat) => (
                  <option key={cat} value={cat} />
                ))}
              </datalist>
            </div>
            {addError && <p className="text-red-500 text-xs" style={{ paddingLeft: '0.5em' }}>{addError}</p>}
            <div className="flex gap-2" style={{ paddingTop: '0.2em', paddingLeft: '0.5em', paddingRight: '0.5em' }}>
              <Button
                size="sm"
                variant="ghost"
                className="bouton_add flex-1 bg-white text-gray-900"
                style={{ borderStyle: 'solid', borderWidth: '1px', borderColor: '#d1d5db', transition: 'border-color 150ms, border-width 150ms' }}
                onMouseEnter={(e) => { e.currentTarget.style.borderColor = '#000'; e.currentTarget.style.borderWidth = '2px'; }}
                onMouseLeave={(e) => { e.currentTarget.style.borderColor = '#d1d5db'; e.currentTarget.style.borderWidth = '1px'; }}
                onClick={handleAddGear}
              >
                Ajouter
              </Button>
              <Button
                size="sm"
                variant="ghost"
                className="bouton_add text-gray-900"
                style={{ borderStyle: 'solid', borderWidth: '1px', borderColor: 'transparent', transition: 'border-color 150ms, border-width 150ms' }}
                onMouseEnter={(e) => { e.currentTarget.style.borderColor = '#000'; e.currentTarget.style.borderWidth = '2px'; }}
                onMouseLeave={(e) => { e.currentTarget.style.borderColor = 'transparent'; e.currentTarget.style.borderWidth = '1px'; }}
                onClick={() => { setIsAddMenuOpen(false); setAddError(''); }}
              >
                Annuler
              </Button>
            </div>
          </div>
        ) : (
          <div style={{ padding: '0.2em' }}>
            <Button
              variant="ghost"
              size="sm"
              className="bouton_add w-full text-gray-900"
              style={{ borderStyle: 'solid', borderWidth: '1px', borderColor: '#d1d5db', transition: 'border-color 150ms, border-width 150ms' }}
              onMouseEnter={(e) => { e.currentTarget.style.borderColor = '#000'; e.currentTarget.style.borderWidth = '2px'; }}
              onMouseLeave={(e) => { e.currentTarget.style.borderColor = '#d1d5db'; e.currentTarget.style.borderWidth = '1px'; }}
              onClick={() => { setIsAddMenuOpen(true); setAddError(''); }}
            >
              <Plus className="w-4 h-4 mr-2" />
              Ajouter un instrument
            </Button>
          </div>
        )}
      </div>
    </Card>
  );
}
