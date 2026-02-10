import React from 'react';

export function Card({ children, className = '' }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={`
      rounded-lg border border-gray-200 bg-white w-full
      ${className}
    `}>
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
      px-4 pt-4 flex items-center justify-between
      ${className}
    `}>
      {children}
    </div>
  );
}

export function CardTitle({ children, className = '' }: { children: React.ReactNode; className?: string }) {
  return (
    <h2 className={`
      text-lg font-semibold text-gray-900
      ${className}
    `}>
      {children}
    </h2>
  );
}

export function CardDescription({ children, className = '' }: { children: React.ReactNode; className?: string }) {
  return (
    <p className={`
      text-sm text-gray-600
      ${className}
    `}>
      {children}
    </p>
  );
}
