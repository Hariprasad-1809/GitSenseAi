import React, { useEffect, useRef } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { X } from 'lucide-react';
import { twMerge } from 'tailwind-merge';

interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  children: React.ReactNode;
  className?: string;
}

export function Modal({ isOpen, onClose, title, children, className }: ModalProps) {
  const closeButtonRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        onClose();
      }
    };
    if (isOpen) {
      window.addEventListener('keydown', handleKeyDown);
      setTimeout(() => closeButtonRef.current?.focus(), 100);
      document.body.style.overflow = 'hidden';
    }
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
      document.body.style.overflow = '';
    };
  }, [isOpen, onClose]);

  return (
    <AnimatePresence>
      {isOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 font-mono">
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="fixed inset-0 bg-[#0a0a0a]/85"
          />

          {/* Dialog Container */}
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 10 }}
            transition={{ type: 'spring', stiffness: 350, damping: 25 }}
            role="dialog"
            aria-modal="true"
            aria-labelledby="modal-title"
            className={twMerge(
              'relative w-full max-w-lg bg-[#181818] border border-[#2b2b2b] rounded-none z-10 flex flex-col max-h-[90vh] overflow-hidden shadow-2xl shadow-black/80',
              className
            )}
          >
            {/* Header */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-[#2b2b2b] bg-[#181818]/45">
              <h2 id="modal-title" className="text-xs font-bold text-[#ffffff] uppercase tracking-wider">
                // {title}
              </h2>
              <button
                ref={closeButtonRef}
                onClick={onClose}
                aria-label="Close dialog"
                className="text-[#6b6b6b] hover:text-[#f5c542] hover:bg-[#2b2b2b] p-1 transition-all cursor-pointer border border-transparent hover:border-[#2b2b2b]"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            {/* Body */}
            <div className="px-6 py-5 overflow-y-auto text-[#e5e5e5] text-xs leading-relaxed">
              {children}
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
}
