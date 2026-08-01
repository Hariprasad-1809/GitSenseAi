import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ChevronDown } from 'lucide-react';
import { clsx } from 'clsx';

interface AccordionItem {
  id: string;
  title: string;
  content: string;
}

interface AccordionProps {
  items: AccordionItem[];
}

export function Accordion({ items }: AccordionProps) {
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const toggle = (id: string) => {
    setExpandedId(expandedId === id ? null : id);
  };

  return (
    <div className="space-y-2 w-full font-mono">
      {items.map((item) => {
        const isExpanded = expandedId === item.id;
        return (
          <div
            key={item.id}
            className="border border-[#2b2b2b] rounded-none bg-[#181818]/25 overflow-hidden transition-colors hover:border-[#d4af37]/50"
          >
            <button
              onClick={() => toggle(item.id)}
              aria-expanded={isExpanded}
              className="w-full flex items-center justify-between px-5 py-3 text-left font-medium text-[#6b6b6b] hover:text-[#ffffff] text-xs tracking-tight transition-colors cursor-pointer focus:outline-none"
            >
              <span>{item.title}</span>
              <ChevronDown
                className={clsx(
                  'h-3.5 w-3.5 text-zinc-500 transition-transform duration-250 ease-out',
                  isExpanded && 'transform rotate-180 text-[#ffffff]'
                )}
              />
            </button>

            <AnimatePresence initial={false}>
              {isExpanded && (
                <motion.div
                  initial={{ height: 0 }}
                  animate={{ height: 'auto' }}
                  exit={{ height: 0 }}
                  transition={{ type: 'spring', stiffness: 350, damping: 25 }}
                >
                  <div className="px-5 pb-4 pt-1 text-[#e5e5e5]/90 text-xs leading-relaxed border-t border-[#2b2b2b] bg-[#181818]/45">
                    {item.content}
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        );
      })}
    </div>
  );
}
