import React, { ButtonHTMLAttributes, forwardRef } from 'react';
import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';
import { motion } from 'framer-motion';

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'outline' | 'ghost' | 'danger';
  size?: 'sm' | 'md' | 'lg';
  isLoading?: boolean;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = 'primary', size = 'md', isLoading, disabled, children, ...props }, ref) => {
    const baseStyles = 'inline-flex items-center justify-center font-mono font-bold tracking-tight border select-none transition-all duration-150 disabled:opacity-50 disabled:pointer-events-none cursor-pointer focus:outline-none focus:ring-1 focus:ring-[#d4af37]';
    
    const variants = {
      primary: 'bg-[#d4af37] border-[#d4af37] text-[#0a0a0a] hover:bg-[#f5c542] hover:border-[#f5c542] shadow-sm',
      secondary: 'bg-[#181818] border-[#2b2b2b] text-[#ffffff] hover:bg-[#2b2b2b] hover:border-[#d4af37]/40',
      outline: 'bg-transparent border-[#2b2b2b] text-[#6b6b6b] hover:text-[#ffffff] hover:bg-[#181818] hover:border-[#d4af37]/30',
      ghost: 'bg-transparent border-transparent text-[#6b6b6b] hover:text-[#ffffff] hover:bg-[#181818]/50',
      danger: 'bg-[#181818] border-red-900/60 text-[#e5484d] hover:bg-red-950'
    };

    const sizes = {
      sm: 'h-8 px-3 text-[10px] tracking-wide gap-1.5',
      md: 'h-9 px-4 text-xs tracking-wide gap-2',
      lg: 'h-11 px-5 text-xs tracking-wider gap-2.5'
    };

    const MotionButton = motion.button;

    const motionProps = {
      disabled: disabled || isLoading,
      whileHover: { scale: 0.98 },
      whileTap: { scale: 0.96 },
      transition: { type: 'spring', stiffness: 400, damping: 15 },
      className: twMerge(clsx(baseStyles, variants[variant], sizes[size], className)),
      ...props
    };

    return (
      <MotionButton
        ref={ref as any}
        {...(motionProps as any)}
      >
        {isLoading ? (
          <svg className="animate-spin -ml-1 mr-2 h-3.5 w-3.5 text-current" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
          </svg>
        ) : null}
        {children}
      </MotionButton>
    );
  }
);

Button.displayName = 'Button';
