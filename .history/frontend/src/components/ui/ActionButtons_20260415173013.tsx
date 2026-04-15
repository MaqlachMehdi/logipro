import React from 'react';

interface ActionButtonsProps {
  onEdit?: (e: React.MouseEvent<HTMLButtonElement>) => void;
  onDelete?: (e: React.MouseEvent<HTMLButtonElement>) => void;
  showDelete?: boolean;
}

export function ActionButtons({ onEdit, onDelete, showDelete = true }: ActionButtonsProps) {
  return (
    <div className="ml-2 flex shrink-0 self-center items-center gap-1">
      {onEdit && (
        <button
          style={{
            backgroundColor: 'transparent',
            border: 'none',
            cursor: 'pointer',
            color: '#666666',
            fontSize: '18px',
            padding: '1px',
            width: '32px',
            height: '32px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            borderRadius: '6px',
            transition: 'background-color 150ms',
          }}
          onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = '#e0e7ff')}
          onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = 'transparent')}
          onClick={onEdit}
          type="button"
          title="Modifier"
        >
          ⚙️
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
            transition: 'background-color 150ms',
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
