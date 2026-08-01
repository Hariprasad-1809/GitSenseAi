import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { motion, Variants } from 'framer-motion';
import {
  ArrowRight,
  Terminal,
  Search,
  Sparkles,
  GitBranch,
  ShieldAlert,
  Layers,
  BookOpen,
  ChevronRight,
  HelpCircle,
  Activity,
  Code
} from 'lucide-react';
import { Accordion } from '../components/ui/Accordion';
import { Button } from '../components/ui/Button';
import { ContactModal } from '../components/layout/ContactModal';

const features = [
  {
    icon: Layers,
    title: 'AST-AWARE CODE CHUNKING',
    index: '0x01',
    desc: 'Bypasses crude token-splitting rules. Parses actual class declarations, methods, and functions alongside preceding docstrings using Tree-sitter AST nodes.',
  },
  {
    icon: Search,
    title: 'SEMANTIC + KEYWORD RETRIEVAL',
    index: '0x02',
    desc: 'Combines dense vector similarity searches (pgvector BGE) with full-text keyword indexing (PostgreSQL FTS) to query code concepts and names.',
  },
  {
    icon: Sparkles,
    title: 'CITED RESPONSE SCHEMAS',
    index: '0x03',
    desc: 'Answers questions using retrieve-only contexts. Generates explicit source listings (e.g., `main.py, Lines 10-25`) referencing real repository coordinates.',
  },
  {
    icon: GitBranch,
    title: 'GIT CLONE & ZIP INGESTION',
    index: '0x04',
    desc: 'Clones public repositories shallowly or parses uploaded codebase archives. Indexes them dynamically in background worker queues.',
  },
  {
    icon: BookOpen,
    title: 'PROJECT OVERVIEW INTENTS',
    index: '0x05',
    desc: 'Answers project summaries using a specialized layout mapping pipeline, prioritizing README summaries and main entry point dependencies.',
  },
  {
    icon: ShieldAlert,
    title: 'SESSION RESOURCE ISOLATION',
    index: '0x06',
    desc: 'Stores workspace logs under isolated anonymous session keys. Cloned folders and database tables expire and clear completely after 3 hours.',
  }
];

const timelineSteps = [
  {
    step: '01',
    name: 'Ingestion / Ingest',
    desc: 'Clones public repository link with depth=1 (GitPython) or extracts uploaded ZIP files to a secure session directory.',
  },
  {
    step: '02',
    name: 'Lexical Parsing / Tree-sitter',
    desc: 'Parses files into syntax structures, mapping symbols (classes, functions) and extracting adjacent comment blocks.',
  },
  {
    step: '03',
    name: 'Vectorization / Embeddings',
    desc: 'Generates local 384-dimensional embeddings (bge-small-en-v1.5), prefixing text strings for retrieval optimization.',
  },
  {
    step: '04',
    name: 'Hybrid Search / RRF Fusion',
    desc: 'Executes cosine similarity and keyword full-text searches. Merges ranks using Reciprocal Rank Fusion (RRF) scores.',
  },
  {
    step: '05',
    name: 'Synthesis / OpenRouter',
    desc: 'Structures retrieved context fragments into context-heavy prompts, querying OpenRouter models with strict cited instructions.',
  }
];

const faqItems = [
  {
    id: 'faq-1',
    title: 'How does GitSense AI parse code files?',
    content: 'Instead of splitting files by arbitrary character lengths, GitSense AI parses actual syntax definitions using Tree-sitter. It extracts functions, classes, and methods along with preceding docstrings to keep comment contexts alongside the code scopes.',
  },
  {
    id: 'faq-2',
    title: 'How is codebase privacy managed?',
    content: 'GitSense AI uses temporary anonymous sessions. Cloned files and database mappings (projects, files, chunks, histories) automatically expire and are completely deleted from both storage disk and database tables after 3 hours.',
  },
  {
    id: 'faq-3',
    title: 'What retrieval models does the search engine run?',
    content: 'It executes hybrid search: vector similarity search on pgvector (Cosine distance) and keyword queries on full-text search indices. A Reciprocal Rank Fusion (RRF) algorithm merges candidates to select the top 5 most relevant chunks.',
  },
  {
    id: 'faq-4',
    title: 'Which LLMs are used, and is there a fallback system?',
    content: 'It defaults to Qwen 30B via OpenRouter. If a model returns 404 or 410, the backend calls secondary fallback models in sequence (e.g. Cohere or Llama) to prevent query failures.',
  }
];

const containerVariants: Variants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: { staggerChildren: 0.08, delayChildren: 0.05 }
  }
};

const itemVariants: Variants = {
  hidden: { y: 10, opacity: 0 },
  visible: { y: 0, opacity: 1, transition: { type: 'spring', stiffness: 350, damping: 25 } }
};

export function LandingPage() {
  const [isContactOpen, setIsContactOpen] = useState(false);

  return (
    <div className="flex flex-col min-h-screen bg-[#0a0a0a] text-[#e5e5e5] font-mono relative">
      {/* Decorative top header line */}
      <div className="h-[1px] w-full border-b border-[#2b2b2b]" />

      {/* Hero Section */}
      <section className="relative pt-20 pb-16 border-b border-[#2b2b2b]">
        <div className="max-w-6xl mx-auto px-6 flex flex-col items-start text-left">
          
          <motion.div
            initial={{ opacity: 0, x: -10 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.4 }}
            className="flex items-center gap-2 text-[10px] text-[#6b6b6b] font-bold uppercase tracking-wider mb-6"
          >
            <Terminal className="h-3.5 w-3.5" />
            <span>[ SYSTEM: INIT_OK • ENG_V1.0 ]</span>
          </motion.div>

          <motion.h1
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.1 }}
            className="text-3xl sm:text-5xl font-bold text-[#ffffff] tracking-tight leading-none uppercase max-w-4xl"
          >
            // RETRIEVAL-AUGMENTED CODE EXPLORER.<br/>
            <span className="text-[#6b6b6b]/60">EXAMINE REPOSITORIES IN NATURAL LANGUAGE.</span>
          </motion.h1>

          <motion.p
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.2 }}
            className="mt-6 text-xs text-[#e5e5e5]/80 max-w-2xl leading-relaxed"
          >
            GitSense AI parses syntax scopes, matches query targets using hybrid pgvector + full-text search rankings, and compiles answers with cited coordinate maps.
          </motion.p>

          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.3 }}
            className="mt-8 flex flex-wrap items-center gap-3"
          >
            <Link to="/chat">
              <Button size="md" className="group">
                <span>CONNECT WORKSPACE</span>
                <ArrowRight className="h-3.5 w-3.5 group-hover:translate-x-0.5 transition-transform" />
              </Button>
            </Link>
            <Button size="md" variant="outline" onClick={() => setIsContactOpen(true)}>
              <span>REQUEST SPEC</span>
            </Button>
          </motion.div>
        </div>
      </section>

      {/* Grid Features */}
      <section className="py-16 border-b border-[#2b2b2b] bg-[#0a0a0a]/20">
        <div className="max-w-6xl mx-auto px-6">
          <div className="flex flex-col items-start justify-between border-b border-[#2b2b2b] pb-8 mb-12">
            <span className="text-[10px] text-[#6b6b6b] font-bold uppercase tracking-wider">// SPECIFICATIONS</span>
            <h2 className="text-sm font-bold text-[#ffffff] mt-2 uppercase tracking-wide">CORE PARSING & INGESTION RULES</h2>
          </div>

          <motion.div
            variants={containerVariants}
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true, margin: '-100px' }}
            className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-px bg-[#2b2b2b] border border-[#2b2b2b]"
          >
            {features.map((feat, index) => {
              const IconComp = feat.icon;
              return (
                <motion.div
                  key={index}
                  variants={itemVariants}
                  className="p-6 bg-[#0a0a0a] hover:bg-[#181818]/30 transition-colors flex flex-col justify-between gap-6"
                >
                  <div className="flex items-center justify-between text-[10px] text-[#6b6b6b]">
                    <span>{feat.index}</span>
                    <IconComp className="h-4 w-4 text-[#d4af37]" />
                  </div>
                  <div>
                    <h3 className="text-xs font-bold text-[#ffffff] uppercase tracking-wide">{feat.title}</h3>
                    <p className="mt-2 text-[11px] text-[#e5e5e5]/80 leading-relaxed font-mono">{feat.desc}</p>
                  </div>
                </motion.div>
              );
            })}
          </motion.div>
        </div>
      </section>

      {/* How it Works Timeline */}
      <section className="py-16 border-b border-[#2b2b2b] bg-[#0a0a0a]/20">
        <div className="max-w-4xl mx-auto px-6">
          <div className="border-b border-[#2b2b2b] pb-8 mb-12 flex flex-col items-start">
            <span className="text-[10px] text-[#6b6b6b] font-bold uppercase tracking-wider">// WORKFLOW</span>
            <h2 className="text-sm font-bold text-[#ffffff] mt-2 uppercase tracking-wide">INGESTION PIPELINE CHRONOLOGY</h2>
          </div>

          <div className="space-y-4">
            {timelineSteps.map((step, idx) => (
              <div key={idx} className="flex gap-6 p-4 border border-[#2b2b2b] hover:border-[#d4af37]/45 bg-[#181818]/15 transition-all group">
                <div className="text-xs font-bold text-[#d4af37] font-mono select-none">
                  [{step.step}]
                </div>
                <div className="space-y-1">
                  <h3 className="text-xs font-bold text-[#ffffff] uppercase tracking-wide">{step.name}</h3>
                  <p className="text-[11px] text-[#e5e5e5]/80 leading-relaxed">{step.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Code Query Demos */}
      <section className="py-16 border-b border-[#2b2b2b]">
        <div className="max-w-6xl mx-auto px-6">
          <div className="border-b border-[#2b2b2b] pb-8 mb-12">
            <span className="text-[10px] text-[#6b6b6b] font-bold uppercase tracking-wider">// QUERIES</span>
            <h2 className="text-sm font-bold text-[#ffffff] mt-2 uppercase tracking-wide">SUPPORTED TARGET ENQUIRIES</h2>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 max-w-4xl">
            <div className="p-5 border border-[#2b2b2b] bg-[#181818]/20 flex flex-col justify-between gap-4">
              <div className="flex items-center justify-between text-[10px] text-[#6b6b6b]">
                <span>INTENT: OVERVIEW</span>
                <Activity className="h-3.5 w-3.5 text-[#d4af37]" />
              </div>
              <p className="text-xs text-[#ffffff] mt-2 font-semibold font-mono">"Summarize this repository and explain the codebase layout."</p>
              <p className="text-[11px] text-[#e5e5e5]/80 leading-normal border-t border-[#2b2b2b] pt-3">
                Dispatches a query to load configuration files (e.g. package.json) and README paths to render high-level project summaries.
              </p>
            </div>

            <div className="p-5 border border-[#2b2b2b] bg-[#181818]/20 flex flex-col justify-between gap-4">
              <div className="flex items-center justify-between text-[10px] text-[#6b6b6b]">
                <span>INTENT: HYBRID</span>
                <Code className="h-3.5 w-3.5 text-[#d4af37]" />
              </div>
              <p className="text-xs text-[#ffffff] mt-2 font-semibold font-mono">"How does this app handle database connection retries?"</p>
              <p className="text-[11px] text-[#e5e5e5]/80 leading-normal border-t border-[#2b2b2b] pt-3">
                Runs vector matches combined with GIN text searches to locate function nodes, outputting cited lines segments.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* FAQ Section */}
      <section className="py-16 border-b border-[#2b2b2b]">
        <div className="max-w-3xl mx-auto px-6">
          <div className="text-center mb-12 flex flex-col items-center">
            <div className="inline-flex h-8 w-8 bg-[#181818] flex items-center justify-center text-[#d4af37] border border-[#2b2b2b] mb-4 select-none">
              <HelpCircle className="h-4.5 w-4.5" />
            </div>
            <h2 className="text-sm font-bold text-[#ffffff] uppercase tracking-wide">ENGINE FAQ</h2>
            <p className="text-[10px] text-[#6b6b6b] mt-1 uppercase tracking-wider">SYSTEM CONSTRAINTS AND LIMITS</p>
          </div>

          <Accordion items={faqItems} />
        </div>
      </section>

      {/* Access Form CTA */}
      <section className="py-16 text-center relative overflow-hidden bg-[#0a0a0a]">
        <div className="max-w-4xl mx-auto px-6">
          <h2 className="text-xs font-bold text-[#ffffff] uppercase tracking-widest">// READY TO CLONE</h2>
          <p className="mt-4 text-xs text-[#e5e5e5]/85 max-w-md mx-auto leading-relaxed">
            Ingest your codebase into isolated database schemas to query parameters, dependencies, and syntaxes.
          </p>
          <div className="mt-8 flex justify-center">
            <Link to="/chat">
              <Button size="lg" className="shadow-none">
                <span>INITIALIZE WORKSPACE</span>
                <ChevronRight className="h-4 w-4" />
              </Button>
            </Link>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="py-6 border-t border-[#2b2b2b] bg-[#0a0a0a]/60 text-[10px] text-[#6b6b6b]/50">
        <div className="max-w-6xl mx-auto px-6 flex flex-col sm:flex-row items-center justify-between gap-4">
          <div>
            <span>© {new Date().getFullYear()} GITSENSE AI. COMPILER STACK.</span>
          </div>
          <div className="flex items-center gap-6">
            <span className="cursor-pointer hover:text-[#d4af37] transition-colors uppercase font-bold" onClick={() => setIsContactOpen(true)}>
              [ Contact support ]
            </span>
            <a href="https://github.com" target="_blank" rel="noreferrer" className="hover:text-[#d4af37] transition-colors uppercase font-bold">
              [ Github repo ]
            </a>
          </div>
        </div>
      </footer>

      {/* Contact modal */}
      <ContactModal isOpen={isContactOpen} onClose={() => setIsContactOpen(false)} />
    </div>
  );
}
