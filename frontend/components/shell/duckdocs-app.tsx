'use client';

import {
  AlertCircle,
  ArrowDownToLine,
  ArrowUpRight,
  Bell,
  BookOpen,
  Check,
  ChevronDown,
  ChevronRight,
  CircleHelp,
  Command,
  Copy,
  Database,
  FileArchive,
  FileCode2,
  FileImage,
  FileSpreadsheet,
  FileText,
  FolderOpen,
  Gauge,
  Highlighter,
  History,
  Keyboard,
  LayoutGrid,
  LibraryBig,
  ListFilter,
  LoaderCircle,
  LockKeyhole,
  Menu,
  MessageSquareText,
  Moon,
  MoreHorizontal,
  PanelRight,
  Paperclip,
  Plus,
  Search,
  Send,
  Settings2,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
  Split,
  Sun,
  Upload,
  X,
  type LucideIcon,
} from 'lucide-react';
import { usePathname, useRouter } from 'next/navigation';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { ApiError, duckDocsApi } from '@/lib/api/client';
import type { DocumentRecord, EvidenceRecord, MessageRecord, Surface } from '@/lib/types';

interface DuckDocsAppProps {
  initialSurface: Surface;
}

type ApiState = 'connecting' | 'ready' | 'offline';

const navItems: Array<{ id: Surface; label: string; icon: LucideIcon; hint: string }> = [
  { id: 'library', label: 'Library', icon: LibraryBig, hint: 'Browse documents' },
  { id: 'intelligence', label: 'Intelligence', icon: Sparkles, hint: 'Ask and search' },
  { id: 'review', label: 'Review', icon: Highlighter, hint: 'Annotations and compare' },
  { id: 'settings', label: 'Settings', icon: Settings2, hint: 'Providers and privacy' },
];

const surfaceMeta: Record<Surface, { label: string; title: string; subtitle: string }> = {
  library: { label: 'Library', title: 'Your document library', subtitle: 'A private index of the files you choose to work with.' },
  intelligence: { label: 'Intelligence', title: 'Ask your library', subtitle: 'Search, reason, and verify without leaving the source behind.' },
  review: { label: 'Review', title: 'Review workspace', subtitle: 'Keep evidence, notes, and version decisions in one place.' },
  settings: { label: 'Settings', title: 'Workspace settings', subtitle: 'Control providers, privacy boundaries, paths, and density.' },
};

function formatFileIcon(type: string): LucideIcon {
  if (type === 'CSV') return FileSpreadsheet;
  if (type === 'PNG' || type === 'JPG') return FileImage;
  if (type === 'TS' || type === 'PY' || type === 'JS') return FileCode2;
  if (type === 'ZIP') return FileArchive;
  return FileText;
}

function currentTimestamp(): string {
  return new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function describeApiIssue(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  return 'DuckDocs API is not reachable. Start the backend to use live documents.';
}

function offlineAnswer(): { content: string; citations: EvidenceRecord[] } {
  return {
    content: 'DuckDocs cannot answer until the local API is running. Start the backend, add documents, then ask again.',
    citations: [],
  };
}

function StatusBadge({ status }: { status: DocumentRecord['status'] }) {
  const config: Record<DocumentRecord['status'], { label: string; className: string; icon: LucideIcon }> = {
    ready: { label: 'Ready', className: 'status-ready', icon: Check },
    processing: { label: 'Processing', className: 'status-processing', icon: LoaderCircle },
    review: { label: 'Needs review', className: 'status-review', icon: AlertCircle },
    failed: { label: 'Failed', className: 'status-failed', icon: AlertCircle },
  };
  const current = config[status];
  const Icon = current.icon;
  return (
    <span className={`status-badge ${current.className}`} aria-label={`Document status: ${current.label}`}>
      <Icon size={13} strokeWidth={1.8} aria-hidden="true" />
      {current.label}
    </span>
  );
}

function CitationChip({ evidence, onClick }: { evidence: EvidenceRecord; onClick: () => void }) {
  return (
    <button className="citation-chip" onClick={onClick} aria-label={`Open citation from ${evidence.documentName}, page ${evidence.page}`}>
      <span>[{evidence.id.slice(-1)}]</span>
      <span className="citation-chip-dot" aria-hidden="true" />
    </button>
  );
}

function EmptyState({ icon: Icon, title, description, action }: { icon: LucideIcon; title: string; description: string; action?: React.ReactNode }) {
  return (
    <div className="empty-state">
      <div className="empty-state-icon"><Icon size={22} strokeWidth={1.6} /></div>
      <h3>{title}</h3>
      <p>{description}</p>
      {action}
    </div>
  );
}

function NavRail({ activeSurface, documentCount, onNavigate, onCommand }: { activeSurface: Surface; documentCount: number; onNavigate: (surface: Surface) => void; onCommand: () => void }) {
  return (
    <aside className="nav-rail">
      <div className="brand-lockup" aria-label="DuckDocs home">
        <div className="brand-mark">D</div>
        <div className="brand-copy"><strong>DuckDocs</strong><span>Waymark workspace</span></div>
      </div>

      <button className="new-work-button" onClick={() => onNavigate('intelligence')}>
        <Plus size={16} strokeWidth={2} />
        <span>New question</span>
        <kbd>Ctrl Enter</kbd>
      </button>

      <nav className="surface-nav" aria-label="Primary">
        <div className="nav-section-label">Workspace</div>
        {navItems.map((item) => {
          const Icon = item.icon;
          const active = item.id === activeSurface;
          return (
            <button key={item.id} className={`nav-item ${active ? 'active' : ''}`} onClick={() => onNavigate(item.id)} aria-current={active ? 'page' : undefined}>
              <Icon size={18} strokeWidth={active ? 2 : 1.6} />
              <span>{item.label}</span>
              {item.id === 'library' && <span className="nav-count">{documentCount}</span>}
            </button>
          );
        })}
      </nav>

      <div className="rail-lower">
        <div className="local-card">
          <div className="local-card-heading"><span className="live-indicator" /> Local mode</div>
          <p>Nothing leaves this machine unless you configure a provider.</p>
          <button onClick={() => onNavigate('settings')}>Review privacy <ArrowUpRight size={13} /></button>
        </div>
        <button className="command-shortcut" onClick={onCommand}>
          <Command size={16} /><span>Command palette</span><kbd>Ctrl K</kbd>
        </button>
        <div className="user-row">
          <div className="avatar">ME</div>
          <div><strong>You</strong><span>Personal workspace</span></div>
          <MoreHorizontal size={17} className="muted-icon" />
        </div>
      </div>
    </aside>
  );
}

function TopBar({ surface, apiState, onCommand, onToggleNav, onOpenEvidence, hasEvidence }: { surface: Surface; apiState: ApiState; onCommand: () => void; onToggleNav: () => void; onOpenEvidence: () => void; hasEvidence: boolean }) {
  const meta = surfaceMeta[surface];
  const networkLabel = apiState === 'ready' ? 'Local API' : apiState === 'connecting' ? 'Connecting' : 'Offline';
  return (
    <header className="top-bar">
      <button className="mobile-menu" onClick={onToggleNav} aria-label="Open navigation"><Menu size={20} /></button>
      <div className="top-context"><span className="top-context-label">Workspace</span><ChevronRight size={13} /><strong>{meta.label}</strong></div>
      <div className="top-actions">
        <button className="command-trigger" onClick={onCommand}><Search size={15} /><span>Search documents and ask</span><kbd>Ctrl K</kbd></button>
        <span className={`network-state ${apiState}`}><span className="live-indicator" />{networkLabel}</span>
        <button className="icon-button" aria-label="Notifications"><Bell size={17} /></button>
        {surface !== 'settings' && <button className={`icon-button evidence-toggle ${hasEvidence ? 'has-evidence' : ''}`} onClick={onOpenEvidence} aria-label="Open evidence pane"><PanelRight size={17} /></button>}
      </div>
    </header>
  );
}

function CommandPalette({ open, onClose, onNavigate }: { open: boolean; onClose: () => void; onNavigate: (surface: Surface) => void }) {
  const [query, setQuery] = useState('');
  useEffect(() => {
    if (!open) return;
    const handler = (event: KeyboardEvent) => { if (event.key === 'Escape') onClose(); };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [open, onClose]);
  if (!open) return null;
  const commands = [
    { label: 'Ask a question', hint: 'Open Intelligence', icon: MessageSquareText, surface: 'intelligence' as Surface },
    { label: 'Browse library', hint: 'Open Library', icon: LibraryBig, surface: 'library' as Surface },
    { label: 'Review annotations', hint: 'Open Review', icon: Highlighter, surface: 'review' as Surface },
    { label: 'Configure providers', hint: 'Open Settings', icon: Settings2, surface: 'settings' as Surface },
  ].filter((item) => `${item.label} ${item.hint}`.toLowerCase().includes(query.toLowerCase()));
  return (
    <div className="command-backdrop" onMouseDown={onClose}>
      <div className="command-dialog" role="dialog" aria-modal="true" aria-label="Command palette" onMouseDown={(event) => event.stopPropagation()}>
        <div className="command-input-row"><Search size={18} /><input autoFocus value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search actions or documents" /><kbd>ESC</kbd></div>
        <div className="command-list">
          <div className="command-list-label">Jump to</div>
          {commands.map((item) => { const Icon = item.icon; return <button key={item.label} className="command-item" onClick={() => { onNavigate(item.surface); onClose(); }}><span className="command-item-icon"><Icon size={17} /></span><span><strong>{item.label}</strong><small>{item.hint}</small></span><ChevronRight size={15} className="muted-icon" /></button>; })}
          {commands.length === 0 && <p className="command-empty">No actions match that search.</p>}
        </div>
        <div className="command-footer"><span><kbd>Up</kbd><kbd>Down</kbd> Navigate</span><span><kbd>Enter</kbd> Open</span><span><kbd>esc</kbd> Close</span></div>
      </div>
    </div>
  );
}

function EvidencePane({ evidence, onClose, onAnnotate }: { evidence: EvidenceRecord | null; onClose: () => void; onAnnotate: () => void }) {
  if (!evidence) {
    return <aside className="evidence-pane empty-evidence-pane"><div className="pane-heading"><div><span className="pane-kicker">Evidence</span><h2>Nothing selected</h2></div><button className="icon-button" onClick={onClose} aria-label="Close evidence pane"><X size={16} /></button></div><EmptyState icon={PanelRight} title="Select a citation to inspect it" description="Evidence opens here when you click a citation, search result, or reviewed passage." /></aside>;
  }
  return (
    <aside className="evidence-pane" aria-label="Evidence inspector">
      <div className="pane-heading"><div><span className="pane-kicker">Evidence inspector</span><h2>Source passage</h2></div><button className="icon-button" onClick={onClose} aria-label="Close evidence pane"><X size={16} /></button></div>
      <div className="evidence-source"><div className="file-icon small"><FileText size={16} /></div><div><strong>{evidence.documentName}</strong><span>{evidence.section}</span></div><button className="icon-button"><MoreHorizontal size={16} /></button></div>
      <div className="evidence-location"><span><BookOpen size={14} /> Page {evidence.page}</span><span className="mono">Lines {evidence.lines}</span><span className="relevance-high"><span className="confidence-dot" />{evidence.relevance} relevance</span></div>
      <div className="page-preview">
        <div className="preview-page-header"><span>{evidence.documentName.toUpperCase()}</span><span className="mono">PAGE {String(evidence.page).padStart(2, '0')}</span></div>
        <div className="preview-title">{evidence.section}</div>
        <div className="preview-line highlight-line">{evidence.snippet}</div>
        <div className="preview-page-footer"><span>Evidence anchor</span><span className="mono">{evidence.id}</span></div>
      </div>
      <div className="evidence-quote"><span className="quote-mark">"</span><p>{evidence.snippet}</p></div>
      <div className="evidence-actions"><button className="button button-secondary" onClick={onAnnotate}><Highlighter size={15} /> Annotate</button><button className="button button-secondary"><ArrowDownToLine size={15} /> Export passage</button></div>
      <div className="evidence-meta"><div><span>Anchor quality</span><strong>Line-level</strong></div><div><span>Relevance</span><strong className="confidence-text">{evidence.relevance}</strong></div><div><span>Source</span><strong>Local index</strong></div></div>
    </aside>
  );
}

function IntelligenceSurface({
  messages,
  question,
  setQuestion,
  onAsk,
  onCitation,
  onOpenLibrary,
  onUpload,
  documentCount,
  apiState,
  asking,
}: {
  messages: MessageRecord[];
  question: string;
  setQuestion: (value: string) => void;
  onAsk: () => void;
  onCitation: (evidence: EvidenceRecord) => void;
  onOpenLibrary: () => void;
  onUpload: (files: FileList | File[]) => Promise<void>;
  documentCount: number;
  apiState: ApiState;
  asking: boolean;
}) {
  const fileRef = useRef<HTMLInputElement>(null);
  const [scopeOpen, setScopeOpen] = useState(false);
  const [scope, setScope] = useState('Entire library');
  const [pendingFiles, setPendingFiles] = useState<File[]>([]);
  const [uploading, setUploading] = useState(false);
  const [dragging, setDragging] = useState(false);

  const addDocuments = async (files: FileList | File[] | null) => {
    if (!files || files.length === 0) return;
    const list = Array.from(files);
    setPendingFiles(list);
    setUploading(true);
    try {
      await onUpload(list);
    } finally {
      setUploading(false);
      setPendingFiles([]);
      if (fileRef.current) fileRef.current.value = '';
    }
  };

  return (
    <section className="surface-content intelligence-surface">
      <div className="surface-header intelligence-header">
        <div>
          <span className="surface-kicker">INTELLIGENCE</span>
          <h1>Ask your library</h1>
          <p>Answers stay close to the documents that support them.</p>
        </div>
        <div className="header-actions">
          <div className="scope-select-wrap">
            <button className="scope-select" onClick={() => setScopeOpen(!scopeOpen)}>
              <FolderOpen size={15} />
              {scope}
              <ChevronDown size={14} />
            </button>
            {scopeOpen && (
              <div className="scope-menu">
                {['Entire library', 'Ready documents', 'Needs review'].map((item) => (
                  <button
                    key={item}
                    onClick={() => {
                      setScope(item);
                      setScopeOpen(false);
                    }}
                  >
                    {item}
                    {scope === item && <Check size={14} />}
                  </button>
                ))}
              </div>
            )}
          </div>
          <button className="icon-button" aria-label="Intelligence settings">
            <SlidersHorizontal size={17} />
          </button>
        </div>
      </div>

      <div className="chat-workspace">
        <div className="chat-scroll" aria-live="polite">
          {messages.map((message) => (
            <article key={message.id} className={`message-row ${message.role}`}>
              <div className={`message-avatar ${message.role}`}>
                {message.role === 'user' ? 'ME' : <span className="waymark-glyph">W</span>}
              </div>
              <div className="message-body">
                <div className="message-meta">
                  <strong>{message.role === 'user' ? 'You' : 'Waymark'}</strong>
                  <span>{message.timestamp}</span>
                  {message.role === 'assistant' && message.state !== 'thinking' && (
                    <span className={`grounded-label ${message.state ?? 'grounded'}`}>
                      <ShieldCheck size={12} />{' '}
                      {message.state === 'insufficient_evidence'
                        ? 'Needs evidence'
                        : message.state === 'error'
                          ? 'Check API'
                          : 'Grounded'}
                    </span>
                  )}
                </div>
                <div className="message-content">
                  <p>
                    {message.content}
                    {message.citations?.map((citation) => (
                      <CitationChip key={citation.id} evidence={citation} onClick={() => onCitation(citation)} />
                    ))}
                  </p>
                  {message.role === 'assistant' && (
                    <div className="answer-tools">
                      <button>
                        <Copy size={14} /> Copy
                      </button>
                      <button>
                        <Highlighter size={14} /> Annotate answer
                      </button>
                      <button>
                        <MoreHorizontal size={14} />
                      </button>
                    </div>
                  )}
                </div>
              </div>
            </article>
          ))}
          {asking && (
            <article className="message-row assistant">
              <div className="message-avatar assistant">
                <span className="waymark-glyph">W</span>
              </div>
              <div className="message-body">
                <div className="message-meta">
                  <strong>Waymark</strong>
                  <span>Now</span>
                </div>
                <div className="message-content thinking-line">
                  <LoaderCircle className="spin" size={14} /> Retrieving evidence before answering
                </div>
              </div>
            </article>
          )}
        </div>
        <div className="composer-wrap">
          <div className="suggestion-row">
            <span>Try asking</span>
            {['What changed since Q2?', 'Summarize retention rules', 'Find open obligations'].map((prompt) => (
              <button key={prompt} onClick={() => setQuestion(prompt)}>
                {prompt}
              </button>
            ))}
          </div>
          <form
            className={`composer ${dragging ? 'dragging' : ''} ${uploading ? 'uploading' : ''}`}
            onSubmit={(event) => {
              event.preventDefault();
              onAsk();
            }}
            onDragEnter={(event) => {
              event.preventDefault();
              setDragging(true);
            }}
            onDragOver={(event) => event.preventDefault()}
            onDragLeave={() => setDragging(false)}
            onDrop={(event) => {
              event.preventDefault();
              setDragging(false);
              void addDocuments(event.dataTransfer.files);
            }}
          >
            {pendingFiles.length > 0 && (
              <div className="composer-attachments" aria-live="polite">
                {pendingFiles.map((file) => (
                  <span className="composer-file-chip" key={`${file.name}-${file.size}`}>
                    <FileText size={12} aria-hidden="true" />
                    <span>{file.name}</span>
                    {uploading && <LoaderCircle className="spin" size={12} aria-hidden="true" />}
                  </span>
                ))}
              </div>
            )}
            <textarea
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              placeholder={dragging ? 'Drop documents to add them to your library' : 'Ask a question, or attach documents'}
              rows={1}
              aria-label="Ask your library"
              onKeyDown={(event) => {
                if (event.key === 'Enter' && !event.shiftKey) {
                  event.preventDefault();
                  onAsk();
                }
              }}
            />
            <div className="composer-footer">
              <div className="composer-context">
                <button
                  type="button"
                  className="composer-attach"
                  onClick={() => fileRef.current?.click()}
                  disabled={uploading || apiState === 'offline'}
                  aria-label="Add documents"
                  title="Add documents"
                >
                  {uploading ? <LoaderCircle className="spin" size={16} /> : <Paperclip size={16} />}
                  <span>Add docs</span>
                </button>
                <input
                  ref={fileRef}
                  className="visually-hidden"
                  type="file"
                  multiple
                  accept=".pdf,.doc,.docx,.txt,.md,.csv,.png,.jpg,.jpeg,.webp,.ts,.tsx,.js,.jsx,.py,.json"
                  onChange={(event) => {
                    void addDocuments(event.target.files);
                  }}
                />
                <span className="composer-status">
                  <span className="live-indicator" />
                  {scope}
                </span>
                <span className="composer-hint">Enter to send / Drop files to add</span>
              </div>
              <button className="send-button" type="submit" disabled={!question.trim() || asking} aria-label="Send question">
                {asking ? <LoaderCircle className="spin" size={17} /> : <Send size={17} />}
              </button>
            </div>
          </form>
          <div className="composer-note">
            <LockKeyhole size={12} />{' '}
            {apiState === 'ready'
              ? 'Local API active / attach docs here or ask from the indexed library'
              : 'Offline / start the local API to query uploaded documents'}
          </div>
        </div>
      </div>
      <div className="intelligence-footnote">
        <span>
          <Database size={13} /> {documentCount} documents indexed
        </span>
        <span>
          <Gauge size={13} /> {apiState === 'ready' ? 'Retrieval ready' : 'API offline'}
        </span>
        <button onClick={onOpenLibrary}>
          Manage library <ArrowUpRight size={13} />
        </button>
      </div>
    </section>
  );
}

function LibrarySurface({ documents, loading, apiState, onUpload, onInspectDocument, onOpenSettings }: { documents: DocumentRecord[]; loading: boolean; apiState: ApiState; onUpload: (files: FileList | File[]) => Promise<void>; onInspectDocument: (document: DocumentRecord) => void; onOpenSettings: () => void }) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [query, setQuery] = useState('');
  const [filter, setFilter] = useState<'All' | 'Ready' | 'Needs review'>('All');
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const filteredDocuments = useMemo(() => documents.filter((doc) => doc.name.toLowerCase().includes(query.toLowerCase()) && (filter === 'All' || (filter === 'Ready' ? doc.status === 'ready' : doc.status === 'review' || doc.status === 'failed'))), [documents, filter, query]);
  const readyCount = documents.filter((doc) => doc.status === 'ready').length;
  const reviewCount = documents.filter((doc) => doc.status === 'review' || doc.status === 'failed').length;
  const totalPages = documents.reduce((total, doc) => total + doc.pages, 0);
  const handleFiles = (files: FileList | null) => {
    if (!files?.length) return;
    setUploading(true);
    void onUpload(files).finally(() => setUploading(false));
  };
  return (
    <section className="surface-content library-surface">
      <div className="surface-header"><div><span className="surface-kicker">LIBRARY</span><h1>Your documents</h1><p>{documents.length} documents / {totalPages} indexed pages / {apiState === 'ready' ? 'stored locally' : 'local API offline'}</p></div><div className="header-actions"><button className="button button-secondary"><ListFilter size={15} /> Filter</button><button className="button button-primary" onClick={() => inputRef.current?.click()} disabled={uploading}><Upload size={15} /> Add documents</button><input ref={inputRef} className="visually-hidden" type="file" multiple onChange={(event) => handleFiles(event.target.files)} /></div></div>
      <div className={`dropzone ${dragging ? 'dragging' : ''} ${uploading ? 'uploading' : ''}`} onClick={() => inputRef.current?.click()} onDragEnter={(event) => { event.preventDefault(); setDragging(true); }} onDragOver={(event) => event.preventDefault()} onDragLeave={() => setDragging(false)} onDrop={(event) => { event.preventDefault(); setDragging(false); handleFiles(event.dataTransfer.files); }} role="button" tabIndex={0} onKeyDown={(event) => { if (event.key === 'Enter' || event.key === ' ') inputRef.current?.click(); }}><div className="dropzone-icon">{uploading ? <LoaderCircle className="spin" size={20} /> : <Upload size={20} />}</div><div><strong>{uploading ? 'Adding files to your library' : 'Drop files here or choose from your device'}</strong><span>PDF, DOCX, TXT, Markdown, CSV, images, and source code</span></div><span className="dropzone-action">{uploading ? 'Indexing starts next' : 'Browse files'}</span></div>
      <div className="library-toolbar"><div className="filter-tabs">{(['All', 'Ready', 'Needs review'] as const).map((item) => <button key={item} className={filter === item ? 'active' : ''} onClick={() => setFilter(item)}>{item}{item === 'All' && <span>{documents.length}</span>}{item === 'Ready' && <span>{readyCount}</span>}{item === 'Needs review' && <span className="needs-count">{reviewCount}</span>}</button>)}</div><label className="inline-search"><Search size={15} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Filter documents" /></label><button className="icon-button"><LayoutGrid size={16} /></button></div>
      {loading && <div className="inline-state"><LoaderCircle className="spin" size={15} /> Loading local documents</div>}
      <div className="document-list" role="table" aria-label="Document library"><div className="document-list-head" role="row"><span>Name</span><span>Type</span><span>Status</span><span>Updated</span><span aria-hidden="true" /></div>{filteredDocuments.map((doc) => { const Icon = formatFileIcon(doc.type); return <button className="document-row" key={doc.id} role="row" onClick={() => onInspectDocument(doc)}><span className="document-name"><span className="file-icon"><Icon size={17} /></span><span><strong>{doc.name}</strong><small>{doc.category} / {doc.size}</small></span></span><span className="doc-type mono">{doc.type}</span><span><StatusBadge status={doc.status} /></span><span className="document-updated">{doc.updated}</span><ChevronRight size={16} className="muted-icon" /></button>; })}</div>
      {filteredDocuments.length === 0 && <EmptyState icon={documents.length ? Search : Upload} title={documents.length ? 'No documents found' : 'Add your first document'} description={documents.length ? 'Try a different name or clear the current filter.' : 'Upload TXT, Markdown, CSV, or source files to create searchable evidence immediately. Binary files are stored and marked for review until parsers are connected.'} action={!documents.length ? <button className="button button-primary" onClick={() => inputRef.current?.click()}><Upload size={15} /> Add documents</button> : undefined} />}
      <div className="library-footer"><span>Showing {filteredDocuments.length} of {documents.length} documents</span><button onClick={onOpenSettings}>Manage indexing settings <ArrowUpRight size={13} /></button></div>
    </section>
  );
}

function ReviewSurface({ documents, onInspectDocument }: { documents: DocumentRecord[]; onInspectDocument: (document: DocumentRecord) => void }) {
  const reviewDocuments = documents.filter((document) => document.status === 'review' || document.status === 'failed');
  const readyDocuments = documents.filter((document) => document.status === 'ready');
  const progress = documents.length ? Math.round((readyDocuments.length / documents.length) * 100) : 0;
  return (
    <section className="surface-content review-surface">
      <div className="surface-header"><div><span className="surface-kicker">REVIEW</span><h1>Review workspace</h1><p>Documents that need parser, OCR, or human attention appear here.</p></div><div className="header-actions"><button className="button button-secondary"><History size={15} /> Version history</button><button className="button button-primary"><Split size={15} /> Compare files</button></div></div>
      <div className="review-grid">
        <div className="review-main">
          <div className="section-heading"><div><h2>Open review items</h2><p>{reviewDocuments.length ? `${reviewDocuments.length} documents need attention.` : 'No documents are waiting for review.'}</p></div></div>
          <div className="review-item-list">
            {reviewDocuments.map((document) => (
              <button className="review-item" key={document.id} onClick={() => onInspectDocument(document)}>
                <span className="review-item-icon amber"><Highlighter size={16} /></span>
                <span className="review-item-content"><strong>{document.name}</strong><span>{document.status === 'failed' ? 'Processing failed. Inspect the file and retry when parsers are configured.' : 'Stored locally, but no searchable evidence has been indexed yet.'}</span><small>{document.fidelity} / {document.updated}</small></span>
                <span className="review-tag">{document.status === 'failed' ? 'Failed' : 'Needs review'}</span>
                <ChevronRight size={15} className="muted-icon" />
              </button>
            ))}
          </div>
          {!reviewDocuments.length && <EmptyState icon={Highlighter} title="Nothing needs review" description={documents.length ? 'Ready documents can be searched and cited from Intelligence.' : 'Add documents to begin building the review queue.'} />}
          <div className="section-heading compare-heading"><div><h2>Recent comparisons</h2><p>Comparisons will appear after two document versions are selected.</p></div></div>
          <div className="comparison-table empty-comparison"><EmptyState icon={Split} title="No comparisons yet" description="Version comparison is ready in the interface, but no comparison records exist yet." /></div>
        </div>
        <aside className="review-summary">
          <div className="summary-heading"><span className="pane-kicker">LOCAL INDEX</span><MoreHorizontal size={16} className="muted-icon" /></div>
          <div className="review-stat"><strong>{documents.length}</strong><span>documents in this workspace</span></div>
          <div className="review-progress"><div><span>Ready for retrieval</span><strong>{progress}%</strong></div><div className="progress-track"><span style={{ width: `${progress}%` }} /></div></div>
          <div className="review-rule" />
          <div className="review-summary-row"><Check size={15} /><span>{readyDocuments.length} ready documents</span></div>
          <div className="review-summary-row"><MessageSquareText size={15} /><span>{reviewDocuments.length} review items</span></div>
          <div className="review-summary-row"><ArrowDownToLine size={15} /><span>0 exports generated</span></div>
          <button className="button button-secondary full-width"><ArrowDownToLine size={15} /> Open export history</button>
        </aside>
      </div>
    </section>
  );
}

function SettingsSurface({
  onTheme,
  theme,
  comfortable,
  onComfortable,
  providers,
  providersLoading,
  onConfigureOllama,
  onConfigureOpenAI,
  onTestProvider,
  testingProviderId,
}: {
  onTheme: (theme: 'dark' | 'light') => void;
  theme: 'dark' | 'light';
  comfortable: boolean;
  onComfortable: (value: boolean) => void;
  providers: import('@/lib/api/client').ProviderConfigRecord[];
  providersLoading: boolean;
  onConfigureOllama: () => void;
  onConfigureOpenAI: () => void;
  onTestProvider: (id: string) => void;
  testingProviderId: string | null;
}) {
  const chatProviders = providers.filter((provider) => provider.role === 'chat');
  const embedProviders = providers.filter((provider) => provider.role === 'embedding');
  const renderProvider = (provider: import('@/lib/api/client').ProviderConfigRecord) => {
    const mark = provider.providerType === 'ollama' ? 'O' : provider.providerType === 'extractive' ? 'D' : provider.providerType === 'keyword' ? 'K' : 'O';
    return (
      <div className={`provider-row ${provider.connected || provider.isDefault ? 'active-provider' : ''}`} key={provider.id}>
        <div className={`provider-logo ${provider.local ? 'local' : 'openai'}`}><span>{mark}</span></div>
        <div className="provider-copy">
          <div>
            <strong>{provider.providerType === 'extractive' ? 'DuckDocs Extractive' : provider.providerType === 'keyword' ? 'Keyword index' : provider.providerType === 'ollama' ? 'Ollama' : provider.providerType === 'openai_compatible' ? 'OpenAI-compatible' : provider.providerType}</strong>
            {provider.isDefault && <span className="provider-badge">Default</span>}
          </div>
          <p>{provider.modelName || 'No model set'}{provider.baseUrl ? ` / ${provider.baseUrl}` : provider.local ? ' / local' : ' / API key stays local'}</p>
        </div>
        <span className={`provider-status ${provider.connected ? '' : 'muted'}`}>
          <span className={provider.connected ? 'live-indicator' : 'empty-indicator'} />
          {provider.connected ? 'Connected' : 'Not connected'}
        </span>
        <button className="button button-secondary small-button" onClick={() => onTestProvider(provider.id)} disabled={testingProviderId === provider.id}>
          {testingProviderId === provider.id ? 'Testing…' : 'Test'}
        </button>
      </div>
    );
  };
  return (
    <section className="surface-content settings-surface">
      <div className="surface-header">
        <div>
          <span className="surface-kicker">SETTINGS</span>
          <h1>Workspace settings</h1>
          <p>Make privacy, provider, and review behavior explicit.</p>
        </div>
        <button className="button button-secondary"><CircleHelp size={15} /> Help center</button>
      </div>
      <div className="settings-layout">
        <nav className="settings-nav">
          <button className="active"><Sparkles size={16} /> Providers</button>
          <button><FolderOpen size={16} /> Local paths</button>
          <button><ShieldCheck size={16} /> Privacy</button>
          <button><SlidersHorizontal size={16} /> Processing</button>
          <button><Keyboard size={16} /> Shortcuts</button>
        </nav>
        <div className="settings-sections">
          <section className="settings-section">
            <div className="settings-section-heading">
              <div>
                <h2>AI providers</h2>
                <p>DuckDocs answers from indexed local evidence. Cloud and model providers stay opt-in.</p>
              </div>
              <div className="header-actions">
                <button className="button button-secondary" onClick={onConfigureOllama}><Plus size={15} /> Configure Ollama</button>
                <button className="button button-secondary" onClick={onConfigureOpenAI}><Plus size={15} /> Add OpenAI-compatible</button>
              </div>
            </div>
            {providersLoading && <div className="inline-state"><LoaderCircle className="spin" size={15} /> Loading provider status</div>}
            {!providersLoading && !providers.length && (
              <EmptyState icon={Sparkles} title="No providers configured" description="Configure Ollama for local generation, or keep the built-in extractive fallback." />
            )}
            {chatProviders.map(renderProvider)}
            {embedProviders.map(renderProvider)}
          </section>
          <section className="settings-section split-settings">
            <div>
              <div className="settings-section-heading compact"><div><h2>Appearance</h2><p>Dark is the default for long review sessions.</p></div></div>
              <div className="theme-toggle">
                <button className={theme === 'dark' ? 'active' : ''} onClick={() => onTheme('dark')}><Moon size={16} /> Dark</button>
                <button className={theme === 'light' ? 'active' : ''} onClick={() => onTheme('light')}><Sun size={16} /> Light</button>
              </div>
            </div>
            <div>
              <div className="settings-section-heading compact"><div><h2>Density</h2><p>Comfortable mode increases row height and panel breathing room.</p></div></div>
              <button className={`density-toggle ${comfortable ? 'active' : ''}`} onClick={() => onComfortable(!comfortable)}>
                <span className="toggle-track"><span /></span>
                <span><strong>{comfortable ? 'Comfortable' : 'Dense'}</strong><small>{comfortable ? '40px row height' : '32px row height'}</small></span>
              </button>
            </div>
          </section>
          <section className="privacy-callout">
            <div className="privacy-icon"><LockKeyhole size={19} /></div>
            <div>
              <h2>Your data boundary</h2>
              <p>DuckDocs uses local file storage, a local evidence index, and optional local Ollama/Chroma adapters. Cloud providers only run when you configure them.</p>
              <button className="text-button">View network activity <ArrowUpRight size={13} /></button>
            </div>
            <ShieldCheck size={20} className="privacy-check" />
          </section>
        </div>
      </div>
    </section>
  );
}

function Toast({ message, onClose }: { message: string | null; onClose: () => void }) {
  useEffect(() => { if (!message) return; const timer = window.setTimeout(onClose, 2800); return () => window.clearTimeout(timer); }, [message, onClose]);
  if (!message) return null;
  return <div className="toast" role="status"><Check size={15} /><span>{message}</span><button onClick={onClose} aria-label="Dismiss notification"><X size={14} /></button></div>;
}

export default function DuckDocsApp({ initialSurface }: DuckDocsAppProps) {
  const router = useRouter();
  const pathname = usePathname();
  const [activeSurface, setActiveSurface] = useState<Surface>(initialSurface);
  const [navOpen, setNavOpen] = useState(false);
  const [commandOpen, setCommandOpen] = useState(false);
  const [evidence, setEvidence] = useState<EvidenceRecord | null>(null);
  const [documents, setDocuments] = useState<DocumentRecord[]>([]);
  const [documentsLoading, setDocumentsLoading] = useState(true);
  const [apiState, setApiState] = useState<ApiState>('connecting');
  const [asking, setAsking] = useState(false);
  const [question, setQuestion] = useState('');
  const [messages, setMessages] = useState<MessageRecord[]>([
    { id: 'message_welcome', role: 'assistant', timestamp: currentTimestamp(), content: 'DuckDocs is ready. Add documents to build a local evidence index, then ask a question and I will cite only retrieved passages.' },
  ]);
  const [toast, setToast] = useState<string | null>(null);
  const [theme, setTheme] = useState<'dark' | 'light'>('dark');
  const [comfortable, setComfortable] = useState(false);
  const [providers, setProviders] = useState<import('@/lib/api/client').ProviderConfigRecord[]>([]);
  const [providersLoading, setProvidersLoading] = useState(false);
  const [testingProviderId, setTestingProviderId] = useState<string | null>(null);

  useEffect(() => {
    if (pathname?.includes('/library')) setActiveSurface('library');
    else if (pathname?.includes('/review')) setActiveSurface('review');
    else if (pathname?.includes('/settings')) setActiveSurface('settings');
    else if (pathname?.includes('/intelligence') || pathname === '/') setActiveSurface('intelligence');
  }, [pathname]);

  const refreshDocuments = useCallback(async () => {
    try {
      const response = await duckDocsApi.listDocuments();
      setDocuments(response.items);
      setApiState('ready');
    } catch {
      setDocuments([]);
      setApiState('offline');
    } finally {
      setDocumentsLoading(false);
    }
  }, []);

  const refreshProviders = useCallback(async () => {
    setProvidersLoading(true);
    try {
      const response = await duckDocsApi.listProviderConfigs();
      setProviders(response);
      setApiState('ready');
    } catch {
      setProviders([]);
    } finally {
      setProvidersLoading(false);
    }
  }, []);

  useEffect(() => {
    void refreshDocuments();
  }, [refreshDocuments]);

  useEffect(() => {
    if (activeSurface === 'settings' && apiState !== 'offline') {
      void refreshProviders();
    }
  }, [activeSurface, apiState, refreshProviders]);

  useEffect(() => {
    const handler = (event: KeyboardEvent) => { if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') { event.preventDefault(); setCommandOpen(true); } };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, []);

  const navigate = (surface: Surface) => {
    setActiveSurface(surface);
    setNavOpen(false);
    router.push(`/${surface}`);
  };

  const selectEvidence = (nextEvidence: EvidenceRecord) => {
    setEvidence(nextEvidence);
    setToast(`Opened ${nextEvidence.documentName}, page ${nextEvidence.page}`);
  };

  const uploadDocuments = async (files: FileList | File[]) => {
    if (apiState === 'offline') {
      setToast('Start the DuckDocs API to add documents.');
      return;
    }
    try {
      const uploaded = await duckDocsApi.uploadDocuments(files);
      setDocuments((current) => [...uploaded, ...current.filter((doc) => !uploaded.some((item) => item.id === doc.id))]);
      setToast(`${uploaded.length} document${uploaded.length === 1 ? '' : 's'} added. Indexing is running locally.`);
      window.setTimeout(() => {
        void refreshDocuments();
      }, 1200);
    } catch (error) {
      setToast(describeApiIssue(error));
      if (apiState === 'connecting') setApiState('offline');
    }
  };

  const inspectDocument = async (document: DocumentRecord) => {
    if (apiState !== 'ready') {
      setToast('Start the DuckDocs API to inspect indexed evidence.');
      return;
    }
    try {
      const response = await duckDocsApi.search(document.name);
      const firstEvidence = response.results[0]?.evidence;
      if (firstEvidence) {
        selectEvidence(firstEvidence);
      } else {
        setEvidence(null);
        setToast(`${document.name} has no indexed evidence yet.`);
      }
    } catch (error) {
      setToast(describeApiIssue(error));
    }
  };

  const askQuestion = () => {
    const nextQuestion = question.trim();
    if (!nextQuestion) return;
    setQuestion('');
    setMessages((current) => [...current, { id: `user_${Date.now()}`, role: 'user', timestamp: currentTimestamp(), content: nextQuestion }]);
    setAsking(true);
    void (async () => {
      try {
        if (apiState !== 'ready') {
          await refreshDocuments();
        }
        const answer = await duckDocsApi.ask(nextQuestion);
        setApiState('ready');
        const content =
          answer.answer ??
          'I do not have enough retrieved evidence to answer that confidently. Try narrowing the scope or adding a source document.';
        setMessages((current) => [
          ...current,
          {
            id: `assistant_${Date.now()}`,
            role: 'assistant',
            timestamp: currentTimestamp(),
            content,
            citations: answer.citations,
            state: answer.outcome === 'grounded' ? 'grounded' : 'insufficient_evidence',
          },
        ]);
        if (answer.citations[0]) setEvidence(answer.citations[0]);
      } catch (error) {
        const message = describeApiIssue(error);
        setMessages((current) => [
          ...current,
          {
            id: `assistant_${Date.now()}`,
            role: 'assistant',
            timestamp: currentTimestamp(),
            content: message,
            state: 'error',
          },
        ]);
        setToast(message);
        if (error instanceof ApiError && (error.code === 'NETWORK_ERROR' || error.status === 0 || error.status === 502)) {
          setApiState('offline');
        }
      } finally {
        setAsking(false);
      }
    })();
  };

  const applyTheme = (nextTheme: 'dark' | 'light') => {
    setTheme(nextTheme);
    document.documentElement.dataset.theme = nextTheme;
  };

  const configureOllama = async () => {
    if (apiState === 'offline') {
      setToast('Start the DuckDocs API to configure providers.');
      return;
    }
    try {
      await duckDocsApi.createProviderConfig({
        role: 'chat',
        providerType: 'ollama',
        modelName: 'llama3.2:1b',
        baseUrl: 'http://ollama:11434',
        isDefault: true,
      });
      await duckDocsApi.createProviderConfig({
        role: 'embedding',
        providerType: 'ollama',
        modelName: 'nomic-embed-text',
        baseUrl: 'http://ollama:11434',
        isDefault: true,
      });
      await refreshProviders();
      setToast('Ollama chat and embedding providers configured as defaults.');
    } catch (error) {
      setToast(describeApiIssue(error));
    }
  };

  const configureOpenAI = async () => {
    if (apiState === 'offline') {
      setToast('Start the DuckDocs API to configure providers.');
      return;
    }
    const apiKey = window.prompt('Enter an OpenAI-compatible API key (stored locally, never logged):');
    if (!apiKey) return;
    const baseUrl = window.prompt('Base URL (optional, leave blank for OpenAI default):') || null;
    const modelName = window.prompt('Model name', 'gpt-4.1-mini') || 'gpt-4.1-mini';
    try {
      await duckDocsApi.createProviderConfig({
        role: 'chat',
        providerType: baseUrl ? 'openai_compatible' : 'openai',
        modelName,
        baseUrl,
        apiKey,
        isDefault: false,
      });
      await refreshProviders();
      setToast('OpenAI-compatible provider saved locally.');
    } catch (error) {
      setToast(describeApiIssue(error));
    }
  };

  const testProvider = async (id: string) => {
    setTestingProviderId(id);
    try {
      const result = await duckDocsApi.testProviderConfig(id);
      setToast(result.reachable ? `Provider reachable${result.latency_ms != null ? ` in ${Math.round(result.latency_ms)} ms` : ''}.` : `Provider unreachable${result.error ? `: ${result.error}` : '.'}`);
      await refreshProviders();
    } catch (error) {
      setToast(describeApiIssue(error));
    } finally {
      setTestingProviderId(null);
    }
  };

  return (
    <div className={`duckdocs-app ${navOpen ? 'nav-is-open' : ''}`}>
      <NavRail activeSurface={activeSurface} documentCount={documents.length} onNavigate={navigate} onCommand={() => setCommandOpen(true)} />
      <div className="app-stage">
        <TopBar surface={activeSurface} apiState={apiState} onCommand={() => setCommandOpen(true)} onToggleNav={() => setNavOpen(!navOpen)} onOpenEvidence={() => setEvidence(evidence)} hasEvidence={Boolean(evidence)} />
        <main className="app-main" data-density={comfortable ? 'comfortable' : 'dense'}>
          {activeSurface === 'intelligence' && (
            <IntelligenceSurface
              messages={messages}
              question={question}
              setQuestion={setQuestion}
              onAsk={askQuestion}
              onCitation={selectEvidence}
              onOpenLibrary={() => navigate('library')}
              onUpload={uploadDocuments}
              documentCount={documents.length}
              apiState={apiState}
              asking={asking}
            />
          )}
          {activeSurface === 'library' && <LibrarySurface documents={documents} loading={documentsLoading} apiState={apiState} onUpload={uploadDocuments} onInspectDocument={inspectDocument} onOpenSettings={() => navigate('settings')} />}
          {activeSurface === 'review' && <ReviewSurface documents={documents} onInspectDocument={inspectDocument} />}
          {activeSurface === 'settings' && (
            <SettingsSurface
              onTheme={applyTheme}
              theme={theme}
              comfortable={comfortable}
              onComfortable={(next) => {
                setComfortable(next);
                document.documentElement.dataset.density = next ? 'comfortable' : 'dense';
              }}
              providers={providers}
              providersLoading={providersLoading}
              onConfigureOllama={() => { void configureOllama(); }}
              onConfigureOpenAI={() => { void configureOpenAI(); }}
              onTestProvider={(id) => { void testProvider(id); }}
              testingProviderId={testingProviderId}
            />
          )}
          {activeSurface !== 'settings' && <EvidencePane evidence={evidence} onClose={() => setEvidence(null)} onAnnotate={() => setToast('Annotation composer is ready for this passage')} />}
        </main>
      </div>
      <CommandPalette open={commandOpen} onClose={() => setCommandOpen(false)} onNavigate={navigate} />
      <Toast message={toast} onClose={() => setToast(null)} />
    </div>
  );
}
