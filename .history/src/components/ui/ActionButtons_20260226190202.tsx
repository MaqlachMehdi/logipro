import React from 'react';

interface ActionButtonsProps {
  onEdit?: (e: React.MouseEvent<HTMLButtonElement>) => void;
  onDelete?: (e: React.MouseEvent<HTMLButtonElement>) => void;
  showDelete?: boolean;
}

export function ActionButtons({ onEdit, onDelete, showDelete = true }: ActionButtonsProps) {
  const buttonStyle = (hoverColor: string) => ({
    backgroundColor: 'transparent',
    border: 'none',
    cursor: 'pointer',
    fontSize: '18px',
    padding: '0',
    width: '32px',
    height: '32px',
    display: 'flex' as const,
    alignItems: 'center' as const,
    justifyContent: 'center' as const,
    borderRadius: '6px',
    transition: 'background-color 150ms',
    hoverColor,
  });

  return (
    <div className="flex gap-1 ml-2">
      {onEdit && (
        <button
          style={{
            backgroundColor: 'transparent',
            border: 'none',
            cursor: 'pointer',
            color: '#666666',
            fontSize: '18px',
            padding: '0',
            width: '32px',
            height: '32px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            borderRadius: '6px',
            transition: 'background-color 150ms'
          }}
          onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = '#e0e7ff')}
          onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = 'transparent')}
          onClick={onEdit}
          type="button"
          title="Modifier"
        >
          🔧
        </button>
      )}
      {showDelete && onDelete && (
        <button
          style={{
            backgroundColor: 'transparent',
            border: 'none',
            cursor: 'pointer',
            color: '#000000',
            fontSize: '20px',
            fontWeight: 'bold',
            padding: '0',
            width: '32px',
            height: '32px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            borderRadius: '6px',
            transition: 'background-color 150ms'
          }}
          onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = '#fecaca')}
          onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = 'transparent')}
          onClick={onDelete}
          type="button"
          title="Supprimer"
        >
          ×
        </button>
      )}
    </div>
  );
}
