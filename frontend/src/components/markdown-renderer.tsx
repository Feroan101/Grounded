"use client";

import React from "react";

interface MarkdownRendererProps {
  content: string;
}

function renderInlineMarkdown(text: string): React.ReactNode[] {
  const parts: React.ReactNode[] = [];
  let key = 0;

  const regex = /(\*\*(.+?)\*\*|__(.+?)__|`([^`]+)`|\[([^\]]+)\]\(([^)]+)\)|_([^_]+)_|(\*([^*]+)\*))/g;
  let lastIndex = 0;
  let match;

  while ((match = regex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push(text.slice(lastIndex, match.index));
    }

    if (match[2] || match[3]) {
      parts.push(<strong key={key++}>{match[2] || match[3]}</strong>);
    } else if (match[4]) {
      parts.push(
        <code
          key={key++}
          className="rounded bg-espresso/10 px-1.5 py-0.5 text-[0.9em] font-mono"
        >
          {match[4]}
        </code>
      );
    } else if (match[5] && match[6]) {
      parts.push(
        <a
          key={key++}
          href={match[6]}
          target="_blank"
          rel="noopener noreferrer"
          className="text-espresso underline underline-offset-2 decoration-cafe/40 transition-colors hover:decoration-espresso"
        >
          {match[5]}
        </a>
      );
    } else if (match[7]) {
      parts.push(<em key={key++}>{match[7]}</em>);
    } else if (match[9]) {
      parts.push(<em key={key++}>{match[9]}</em>);
    }

    lastIndex = match.index + match[0].length;
  }

  if (lastIndex < text.length) {
    parts.push(text.slice(lastIndex));
  }

  return parts;
}

function parseBlocks(content: string): React.ReactNode[] {
  const blocks: React.ReactNode[] = [];
  const lines = content.split("\n");
  let key = 0;
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];

    // Code block (```)
    if (line.trimStart().startsWith("```")) {
      const lang = line.trimStart().slice(3).trim();
      const codeLines: string[] = [];
      i++;
      while (i < lines.length && !lines[i].trimStart().startsWith("```")) {
        codeLines.push(lines[i]);
        i++;
      }
      i++; // skip closing ```
      blocks.push(
        <div key={key++} className="overflow-x-auto rounded-lg border border-cafe/15 bg-bean/5">
          {lang && (
            <div className="border-b border-cafe/10 px-3 py-1">
              <span className="text-[10px] font-medium uppercase tracking-wider text-latte/50">
                {lang}
              </span>
            </div>
          )}
          <pre className="p-3 text-[13px] leading-relaxed font-mono text-bean/80">
            <code>{codeLines.join("\n")}</code>
          </pre>
        </div>
      );
      continue;
    }

    // Headings
    const heading = line.match(/^(#{1,4})\s+(.*)$/);
    if (heading) {
      const level = heading[1].length;
      const text = heading[2];
      const contentNode = renderInlineMarkdown(text);
      if (level <= 2) {
        blocks.push(
          <h3 key={key++} className="text-[17px] font-semibold tracking-tight text-espresso">
            {contentNode}
          </h3>
        );
      } else {
        blocks.push(
          <h4 key={key++} className="text-[15px] font-semibold text-espresso">
            {contentNode}
          </h4>
        );
      }
      i++;
      continue;
    }

    // Blockquote
    if (/^>\s?/.test(line)) {
      const quoteLines: string[] = [];
      while (i < lines.length && /^>\s?/.test(lines[i])) {
        quoteLines.push(lines[i].replace(/^>\s?/, ""));
        i++;
      }
      blocks.push(
        <blockquote
          key={key++}
          className="border-l-2 border-latte/40 pl-3 text-[15px] leading-relaxed text-latte italic"
        >
          {renderInlineMarkdown(quoteLines.join("\n"))}
        </blockquote>
      );
      continue;
    }

    // Unordered list
    if (/^[\s]*[-*+]\s/.test(line)) {
      const listItems: string[] = [];
      while (i < lines.length && /^[\s]*[-*+]\s/.test(lines[i])) {
        listItems.push(lines[i].replace(/^[\s]*[-*+]\s/, ""));
        i++;
      }
      blocks.push(
        <ul key={key++} className="ml-5 list-disc space-y-1.5 text-[15px] leading-relaxed marker:text-latte/60">
          {listItems.map((item, li) => (
            <li key={li}>{renderInlineMarkdown(item)}</li>
          ))}
        </ul>
      );
      continue;
    }

    // Ordered list
    if (/^[\s]*\d+\.\s/.test(line)) {
      const listItems: string[] = [];
      while (i < lines.length && /^[\s]*\d+\.\s/.test(lines[i])) {
        listItems.push(lines[i].replace(/^[\s]*\d+\.\s/, ""));
        i++;
      }
      blocks.push(
        <ol key={key++} className="ml-5 list-decimal space-y-1.5 text-[15px] leading-relaxed marker:text-latte/60">
          {listItems.map((item, li) => (
            <li key={li}>{renderInlineMarkdown(item)}</li>
          ))}
        </ol>
      );
      continue;
    }

    // Empty line
    if (line.trim() === "") {
      i++;
      continue;
    }

    // Regular paragraph
    const paraLines: string[] = [];
    while (
      i < lines.length &&
      lines[i].trim() !== "" &&
      !lines[i].trimStart().startsWith("```") &&
      !/^#{1,4}\s/.test(lines[i]) &&
      !/^>\s?/.test(lines[i]) &&
      !/^[\s]*[-*+]\s/.test(lines[i]) &&
      !/^[\s]*\d+\.\s/.test(lines[i])
    ) {
      paraLines.push(lines[i]);
      i++;
    }
    if (paraLines.length > 0) {
      blocks.push(
        <p key={key++} className="text-[15px] leading-relaxed">
          {renderInlineMarkdown(paraLines.join("\n"))}
        </p>
      );
    }
  }

  return blocks;
}

export function MarkdownRenderer({ content }: MarkdownRendererProps) {
  return <div className="space-y-3">{parseBlocks(content)}</div>;
}