'use client';

import {
  AlertCircle,
  Check,
  ChevronDown,
  ChevronRight,
  FileCode2,
  FileImage,
  FileSpreadsheet,
  FileText,
  FileType2,
  LoaderCircle,
  Search,
  Upload,
  type LucideIcon,
} from 'lucide-react';
import { useMemo, useRef, useState } from 'react';
import {
  Badge,
  Button,
  EmptyState,
  Input,
  Progress,
  Skeleton,
  Tabs,
  TabsList,
  TabsTrigger,
} from '@/components/ui';
import { useWorkspace } from '@/components/workspace/workspace-provider';
import { cn } from '@/lib/utils';
import type { DocumentRecord, DocumentStatus } from '@/lib/types';

const ACCEPT =
  '.pdf,.docx,.xlsx,.pptx,.txt,.md,.csv,.html,.htm,.json,.xml,.yaml,.yml,.png,.jpg,.jpeg,.webp,.tiff,.tif,.bmp,.ts,.tsx,.js,.jsx,.py,.java,.c,.cpp,.cs,.go,.rs,.sql,.css,.sh,.rb,.php,.kt,.swift';

type Filter = 'all' | 'ready' | 'attention';

const STATUS: Record<
  DocumentStatus,
  { label: string; tone: 'success' | 'warning' | 'destructive' | 'neutral'; icon: LucideIcon; spin?: boolean }
> = {
  ready: { label: 'Ready', tone: 'success', icon: Check },
  processing: { label: 'Processing', tone: 'neutral', icon: LoaderCircle, spin: true },
  review: { label: 'Needs review', tone: 'warning', icon: AlertCircle },
  failed: { label: 'Failed', tone: 'destructive', icon: AlertCircle },
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

/**
 * Colour is an index, not decoration: a hue always means the same kind of
 * file, so a long library becomes scannable without reading extensions. The
 * glyph is tinted rather than reversed out of a saturated tile — twenty
 * saturated tiles in a column is a colour chart, not a document list.
 */
function kindFor(type: string): { icon: LucideIcon; mark: string } {
  const upper = type.toUpperCase();
  if (upper === 'PDF') return { icon: FileType2, mark: 'border-kind-slide/25 bg-kind-slide/10 text-kind-slide' };
  if (['CSV', 'XLSX'].includes(upper)) {
    return { icon: FileSpreadsheet, mark: 'border-kind-sheet/25 bg-kind-sheet/10 text-kind-sheet' };
  }
  if (['PNG', 'JPG', 'JPEG', 'WEBP', 'TIFF', 'TIF', 'BMP'].includes(upper)) {
    return { icon: FileImage, mark: 'border-kind-image/25 bg-kind-image/10 text-kind-image' };
  }
  if (['TS', 'TSX', 'JS', 'JSX', 'PY', 'JSON', 'XML', 'YAML', 'YML', 'SQL', 'GO', 'RS'].includes(upper)) {
    return { icon: FileCode2, mark: 'border-kind-code/25 bg-kind-code/10 text-kind-code' };
  }
  if (['DOCX', 'PPTX'].includes(upper)) {
    return { icon: FileText, mark: 'border-kind-doc/25 bg-kind-doc/10 text-kind-doc' };
  }
  return { icon: FileText, mark: 'border-border bg-muted text-kind-text' };
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
      attention: documents.filter((d) => d.status === 'review' || d.status === 'failed').length,
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
    <div className="mx-auto max-w-5xl px-8 pb-16 pt-8 max-sm:px-4 max-sm:pt-5">
      <header className="mb-7 flex flex-wrap items-end justify-between gap-4 border-b border-border pb-5">
        <div>
          <h2 className="font-display text-3xl text-foreground">Library</h2>
          <p className="mt-1.5 text-sm text-muted-foreground">
            {documents.length} document{documents.length === 1 ? '' : 's'} · {totalPages} indexed page
            {totalPages === 1 ? '' : 's'} · stored on this machine
          </p>
        </div>
        <Button
          variant="primary"
          onClick={() => inputRef.current?.click()}
          disabled={uploading || connection === 'offline'}
        >
          <Upload className="size-3.5" aria-hidden />
          Add documents
        </Button>
      </header>

      <button
        type="button"
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
        className={cn(
          'flex w-full items-center gap-3 rounded-lg border border-dashed px-4 py-3.5 text-left',
          'transition-colors duration-fast',
          dragging ? 'border-accent bg-accent-muted' : 'border-border-strong hover:border-foreground/30 hover:bg-card',
        )}
      >
        {uploading ? (
          <LoaderCircle className="size-4 shrink-0 animate-spin text-muted-foreground" aria-hidden />
        ) : (
          <Upload className="size-4 shrink-0 text-muted-foreground" strokeWidth={1.6} aria-hidden />
        )}
        <span className="min-w-0 flex-1">
          <span className="block text-sm font-medium text-foreground">
            {uploading ? 'Adding to your library…' : 'Drop files here, or browse'}
          </span>
          <span className="block text-xs text-muted-foreground">
            PDF, Office, images, and text. Scans are recognized with local OCR.
          </span>
        </span>
      </button>
      <input
        ref={inputRef}
        type="file"
        multiple
        accept={ACCEPT}
        className="sr-only"
        onChange={(event) => void addFiles(event.target.files)}
      />

      <div className="mb-4 mt-7 flex flex-wrap items-end justify-between gap-3">
        <Tabs value={filter} onValueChange={(value) => setFilter(value as Filter)}>
          <TabsList>
            {(
              [
                ['all', 'All'],
                ['ready', 'Ready'],
                ['attention', 'Needs attention'],
              ] as Array<[Filter, string]>
            ).map(([value, label]) => (
              <TabsTrigger key={value} value={value}>
                {label}
                <span className="font-mono text-[10px] tabular-nums opacity-60">{counts[value]}</span>
              </TabsTrigger>
            ))}
          </TabsList>
        </Tabs>

        <div className="relative w-full sm:w-52">
          <Search
            className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground"
            aria-hidden
          />
          <Input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Filter by name"
            aria-label="Filter documents by name"
            className="h-8 pl-8 text-sm"
          />
        </div>
      </div>

      {documentsLoading ? (
        <div className="overflow-hidden rounded-lg border border-border">
          {[0, 1, 2].map((row) => (
            <Skeleton key={row} className="h-12 rounded-none" />
          ))}
        </div>
      ) : visible.length === 0 ? (
        <EmptyState
          icon={documents.length ? Search : Upload}
          title={documents.length ? 'No matching documents' : 'Nothing here yet'}
          description={
            documents.length
              ? 'Try a different name, or clear the current filter.'
              : 'Add PDFs, Office files, images, or text. Scanned pages are recognized locally with OCR — no page limits.'
          }
          action={
            documents.length ? undefined : (
              <Button variant="primary" size="lg" onClick={() => inputRef.current?.click()}>
                <Upload className="size-4" aria-hidden />
                Add documents
              </Button>
            )
          }
        />
      ) : (
        /**
         * A real table rather than a list of cards. Column alignment is what
         * makes twenty documents comparable at a glance — the whole reason a
         * library view exists.
         */
        <div className="overflow-hidden rounded-lg border border-border bg-card">
          <div
            role="row"
            className="table-head flex items-center gap-3 px-3 py-2"
            aria-hidden
          >
            <span className="min-w-0 flex-1">Document</span>
            <span className="hidden w-[104px] shrink-0 md:block">Fidelity</span>
            <span className="w-[112px] shrink-0 max-sm:w-auto">Status</span>
            <span className="hidden w-[92px] shrink-0 lg:block">Updated</span>
            <span className="w-7 shrink-0" />
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
  const { icon: Icon, mark } = kindFor(document.type);
  const status = STATUS[document.status];
  const StatusIcon = status.icon;
  const processing = document.status === 'processing';
  const [expanded, setExpanded] = useState(false);
  const hasSummary = Boolean(document.summary);

  return (
    <div className="table-row-hairline border-t border-border">
      <div className="flex min-h-[48px] items-center gap-3 px-3 transition-colors duration-fast hover:bg-muted/40">
        <button
          onClick={() => (hasSummary ? setExpanded((value) => !value) : onOpen())}
          aria-expanded={hasSummary ? expanded : undefined}
          className="flex min-w-0 flex-1 items-center gap-2.5 py-2 text-left"
        >
          <span className={cn('kind-mark', mark)}>
            <Icon className="size-4" strokeWidth={1.7} aria-hidden />
          </span>
          <span className="min-w-0">
            <span className="block truncate text-sm font-medium text-foreground">{document.name}</span>
            <span className="flex min-w-0 items-center gap-1.5 text-2xs text-muted-foreground">
              <span className="truncate font-mono">
                {document.type} · {document.size} · {document.pages}p
              </span>
              {/* Without this the summary is invisible: nothing else on the row
                  says the name is a disclosure rather than a link. */}
              {hasSummary ? (
                <span className="flex shrink-0 items-center gap-0.5 text-accent">
                  <ChevronDown
                    className={cn('size-3 transition-transform duration-fast', expanded && 'rotate-180')}
                    aria-hidden
                  />
                  Summary
                </span>
              ) : null}
            </span>
          </span>
        </button>

        <span className="hidden w-[104px] shrink-0 md:block">
          <Badge tone={document.fidelity === 'OCR dependent' ? 'accent' : 'outline'}>{document.fidelity}</Badge>
        </span>

        <span className="w-[112px] shrink-0 max-sm:w-auto">
          {processing && typeof document.progress === 'number' ? (
            <span className="flex items-center gap-2">
              <Progress value={document.progress} label={`Ingest progress for ${document.name}`} />
              <span className="font-mono text-2xs tabular-nums text-muted-foreground">{document.progress}%</span>
            </span>
          ) : (
            <Badge tone={status.tone} icon={StatusIcon} spinning={status.spin}>
              {status.label}
            </Badge>
          )}
        </span>

        <span className="hidden w-[92px] shrink-0 truncate text-2xs text-muted-foreground lg:block">
          {processing && document.stage ? (STAGE_LABEL[document.stage] ?? document.stage) : document.updated}
        </span>

        <button
          onClick={onOpen}
          aria-label={`Open evidence for ${document.name}`}
          className="grid size-7 shrink-0 place-items-center rounded text-muted-foreground transition-colors duration-fast hover:bg-muted hover:text-foreground"
        >
          <ChevronRight className="size-4" aria-hidden />
        </button>
      </div>

      {hasSummary && expanded ? (
        <div className="animate-slide-down border-t border-border bg-muted/30 px-3 py-3.5 pl-[54px] max-sm:pl-3">
          <div className="mb-2 flex flex-wrap items-center gap-2">
            <span className="eyebrow">Summary</span>
            {/* Extractive is verbatim document text; abstractive is model
                output. That changes how much a reader should trust the
                wording, so it is always labeled. */}
            <Badge tone={document.summaryMethod === 'abstractive' ? 'warning' : 'outline'}>
              {document.summaryMethod === 'abstractive' ? 'Model written' : 'From the document'}
            </Badge>
            {document.summaryProvider ? (
              <span className="font-mono text-2xs text-muted-foreground">{document.summaryProvider}</span>
            ) : null}
          </div>
          <p className="max-w-[78ch] text-sm leading-relaxed text-foreground/80">{document.summary}</p>
        </div>
      ) : null}
    </div>
  );
}
