import React, { useState } from 'react';
import { Copy, Check, Terminal } from 'lucide-react';
import { toast } from 'sonner';

interface MarkdownRendererProps {
  content: string;
}

export function MarkdownRenderer({ content }: MarkdownRendererProps) {
  const parseMarkdown = (text: string) => {
    if (!text) return [];

    const blocks: Array<{ type: 'text' | 'code'; content: string; language?: string }> = [];
    const codeBlockRegex = /```(\w*)\n([\s\S]*?)```/g;
    
    let lastIndex = 0;
    let match;

    while ((match = codeBlockRegex.exec(text)) !== null) {
      if (match.index > lastIndex) {
        blocks.push({
          type: 'text',
          content: text.substring(lastIndex, match.index),
        });
      }

      blocks.push({
        type: 'code',
        language: match[1] || 'plaintext',
        content: match[2],
      });

      lastIndex = codeBlockRegex.lastIndex;
    }

    if (lastIndex < text.length) {
      blocks.push({
        type: 'text',
        content: text.substring(lastIndex),
      });
    }

    return blocks;
  };

  const renderTextContent = (text: string) => {
    return text.split('\n').map((line, idx) => {
      const trimmed = line.trim();
      
      // Headers
      if (trimmed.startsWith('# ')) {
        return <h1 key={idx} className="text-sm font-bold text-[#ffffff] mt-4 mb-2 uppercase tracking-wider font-mono border-b border-[#2b2b2b] pb-1">// {trimmed.slice(2)}</h1>;
      }
      if (trimmed.startsWith('## ')) {
        return <h2 key={idx} className="text-xs font-bold text-[#ffffff] mt-3.5 mb-2 uppercase tracking-wide font-mono">// {trimmed.slice(3)}</h2>;
      }
      if (trimmed.startsWith('### ')) {
        return <h3 key={idx} className="text-xs font-bold text-[#e5e5e5] mt-3 mb-1.5 font-mono">{trimmed.slice(4)}</h3>;
      }

      // Bullet Lists
      if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
        return (
          <ul key={idx} className="list-none ml-4 my-1 text-[#e5e5e5] font-mono text-xs">
            <li className="flex items-start gap-2">
              <span className="text-[#d4af37] font-bold">»</span>
              <span>{parseInlineCode(trimmed.slice(2))}</span>
            </li>
          </ul>
        );
      }

      // Number Lists
      const numberListMatch = trimmed.match(/^(\d+)\.\s(.*)/);
      if (numberListMatch) {
        return (
          <ol key={idx} className="list-none ml-4 my-1 text-[#e5e5e5] font-mono text-xs">
            <li className="flex items-start gap-2">
              <span className="text-zinc-650 font-bold">{numberListMatch[1]}.</span>
              <span>{parseInlineCode(numberListMatch[2])}</span>
            </li>
          </ol>
        );
      }

      if (!trimmed) {
        return <div key={idx} className="h-1.5" />;
      }

      return (
        <p key={idx} className="text-[#e5e5e5] leading-relaxed my-1 font-mono text-xs">
          {parseInlineCode(line)}
        </p>
      );
    });
  };

  const parseInlineCode = (line: string) => {
    const parts = line.split(/(`[^`]+`)/g);
    return parts.map((part, index) => {
      if (part.startsWith('`') && part.endsWith('`')) {
        return (
          <code key={index} className="px-1.5 py-0.5 bg-[#181818] border border-[#2b2b2b] text-[#f5c542] font-mono text-[11px] rounded-none">
            {part.slice(1, -1)}
          </code>
        );
      }
      return part;
    });
  };

  const blocks = parseMarkdown(content);

  return (
    <div className="space-y-2">
      {blocks.map((block, idx) => {
        if (block.type === 'code') {
          return (
            <CodeBlock
              key={idx}
              code={block.content.trim()}
              language={block.language}
            />
          );
        }
        return <div key={idx}>{renderTextContent(block.content)}</div>;
      })}
    </div>
  );
}

interface CodeBlockProps {
  code: string;
  language?: string;
}

function CodeBlock({ code, language }: CodeBlockProps) {
  const [copied, setCopied] = useState(false);

  const copyToClipboard = async () => {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      toast.success('Copied.');
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      toast.error('Failed.');
    }
  };

  return (
    <div className="my-3 border border-[#2b2b2b] bg-[#181818] rounded-none overflow-hidden text-[#e5e5e5] max-w-full font-mono">
      <div className="flex items-center justify-between px-4 py-2 border-b border-[#2b2b2b] bg-[#181818]/60 text-[10px] text-zinc-550 uppercase tracking-wider">
        <div className="flex items-center gap-1.5">
          <Terminal className="h-3 w-3 text-zinc-650" />
          <span>{language || 'src'}</span>
        </div>
        <button
          onClick={copyToClipboard}
          className="flex items-center gap-1 hover:text-[#d4af37] transition-colors p-1 border border-transparent hover:border-[#2b2b2b] bg-transparent hover:bg-[#181818]/60 cursor-pointer"
        >
          {copied ? (
            <>
              <Check className="h-3 w-3 text-[#4ade80]" />
              <span className="text-[9px] text-[#4ade80] font-semibold">Done</span>
            </>
          ) : (
            <>
              <span>[Copy]</span>
            </>
          )}
        </button>
      </div>

      <div className="overflow-x-auto p-4 max-w-full">
        <pre className="font-mono text-xs leading-relaxed text-[#ffffff] select-text whitespace-pre">
          {code}
        </pre>
      </div>
    </div>
  );
}
