import { useState } from 'react';

interface UseEditStateReturn<T> {
  editingId: string | null;
  editData: Partial<T> | null;
  startEdit: (item: T, idKey?: keyof T) => void;
  updateEdit: (key: string, value: any) => void;
  saveEdit: (onSave: (item: T) => void) => void;
  cancelEdit: () => void;
}

export function useEditState<T extends { id?: string }>(
  idKey: keyof T = 'id' as keyof T
): UseEditStateReturn<T> {
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editData, setEditData] = useState<Partial<T> | null>(null);

  const startEdit = (item: T) => {
    setEditingId(String(item[idKey]));
    setEditData({ ...item });
  };

  const updateEdit = (key: string, value: any) => {
    setEditData(prev => prev ? { ...prev, [key]: value } : null);
  };

  const saveEdit = (onSave: (item: T) => void) => {
    if (editData && editingId) {
      onSave(editData as T);
      setEditingId(null);
      setEditData(null);
    }
  };

  const cancelEdit = () => {
    setEditingId(null);
    setEditData(null);
  };

  return {
    editingId,
    editData,
    startEdit,
    updateEdit,
    saveEdit,
    cancelEdit,
  };
}
