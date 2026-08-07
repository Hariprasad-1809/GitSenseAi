import React, { useState } from 'react';
import { Copy, Check, Terminal } from 'lucide-react';
import { toast } from 'sonner';

interface MarkdownRendererProps {
  content: string;
}

const formatInlineText = (text: string): React.ReactNode => {
  if (!text) return null;

  // Process inline code first
  const codeParts = text.split(/(`[^`]+`)/g);

  return codeParts.map((part, pIdx) => {
    if (part.startsWith('`') && part.endsWith('`') && part.length > 2) {
      return (
        <code key={pIdx} className="px-1.5 py-0.5 bg-[#181818] border border-[#2b2b2b] text-[#f5c542] font-mono text-[11px] rounded-none">
          {part.slice(1, -1)}
        </code>
      );
    }

    // Process bold/italic formatting within text token
    const tokens = part.split(/(\*\*\*.*?\*\*\*|\*\*.*?\*\*|\*.*?\*)/g);
    return tokens.map((token, tIdx) => {
      if (token.startsWith('***') && token.endsWith('***') && token.length > 6) {
        return <strong key={tIdx} className="font-bold text-[#ffffff]"><em>{token.slice(3, -3)}</em></strong>;
      }
      if (token.startsWith('**') && token.endsWith('**') && token.length > 4) {
        return <strong key={tIdx} className="font-bold text-[#ffffff]">{token.slice(2, -2)}</strong>;
      }
      if (token.startsWith('*') && token.endsWith('*') && token.length > 2) {
        return <em key={tIdx} className="italic text-[#e5e5e5]">{token.slice(1, -1)}</em>;
      }
      return token;
    });
  });
};

export function MarkdownRenderer({ content }: MarkdownRendererProps) {
  const parseMarkdown = (text: string) => {
    if (!text) return [];

    const blocks: Array<{ type: 'text' | 'code' | 'table'; content: string; language?: string; rows?: string[][] }> = [];
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
    const lines = text.split('\n');
    const elements: React.ReactNode[] = [];
    let i = 0;

    while (i < lines.length) {
      const line = lines[i];
      const trimmed = line.trim();

      // Check for horizontal divider rule
      if (trimmed === '---' || trimmed === '***' || trimmed === '___') {
        elements.push(<hr key={i} className="border-[#2b2b2b] my-4" />);
        i++;
        continue;
      }

      // Check for markdown table block
      if (trimmed.startsWith('|') && trimmed.endsWith('|')) {
        const tableLines: string[] = [];
        while (i < lines.length && lines[i].trim().startsWith('|') && lines[i].trim().endsWith('|')) {
          tableLines.push(lines[i].trim());
          i++;
        }

        // Parse table rows
        const parsedRows = tableLines
          .filter(r => !r.match(/^\|[\s:\|-]+\|$/)) // Filter out markdown delimiter row e.g. |---|---|
          .map(rowStr => rowStr.split('|').slice(1, -1).map(cell => cell.trim()));

        if (parsedRows.length > 0) {
          const headerRow = parsedRows[0];
          const bodyRows = parsedRows.slice(1);

          elements.push(
            <div key={`table-${i}`} className="my-4 border border-[#2b2b2b] overflow-x-auto bg-[#181818]/40">
              <table className="w-full text-left border-collapse text-xs font-mono">
                <thead>
                  <tr className="border-b border-[#2b2b2b] bg-[#181818]/80 text-[#f5c542] font-bold">
                    {headerRow.map((cell, cIdx) => (
                      <th key={cIdx} className="px-3 py-2 border-r border-[#2b2b2b] last:border-r-0">
                        {formatInlineText(cell)}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#2b2b2b]/50">
                  {bodyRows.map((row, rIdx) => (
                    <tr key={rIdx} className="hover:bg-[#181818]/60 transition-colors">
                      {row.map((cell, cIdx) => (
                        <td key={cIdx} className="px-3 py-2 border-r border-[#2b2b2b] last:border-r-0 text-[#e5e5e5]">
                          {formatInlineText(cell)}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          );
        }
        continue;
      }

      // Headers (strip leading # symbols and render clean styled headers)
      const headerMatch = trimmed.match(/^(#{1,6})\s+(.*)/);
      if (headerMatch) {
        const level = headerMatch[1].length;
        const headerText = headerMatch[2].replace(/^(\*\*|\*)+(.*?)(\*\*|\*)+$/, '$2');

        if (level === 1) {
          elements.push(
            <h1 key={i} className="text-sm font-bold text-[#ffffff] mt-5 mb-2 uppercase tracking-wider font-mono border-b border-[#2b2b2b] pb-1.5">
              // {formatInlineText(headerText)}
            </h1>
          );
        } else if (level === 2) {
          elements.push(
            <h2 key={i} className="text-xs font-bold text-[#ffffff] mt-4 mb-2 uppercase tracking-wide font-mono">
              // {formatInlineText(headerText)}
            </h2>
          );
        } else if (level === 3) {
          elements.push(
            <h3 key={i} className="text-xs font-bold text-[#f5c542] mt-3.5 mb-1.5 font-mono">
              {formatInlineText(headerText)}
            </h3>
          );
        } else {
          elements.push(
            <h4 key={i} className="text-[11px] font-bold text-[#e5e5e5] mt-3 mb-1 font-mono">
              {formatInlineText(headerText)}
            </h4>
          );
        }
        i++;
        continue;
      }

      // Bullet Lists
      if (trimmed.startsWith('- ') || trimmed.startsWith('* ') || trimmed.startsWith('+ ')) {
        const listText = trimmed.slice(2);
        elements.push(
          <ul key={i} className="list-none ml-4 my-1 text-[#e5e5e5] font-mono text-xs">
            <li className="flex items-start gap-2">
              <span className="text-[#d4af37] font-bold select-none">»</span>
              <span>{formatInlineText(listText)}</span>
            </li>
          </ul>
        );
        i++;
        continue;
      }

      // Number Lists
      const numberListMatch = trimmed.match(/^(\d+)\.\s+(.*)/);
      if (numberListMatch) {
        elements.push(
          <ol key={i} className="list-none ml-4 my-1 text-[#e5e5e5] font-mono text-xs">
            <li className="flex items-start gap-2">
              <span className="text-zinc-500 font-bold select-none">{numberListMatch[1]}.</span>
              <span>{formatInlineText(numberListMatch[2])}</span>
            </li>
          </ol>
        );
        i++;
        continue;
      }

      if (!trimmed) {
        elements.push(<div key={i} className="h-1.5" />);
        i++;
        continue;
      }

      elements.push(
        <p key={i} className="text-[#e5e5e5] leading-relaxed my-1 font-mono text-xs">
          {formatInlineText(line)}
        </p>
      );

      i++;
    }

    return elements;
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
