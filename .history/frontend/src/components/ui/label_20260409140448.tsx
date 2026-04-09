import React from 'react';

interface LabelProps extends React.LabelHTMLAttributes<HTMLLabelElement> {
  children: React.ReactNode;
  className?: string;
}

export function Label({ children, className = '', ...props }: LabelProps) {
  return (
    <label className={`app-text-label text-gray-900 block ${className}`} {...props}>
      {children}
    </label>
  );
}
