import React, { useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Sparkles, Mail, MessageSquare } from 'lucide-react';
import { Button } from '../ui/Button';
import { ContactModal } from './ContactModal';

export function Navbar() {
  const location = useLocation();
  const [isContactOpen, setIsContactOpen] = useState(false);
  const isChatPage = location.pathname === '/chat';

  return (
    <>
      <nav className="sticky top-0 z-40 w-full border-b border-[#2b2b2b] bg-[#0a0a0a]/85 backdrop-blur-md">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 font-mono">
          <div className="flex items-center justify-between h-16">
            {/* Logo */}
            <div className="flex items-center">
              <Link to="/" className="flex items-center gap-2 group focus:outline-none">
                <div className="h-8 w-8 bg-[#d4af37] flex items-center justify-center text-[#0a0a0a] shadow-lg shadow-[#d4af37]/10 group-hover:bg-[#f5c542] transition-colors">
                  <Sparkles className="h-4.5 w-4.5" />
                </div>
                <div className="flex flex-col">
                  <span className="font-bold text-sm text-[#ffffff] tracking-tight leading-none">GitSense</span>
                  <span className="text-[9px] text-[#6b6b6b] tracking-wider mt-1">// ENGINE_CORE</span>
                </div>
              </Link>
            </div>

            {/* Links and CTA */}
            <div className="flex items-center gap-4">
              <button
                onClick={() => setIsContactOpen(true)}
                className="inline-flex items-center gap-1.5 text-[#6b6b6b] hover:text-[#d4af37] text-xs font-semibold uppercase tracking-wider transition-colors cursor-pointer focus:outline-none"
              >
                <Mail className="h-3.5 w-3.5" />
                <span className="hidden sm:inline">CONTACT</span>
              </button>

              <a
                href="https://github.com/Hariprasad-1809/GitSenseAi"
                target="_blank"
                rel="noreferrer"
                className="text-[#6b6b6b] hover:text-[#d4af37] transition-colors p-1.5 hover:bg-[#181818] rounded-none focus:outline-none border border-transparent hover:border-[#2b2b2b]"
              >
                <svg className="h-3.5 w-3.5 fill-current" viewBox="0 0 24 24" aria-hidden="true">
                  <path fillRule="evenodd" clipRule="evenodd" d="M12 2C6.477 2 2 6.477 2 12c0 4.42 2.865 8.167 6.839 9.49.5.092.682-.217.682-.482 0-.237-.008-.866-.013-1.7-2.782.603-3.369-1.34-3.369-1.34-.454-1.156-1.11-1.464-1.11-1.464-.908-.62.069-.608.069-.608 1.003.07 1.531 1.03 1.531 1.03.892 1.529 2.341 1.087 2.91.831.092-.646.35-1.086.636-1.336-2.22-.253-4.555-1.11-4.555-4.943 0-1.091.39-1.984 1.029-2.683-.103-.253-.446-1.27.098-2.647 0 0 .84-.269 2.75 1.025A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.294 2.747-1.025 2.747-1.025.546 1.377.203 2.394.1 2.647.64.699 1.028 1.592 1.028 2.683 0 3.842-2.339 4.687-4.566 4.935.359.309.678.919.678 1.852 0 1.336-.012 2.415-.012 2.743 0 .267.18.579.688.481C19.137 20.164 22 16.418 22 12c0-5.523-4.477-10-10-10z" />
                </svg>
              </a>

              {!isChatPage ? (
                <Link to="/chat" className="focus:outline-none">
                  <Button size="sm" variant="primary">
                    <MessageSquare className="h-3.5 w-3.5" />
                    <span>LAUNCH</span>
                  </Button>
                </Link>
              ) : (
                <Link to="/" className="focus:outline-none">
                  <Button size="sm" variant="outline">
                    <span>HOME</span>
                  </Button>
                </Link>
              )}
            </div>
          </div>
        </div>
      </nav>

      {/* Contact modal */}
      <ContactModal isOpen={isContactOpen} onClose={() => setIsContactOpen(false)} />
    </>
  );
}
