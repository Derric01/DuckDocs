'use client';

import { Highlighter, LibraryBig, MessageSquareText, Search, Settings2, type LucideIcon } from 'lucide-react';
import { useEffect, useMemo, useRef, useState } from 'react';
import { cn } from '@/lib/utils';
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
      className="fixed inset-0 z-[80] flex animate-fade-in items-start justify-center bg-black/40 px-4 pb-4 pt-[12vh] backdrop-blur-[2px]"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Command palette"
        className="w-full max-w-lg animate-scale-in overflow-hidden rounded-lg border border-border bg-popover shadow-xl"
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
        <div className="flex items-center gap-3 border-b border-border px-4 py-3.5 text-muted-foreground">
          <Search className="size-4 shrink-0" aria-hidden />
          <input
            ref={inputRef}
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search commands…"
            aria-label="Search commands"
            className="flex-1 bg-transparent text-md text-foreground outline-none placeholder:text-muted-foreground/80"
          />
        </div>
        {results.length === 0 ? (
          <p className="px-6 py-8 text-center text-sm text-muted-foreground">No matching commands.</p>
        ) : (
          <div role="listbox" aria-label="Commands" className="max-h-80 overflow-y-auto p-2">
            {results.map((command, index) => {
              const Icon = command.icon;
              return (
                <button
                  key={command.id}
                  role="option"
                  aria-selected={index === active}
                  onMouseEnter={() => setActive(index)}
                  onClick={() => commit(index)}
                  className={cn(
                    'flex h-9 w-full items-center gap-3 rounded px-2.5 text-left text-sm transition-colors duration-fast',
                    index === active ? 'bg-accent-muted text-foreground' : 'text-muted-foreground',
                  )}
                >
                  <Icon
                    className={cn('size-4 shrink-0', index === active ? 'text-accent' : 'text-muted-foreground')}
                    aria-hidden
                  />
                  <span className="flex-1">{command.label}</span>
                  <span className="font-mono text-2xs opacity-60">{command.hint}</span>
                </button>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
