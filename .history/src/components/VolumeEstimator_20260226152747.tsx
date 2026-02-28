import { useMemo, useState } from 'react';
import type { ChangeEvent, WheelEvent } from 'react';
import type { GearItem, GearSelection } from '../types';
import { Card, CardContent, CardHeader, CardTitle } from './ui';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { GEAR_CATALOG } from '../utils/volume-data';
import { ChevronDown, ChevronRight, Package, Trash2 } from 'lucide-react';

interface VolumeEstimatorProps {
  selections: GearSelection[];
  onChange: (selections: GearSelection[]) => void;
  spotName: string;
}

export function VolumeEstimator({ selections, onChange, spotName }: VolumeEstimatorProps) {
  const [openCategories, setOpenCategories] = useState<Set<string>>(new Set(['Percussion', 'Guitares']));

  const gearByCategory = useMemo(() => {
    return GEAR_CATALOG.reduce<Record<string, GearItem[]>>((acc, gear) => {
      if (!acc[gear.category]) {
        acc[gear.category] = [];
      }
      acc[gear.category].push(gear);
      return acc;
    }, {});
  }, []);

  const categories = useMemo(() => Object.keys(gearByCategory), [gearByCategory]);

  const selectionsByGearId = useMemo(() => {
    return selections.reduce<Record<string, number>>((acc, selection) => {
      acc[selection.gearId] = selection.quantity;
      return acc;
    }, {});
  }, [selections]);

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
    const gear = GEAR_CATALOG.find((g) => g.id === sel.gearId);
    return sum + (gear?.volume || 0) * sel.quantity;
  }, 0);

  const handleInputChange = (gearId: string, event: ChangeEvent<HTMLInputElement>) => {
    updateQuantity(gearId, parseInt(event.target.value) || 0);
  };

  const handleInputWheel = (event: WheelEvent<HTMLInputElement>) => {
    event.currentTarget.blur();
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
            <span className="text-blue-600 font-bold">{totalVolume.toFixed(1)} m³</span>
          </div>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-2 max-h-[60vh] overflow-y-auto pr-2">
        {categories.map((category) => (
          <div key={category} className="border border-gray-200 rounded-lg overflow-hidden bg-gray-50">
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
              <div className="p-2 space-y-2 border-t border-gray-200 max-h-56 overflow-y-auto overscroll-contain">
                {gearByCategory[category].map((gear) => {
                    const quantity = selectionsByGearId[gear.id] || 0;
                    
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
                            onChange={(e) => handleInputChange(gear.id, e)}
                            onWheel={handleInputWheel}
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
