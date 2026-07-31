'use client';

import { Highlighter, LibraryBig, MessageSquareText, Search, Settings2, type LucideIcon } from 'lucide-react';
import { useEffect, useMemo, useRef, useState } from 'react';
import type { Surface } from '@/lib/types';

interface Command {
  id: Surface;
  label: string;
  hint: string;
  icon: LucideIcon;
}

const COMMANDS: Command[] = [
  { id: 'intelligence', label: 'Ask your library', hint: 'Grounded question answering', icon: MessageSquareText },
  { id: 'library', label: 'Open library', hint: 'Browse and add documents', icon: LibraryBig },
  { id: 'review', label: 'Open review', hint: 'Documents needing attention', icon: Highlighter },
  { id: 'settings', label: 'Open settings', hint: 'Providers, OCR, and privacy', icon: Settings2 },
];

export function CommandPalette({
  open,
  onClose,
  onNavigate,
}: {
  open: boolean;
  onClose: () => void;
  onNavigate: (surface: Surface) => void;
}) {
  const [query, setQuery] = useState('');
  const [active, setActive] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  const results = useMemo(() => {
    const term = query.trim().toLowerCase();
    if (!term) return COMMANDS;
    return COMMANDS.filter(
      (command) => command.label.toLowerCase().includes(term) || command.hint.toLowerCase().includes(term),
    );
  }, [query]);

  useEffect(() => {
    if (!open) {
      setQuery('');
      setActive(0);
      return;
    }
    inputRef.current?.focus();
  }, [open]);

  // Keep the highlighted row inside the result set as it narrows.
  useEffect(() => {
    setActive((current) => Math.min(current, Math.max(0, results.length - 1)));
  }, [results.length]);

  if (!open) return null;

  const commit = (index: number) => {
    const command = results[index];
    if (command) onNavigate(command.id);
  };

  return (
    <div
      className="palette-overlay"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div
        className="palette"
        role="dialog"
        aria-modal="true"
        aria-label="Command palette"
        onKeyDown={(event) => {
          if (event.key === 'Escape') {
            event.preventDefault();
            onClose();
          } else if (event.key === 'ArrowDown') {
            event.preventDefault();
            setActive((current) => (current + 1) % Math.max(1, results.length));
          } else if (event.key === 'ArrowUp') {
            event.preventDefault();
            setActive((current) => (current - 1 + results.length) % Math.max(1, results.length));
          } else if (event.key === 'Enter') {
            event.preventDefault();
            commit(active);
          }
        }}
      >
        <div className="palette-input">
          <Search size={16} strokeWidth={1.8} aria-hidden="true" />
          <input
            ref={inputRef}
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search commands…"
            aria-label="Search commands"
          />
        </div>
        {results.length === 0 ? (
          <p className="palette-empty">No matching commands.</p>
        ) : (
          <div className="palette-list" role="listbox" aria-label="Commands">
            {results.map((command, index) => {
              const Icon = command.icon;
              return (
                <button
                  key={command.id}
                  className="palette-item"
                  role="option"
                  aria-selected={index === active}
                  data-active={index === active}
                  onMouseEnter={() => setActive(index)}
                  onClick={() => commit(index)}
                >
                  <Icon size={16} strokeWidth={1.7} aria-hidden="true" />
                  <span>{command.label}</span>
                  <span className="mono">{command.hint}</span>
                </button>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
