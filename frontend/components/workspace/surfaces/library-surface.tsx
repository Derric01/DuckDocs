'use client';

import {
  AlertCircle,
  Check,
  ChevronRight,
  FileCode2,
  FileImage,
  FileSpreadsheet,
  FileText,
  LoaderCircle,
  Search,
  Sparkles,
  Upload,
  type LucideIcon,
} from 'lucide-react';
import { useMemo, useRef, useState } from 'react';
import { Badge, EmptyState, Progress, Skeleton } from '@/components/ui';
import { useWorkspace } from '@/components/workspace/workspace-provider';
import type { DocumentRecord, DocumentStatus } from '@/lib/types';

const ACCEPT =
  '.pdf,.docx,.xlsx,.pptx,.txt,.md,.csv,.html,.htm,.json,.xml,.yaml,.yml,.png,.jpg,.jpeg,.webp,.tiff,.tif,.bmp,.ts,.tsx,.js,.jsx,.py,.java,.c,.cpp,.cs,.go,.rs,.sql,.css,.sh,.rb,.php,.kt,.swift';

type Filter = 'all' | 'ready' | 'attention';

const STATUS: Record<DocumentStatus, { label: string; tone: 'success' | 'warning' | 'danger' | 'neutral'; icon: LucideIcon; spin?: boolean }> = {
  ready: { label: 'Ready', tone: 'success', icon: Check },
  processing: { label: 'Processing', tone: 'neutral', icon: LoaderCircle, spin: true },
  review: { label: 'Needs review', tone: 'warning', icon: AlertCircle },
  failed: { label: 'Failed', tone: 'danger', icon: AlertCircle },
};

/** Raw pipeline stage names are internal; the row shows what is happening. */
const STAGE_LABEL: Record<string, string> = {
  queued: 'Queued',
  parsing: 'Reading pages',
  ocr: 'Recognizing text',
  chunking: 'Splitting passages',
  summarizing: 'Summarizing',
  embedding: 'Building index',
  indexing: 'Indexing',
};

function iconFor(type: string): LucideIcon {
  const upper = type.toUpperCase();
  if (['CSV', 'XLSX'].includes(upper)) return FileSpreadsheet;
  if (['PNG', 'JPG', 'JPEG', 'WEBP', 'TIFF', 'TIF', 'BMP'].includes(upper)) return FileImage;
  if (['TS', 'TSX', 'JS', 'JSX', 'PY', 'JSON', 'XML', 'YAML', 'YML', 'SQL', 'GO', 'RS'].includes(upper)) {
    return FileCode2;
  }
  return FileText;
}

export function LibrarySurface() {
  const { documents, documentsLoading, uploadDocuments, inspectDocument, connection } = useWorkspace();
  const inputRef = useRef<HTMLInputElement>(null);
  const [query, setQuery] = useState('');
  const [filter, setFilter] = useState<Filter>('all');
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);

  const counts = useMemo(
    () => ({
      all: documents.length,
      ready: documents.filter((document) => document.status === 'ready').length,
      attention: documents.filter((document) => document.status === 'review' || document.status === 'failed').length,
    }),
    [documents],
  );

  const visible = useMemo(() => {
    const term = query.trim().toLowerCase();
    return documents.filter((document) => {
      if (term && !document.name.toLowerCase().includes(term)) return false;
      if (filter === 'ready') return document.status === 'ready';
      if (filter === 'attention') return document.status === 'review' || document.status === 'failed';
      return true;
    });
  }, [documents, filter, query]);

  const addFiles = async (files: FileList | File[] | null) => {
    if (!files || Array.from(files).length === 0) return;
    setUploading(true);
    try {
      await uploadDocuments(files);
    } finally {
      setUploading(false);
      if (inputRef.current) inputRef.current.value = '';
    }
  };

  const totalPages = documents.reduce((total, document) => total + document.pages, 0);

  return (
    <div className="surface surface-narrow">
      <header className="surface-head">
        <div className="surface-head-row">
          <div>
            <h2>Library</h2>
            <p>
              {documents.length} document{documents.length === 1 ? '' : 's'} · {totalPages} indexed page
              {totalPages === 1 ? '' : 's'} · stored on this machine
            </p>
          </div>
          <div className="head-actions">
            <button
              className="btn btn-primary"
              onClick={() => inputRef.current?.click()}
              disabled={uploading || connection === 'offline'}
            >
              <Upload size={15} strokeWidth={1.8} aria-hidden="true" />
              Add documents
            </button>
          </div>
        </div>
      </header>

      <button
        type="button"
        className={`dropzone ${dragging ? 'dragging' : ''}`}
        onClick={() => inputRef.current?.click()}
        onDragEnter={(event) => {
          event.preventDefault();
          setDragging(true);
        }}
        onDragOver={(event) => event.preventDefault()}
        onDragLeave={(event) => {
          if (event.currentTarget.contains(event.relatedTarget as Node)) return;
          setDragging(false);
        }}
        onDrop={(event) => {
          event.preventDefault();
          setDragging(false);
          void addFiles(event.dataTransfer.files);
        }}
      >
        <span className="dropzone-icon" aria-hidden="true">
          {uploading ? <LoaderCircle size={17} className="spin" /> : <Upload size={17} strokeWidth={1.7} />}
        </span>
        <span className="dropzone-copy">
          <strong>{uploading ? 'Adding to your library…' : 'Drop files here, or browse'}</strong>
          <span>PDF, Office, images, and text. Scans are recognized with local OCR.</span>
        </span>
      </button>
      <input
        ref={inputRef}
        type="file"
        multiple
        accept={ACCEPT}
        className="visually-hidden"
        onChange={(event) => void addFiles(event.target.files)}
      />

      <div className="toolbar">
        <div className="tabs" role="tablist" aria-label="Filter documents">
          {(
            [
              ['all', 'All'],
              ['ready', 'Ready'],
              ['attention', 'Needs attention'],
            ] as Array<[Filter, string]>
          ).map(([value, label]) => (
            <button
              key={value}
              className="tab"
              role="tab"
              aria-selected={filter === value}
              onClick={() => setFilter(value)}
            >
              {label}
              <span className="tab-count">{counts[value]}</span>
            </button>
          ))}
        </div>
        <label className="search">
          <Search size={14} strokeWidth={1.8} aria-hidden="true" />
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Filter by name"
            aria-label="Filter documents by name"
          />
        </label>
      </div>

      {documentsLoading ? (
        <div className="doc-table">
          {[0, 1, 2].map((row) => (
            <div className="doc-row" key={row}>
              <Skeleton height={16} />
              <Skeleton height={16} />
              <Skeleton height={16} />
              <Skeleton height={16} />
              <span />
            </div>
          ))}
        </div>
      ) : visible.length === 0 ? (
        <EmptyState
          icon={documents.length ? Search : Upload}
          title={documents.length ? 'No matching documents' : 'No documents yet'}
          description={
            documents.length
              ? 'Try a different name, or clear the current filter.'
              : 'Add PDFs, Office files, images, or text. Scanned pages are recognized locally with OCR.'
          }
          action={
            documents.length ? undefined : (
              <button className="btn btn-primary" onClick={() => inputRef.current?.click()}>
                <Upload size={15} strokeWidth={1.8} aria-hidden="true" />
                Add documents
              </button>
            )
          }
        />
      ) : (
        <div className="doc-table" role="table" aria-label="Documents">
          <div className="doc-head" role="row">
            <span role="columnheader">Name</span>
            <span role="columnheader">Fidelity</span>
            <span role="columnheader">Status</span>
            <span role="columnheader">Updated</span>
            <span aria-hidden="true" />
          </div>
          {visible.map((document) => (
            <DocumentRow key={document.id} document={document} onOpen={() => void inspectDocument(document)} />
          ))}
        </div>
      )}
    </div>
  );
}

function DocumentRow({ document, onOpen }: { document: DocumentRecord; onOpen: () => void }) {
  const Icon = iconFor(document.type);
  const status = STATUS[document.status];
  const StatusIcon = status.icon;
  const processing = document.status === 'processing';
  const [expanded, setExpanded] = useState(false);

  const hasSummary = Boolean(document.summary);

  return (
    <div className="doc-entry">
      <div className="doc-row" role="row">
        <button
          className="doc-name doc-name-button"
          role="cell"
          onClick={() => (hasSummary ? setExpanded((value) => !value) : onOpen())}
          aria-expanded={hasSummary ? expanded : undefined}
        >
          <span className="doc-icon" aria-hidden="true">
            <Icon size={15} strokeWidth={1.7} />
          </span>
          <span className="doc-name-copy">
            <strong>{document.name}</strong>
            <small>
              {document.type} · {document.size} · {document.pages} page{document.pages === 1 ? '' : 's'}
            </small>
          </span>
        </button>

        <span className="doc-fidelity" role="cell">
          <Badge tone={document.fidelity === 'OCR dependent' ? 'accent' : 'neutral'}>{document.fidelity}</Badge>
        </span>

        <span className="doc-status" role="cell">
          {processing && typeof document.progress === 'number' ? (
            <span className="doc-progress">
              <Progress value={document.progress} label={`Ingest progress for ${document.name}`} />
              <span className="mono">{document.progress}%</span>
            </span>
          ) : (
            <Badge tone={status.tone} icon={StatusIcon} spinning={status.spin}>
              {status.label}
            </Badge>
          )}
        </span>

        <span className="doc-updated" role="cell">
          {processing && document.stage ? STAGE_LABEL[document.stage] ?? document.stage : document.updated}
        </span>

        <button className="doc-open" onClick={onOpen} aria-label={`Open evidence for ${document.name}`}>
          <ChevronRight size={15} strokeWidth={1.8} className="doc-chevron" aria-hidden="true" />
        </button>
      </div>

      {hasSummary && expanded ? (
        <div className="doc-summary">
          <div className="doc-summary-head">
            <Sparkles size={13} strokeWidth={1.8} aria-hidden="true" />
            <span className="kicker">Summary</span>
            {/* An extractive summary is verbatim document text; an abstractive
                one is model output. The distinction changes how much a reader
                should trust the wording, so it is always labeled. */}
            <Badge tone={document.summaryMethod === 'abstractive' ? 'warning' : 'neutral'}>
              {document.summaryMethod === 'abstractive' ? 'Model written' : 'From the document'}
            </Badge>
            {document.summaryProvider ? <span className="mono">{document.summaryProvider}</span> : null}
          </div>
          <p>{document.summary}</p>
        </div>
      ) : null}
    </div>
  );
}
