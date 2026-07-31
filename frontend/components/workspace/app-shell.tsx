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
import { useCallback, useEffect, useState, type ReactNode } from 'react';
import { IconButton, Kbd } from '@/components/ui';
import { CommandPalette } from '@/components/workspace/command-palette';
import { EvidencePanel } from '@/components/workspace/evidence-panel';
import { useWorkspace, type ConnectionState } from '@/components/workspace/workspace-provider';
import type { Surface } from '@/lib/types';

const NAV: Array<{ id: Surface; label: string; icon: LucideIcon }> = [
  { id: 'intelligence', label: 'Ask', icon: MessageSquareText },
  { id: 'library', label: 'Library', icon: LibraryBig },
  { id: 'review', label: 'Review', icon: Highlighter },
  { id: 'settings', label: 'Settings', icon: Settings2 },
];

const TITLES: Record<Surface, string> = {
  intelligence: 'Ask',
  library: 'Library',
  review: 'Review',
  settings: 'Settings',
};

const CONNECTION_COPY: Record<ConnectionState, { label: string; detail: string; dot: string }> = {
  ready: { label: 'Local mode', detail: 'Nothing leaves this machine.', dot: 'dot-ready' },
  offline: { label: 'API offline', detail: 'Start the backend to continue.', dot: 'dot-offline' },
  connecting: { label: 'Connecting', detail: 'Reaching the local API.', dot: 'dot-connecting' },
};

export function AppShell({ surface, children }: { surface: Surface; children: ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const { connection, documents, evidence, selectEvidence } = useWorkspace();

  const [navOpen, setNavOpen] = useState(false);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [panelOpen, setPanelOpen] = useState(false);

  // Close the mobile drawer on navigation so it never lingers over the
  // surface the user just moved to.
  useEffect(() => {
    setNavOpen(false);
  }, [pathname]);

  // Opening evidence should reveal the panel on narrow screens, where it is
  // an overlay rather than a persistent column.
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

  const navigate = useCallback(
    (next: Surface) => {
      router.push(`/${next}`);
    },
    [router],
  );

  const status = CONNECTION_COPY[connection];
  const showPanel = surface !== 'settings';

  return (
    <div className="shell" data-nav={navOpen ? 'open' : 'closed'}>
      <a className="skip-link" href="#main">
        Skip to content
      </a>

      <aside className="sidebar" aria-label="Primary">
        <div className="sidebar-head">
          <Link href="/" className="brand">
            <span className="brand-mark" aria-hidden="true">
              D
            </span>
            <span>
              <span className="brand-name">DuckDocs</span>
              <span className="brand-sub">Evidence workspace</span>
            </span>
          </Link>
        </div>

        <div className="sidebar-action">
          <button className="btn btn-secondary btn-block" onClick={() => navigate('intelligence')}>
            <Plus size={15} strokeWidth={1.8} aria-hidden="true" />
            New question
          </button>
        </div>

        <nav className="sidebar-nav" aria-label="Workspace">
          <p className="nav-group-label">Workspace</p>
          {NAV.map((item) => {
            const Icon = item.icon;
            const active = item.id === surface;
            return (
              <Link
                key={item.id}
                href={`/${item.id}`}
                className="nav-item"
                aria-current={active ? 'page' : undefined}
              >
                <Icon size={16} strokeWidth={1.7} aria-hidden="true" />
                <span>{item.label}</span>
                {item.id === 'library' && documents.length > 0 ? (
                  <span className="nav-count">{documents.length}</span>
                ) : null}
              </Link>
            );
          })}
        </nav>

        <div className="sidebar-foot">
          <div className="status-card">
            <span className={`dot ${status.dot}`} aria-hidden="true" />
            <div>
              <strong>{status.label}</strong>
              <p>{status.detail}</p>
            </div>
          </div>
        </div>
      </aside>

      {navOpen ? <div className="scrim" onClick={() => setNavOpen(false)} aria-hidden="true" /> : null}

      <div className="stage">
        <header className="topbar">
          <IconButton
            icon={Menu}
            label="Open navigation"
            className="mobile-only"
            onClick={() => setNavOpen(true)}
          />
          <div className="topbar-title">
            <h1>{TITLES[surface]}</h1>
          </div>
          <div className="topbar-actions">
            <button className="trigger-search" onClick={() => setPaletteOpen(true)}>
              <Search size={14} strokeWidth={1.8} aria-hidden="true" />
              <span>Search or jump to…</span>
              <Kbd>⌘K</Kbd>
            </button>
            {showPanel ? (
              <IconButton
                icon={PanelRight}
                label={panelOpen ? 'Hide evidence panel' : 'Show evidence panel'}
                aria-pressed={panelOpen}
                onClick={() => setPanelOpen((open) => !open)}
              />
            ) : null}
          </div>
        </header>

        <div className="workspace">
          <main className="workspace-main" id="main">
            {children}
          </main>
          {showPanel && panelOpen ? (
            <EvidencePanel
              evidence={evidence}
              onClose={() => {
                setPanelOpen(false);
                selectEvidence(null);
              }}
            />
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
  );
}
