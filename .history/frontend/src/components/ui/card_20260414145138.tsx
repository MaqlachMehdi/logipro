import React from 'react';

export function Card({ children, className = '' }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={`
      rounded-xl overflow-hidden border border-gray-200 bg-white w-full
      ${className}
    `}>
      <div className="h-2" style={{ backgroundColor: 'var(--color-C)' }} />
      {children}
    </div>
  );
}

export function CardContent({ children, className = '' }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={`
      p-4 flex flex-col flex-grow
      ${className}
    `}>
      {children}
    </div>
  );
}

export function CardHeader({ children, className = '' }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={`
      px-4 pt-5 pb-3 flex items-center justify-between
      ${className}
    `}>
      {children}
    </div>
  );
}

export function CardTitle({ children, className = '' }: { children: React.ReactNode; className?: string }) {
  return (
    <h2 className={`
      app-title-section text-gray-900 flex items-center gap-2.5
      ${className}
    `}>
      {children}
    </h2>
  );
}

export function CardDescription({ children, className = '' }: { children: React.ReactNode; className?: string }) {
  return (
    <p className={`
      app-text-meta text-gray-600
      ${className}
    `}>
      {children}
    </p>
  );
}
