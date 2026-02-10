import React from 'react';

interface LabelProps extends React.LabelHTMLAttributes<HTMLLabelElement> {
  children: React.ReactNode;
  className?: string;
}

export function Label({ children, className = '', ...props }: LabelProps) {
  return (
    <label className={`text-sm font-medium text-slate-300 block ${className}`} {...props}>
      {children}
    </label>
  );
}
