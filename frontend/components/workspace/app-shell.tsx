'use client';

import {
  Highlighter,
  LibraryBig,
  Menu,
  MessageSquareText,
  PanelRight,
  Plus,
  Search,
  Settings2,
  type LucideIcon,
} from 'lucide-react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { useCallback, useEffect, useState, type CSSProperties, type ReactNode } from 'react';
import { Button, Kbd, TooltipProvider } from '@/components/ui';
import { CommandPalette } from '@/components/workspace/command-palette';
import { EvidencePanel } from '@/components/workspace/evidence-panel';
import { ResizeHandle, usePanelWidth } from '@/components/workspace/resize-handle';
import { useWorkspace, type ConnectionState } from '@/components/workspace/workspace-provider';
import { cn } from '@/lib/utils';
import type { Surface } from '@/lib/types';

/** Each surface keeps one hue everywhere it appears, so colour teaches. */
const NAV: Array<{ id: Surface; label: string; icon: LucideIcon; tile: string }> = [
  { id: 'intelligence', label: 'Ask', icon: MessageSquareText, tile: 'bg-ios-orange' },
  { id: 'library', label: 'Library', icon: LibraryBig, tile: 'bg-ios-teal' },
  { id: 'review', label: 'Review', icon: Highlighter, tile: 'bg-ios-pink' },
  { id: 'settings', label: 'Settings', icon: Settings2, tile: 'bg-ios-gray' },
];

const TITLES: Record<Surface, string> = {
  intelligence: 'Ask',
  library: 'Library',
  review: 'Review',
  settings: 'Settings',
};

const CONNECTION: Record<ConnectionState, { label: string; detail: string; dot: string }> = {
  ready: { label: 'Local mode', detail: 'Nothing leaves this machine.', dot: 'bg-success' },
  offline: { label: 'API offline', detail: 'Start the backend to continue.', dot: 'bg-warning' },
  connecting: { label: 'Connecting', detail: 'Reaching the local API.', dot: 'bg-muted-foreground' },
};

export function AppShell({ surface, children }: { surface: Surface; children: ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const { connection, documents, evidence, selectEvidence } = useWorkspace();

  const [navOpen, setNavOpen] = useState(false);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [panelOpen, setPanelOpen] = useState(false);
  const [panelWidth, setPanelWidth] = usePanelWidth();

  useEffect(() => {
    setNavOpen(false);
  }, [pathname]);

  // Opening evidence reveals the panel; on narrow screens it is an overlay.
  useEffect(() => {
    if (evidence) setPanelOpen(true);
  }, [evidence]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault();
        setPaletteOpen((open) => !open);
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, []);

  const navigate = useCallback((next: Surface) => router.push(`/${next}`), [router]);

  const status = CONNECTION[connection];
  const showPanel = surface !== 'settings';

  return (
    <TooltipProvider delayDuration={400}>
      <div className="flex h-[100dvh] overflow-hidden bg-background">
        <a
          href="#main"
          className="sr-only focus:not-sr-only focus:absolute focus:left-3 focus:top-3 focus:z-[100] focus:rounded-md focus:bg-popover focus:px-3 focus:py-2 focus:text-sm focus:shadow-lg"
        >
          Skip to content
        </a>

        <aside
          aria-label="Primary"
          className={cn(
            'material z-50 flex w-[248px] shrink-0 flex-col border-r border-border',
            'max-lg:fixed max-lg:inset-y-0 max-lg:left-0 max-lg:transition-transform max-lg:duration-slow max-lg:ease-spring',
            navOpen ? 'max-lg:translate-x-0 max-lg:shadow-xl' : 'max-lg:-translate-x-full',
          )}
        >
          <div className="px-4 pb-3 pt-4">
            <Link href="/" className="flex items-center gap-2.5 rounded-lg px-1 py-1">
              <span className="icon-tile size-7 bg-gradient-to-br from-ios-orange to-ios-pink text-xs font-bold">
                D
              </span>
              <span className="min-w-0">
                <span className="block truncate text-sm font-semibold tracking-tight">DuckDocs</span>
                <span className="block truncate text-2xs text-muted-foreground">Evidence workspace</span>
              </span>
            </Link>
          </div>

          <div className="px-3 pb-2">
            <Button variant="secondary" className="w-full justify-start" onClick={() => navigate('intelligence')}>
              <Plus className="size-4" aria-hidden />
              New question
            </Button>
          </div>

          <nav aria-label="Workspace" className="flex-1 overflow-y-auto px-3 py-2">
            <p className="px-2 pb-1.5 pt-3 text-2xs font-semibold uppercase tracking-wider text-muted-foreground/70">
              Workspace
            </p>
            <ul className="space-y-0.5">
              {NAV.map((item) => {
                const Icon = item.icon;
                const active = item.id === surface;
                return (
                  <li key={item.id}>
                    <Link
                      href={`/${item.id}`}
                      aria-current={active ? 'page' : undefined}
                      className={cn(
                        'group flex h-9 items-center gap-2.5 rounded-lg px-2 text-sm font-medium',
                        'transition-colors duration-fast',
                        active
                          ? 'bg-primary/10 text-primary'
                          : 'text-muted-foreground hover:bg-muted hover:text-foreground',
                      )}
                    >
                      <span className={cn('icon-tile size-6', item.tile)}>
                        <Icon className="size-[13px]" strokeWidth={2.4} aria-hidden />
                      </span>
                      <span className="min-w-0 flex-1 truncate">{item.label}</span>
                      {item.id === 'library' && documents.length > 0 ? (
                        <span className="shrink-0 font-mono text-2xs tabular-nums text-muted-foreground">
                          {documents.length}
                        </span>
                      ) : null}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </nav>

          <div className="p-3">
            <div className="flex items-start gap-2.5 rounded-xl bg-secondary p-3">
              <span className={cn('mt-1 size-1.5 shrink-0 rounded-full', status.dot)} aria-hidden />
              <div className="min-w-0">
                <p className="text-xs font-medium text-foreground">{status.label}</p>
                <p className="mt-0.5 text-2xs leading-snug text-muted-foreground">{status.detail}</p>
              </div>
            </div>
          </div>
        </aside>

        {navOpen ? (
          <div
            className="fixed inset-0 z-40 animate-fade-in bg-black/40 lg:hidden"
            onClick={() => setNavOpen(false)}
            aria-hidden
          />
        ) : null}

        <div className="flex min-w-0 flex-1 flex-col">
          <header className="material flex h-14 shrink-0 items-center gap-2 border-b border-border px-4">
            <Button
              variant="ghost"
              size="sm"
              className="size-9 p-0 lg:hidden"
              aria-label="Open navigation"
              onClick={() => setNavOpen(true)}
            >
              <Menu className="size-[18px]" />
            </Button>
            <h1 className="min-w-0 flex-1 truncate text-sm font-semibold">{TITLES[surface]}</h1>

            <button
              onClick={() => setPaletteOpen(true)}
              className={cn(
                'flex h-9 items-center gap-2 rounded-lg bg-secondary px-3 text-xs text-muted-foreground',
                'transition-colors duration-fast hover:bg-muted sm:w-56',
              )}
            >
              <Search className="size-3.5 shrink-0" aria-hidden />
              <span className="hidden flex-1 text-left sm:block">Search or jump to…</span>
              <Kbd>⌘K</Kbd>
            </button>

            {showPanel ? (
              <Button
                variant={panelOpen ? 'subtle' : 'ghost'}
                size="sm"
                className="size-9 p-0"
                aria-pressed={panelOpen}
                aria-label={panelOpen ? 'Hide evidence panel' : 'Show evidence panel'}
                onClick={() => setPanelOpen((open) => !open)}
              >
                <PanelRight className="size-[18px]" />
              </Button>
            ) : null}
          </header>

          <div className="flex min-h-0 flex-1">
            <main id="main" className="min-w-0 flex-1 overflow-y-auto">
              {children}
            </main>

            {showPanel && panelOpen ? (
              <>
                <ResizeHandle width={panelWidth} onResize={setPanelWidth} />
                <div
                  className="shrink-0 max-lg:!w-0"
                  style={{ width: `${panelWidth}px` } as CSSProperties}
                >
                  <EvidencePanel
                    evidence={evidence}
                    onClose={() => {
                      setPanelOpen(false);
                      selectEvidence(null);
                    }}
                  />
                </div>
              </>
            ) : null}
          </div>
        </div>

        <CommandPalette
          open={paletteOpen}
          onClose={() => setPaletteOpen(false)}
          onNavigate={(next) => {
            setPaletteOpen(false);
            navigate(next);
          }}
        />
      </div>
    </TooltipProvider>
  );
}
