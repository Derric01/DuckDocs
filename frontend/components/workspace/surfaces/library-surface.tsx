'use client';

import {
  AlertCircle,
  Check,
  ChevronRight,
  FileCode2,
  FileImage,
  FileSpreadsheet,
  FileText,
  FileType2,
  LoaderCircle,
  Search,
  Sparkles,
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
 * file, so a long library becomes scannable without reading extensions.
 */
function kindFor(type: string): { icon: LucideIcon; tile: string } {
  const upper = type.toUpperCase();
  if (upper === 'PDF') return { icon: FileType2, tile: 'bg-ios-red' };
  if (['CSV', 'XLSX'].includes(upper)) return { icon: FileSpreadsheet, tile: 'bg-ios-green' };
  if (['PNG', 'JPG', 'JPEG', 'WEBP', 'TIFF', 'TIF', 'BMP'].includes(upper)) {
    return { icon: FileImage, tile: 'bg-ios-purple' };
  }
  if (['TS', 'TSX', 'JS', 'JSX', 'PY', 'JSON', 'XML', 'YAML', 'YML', 'SQL', 'GO', 'RS'].includes(upper)) {
    return { icon: FileCode2, tile: 'bg-ios-indigo' };
  }
  if (['DOCX', 'PPTX'].includes(upper)) return { icon: FileText, tile: 'bg-ios-blue' };
  return { icon: FileText, tile: 'bg-ios-gray' };
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
    <div className="mx-auto max-w-4xl px-8 pb-16 pt-8 max-sm:px-4 max-sm:pt-5">
      <header className="mb-6 flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 className="text-3xl font-bold tracking-tight">Library</h2>
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
          <Upload className="size-4" aria-hidden />
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
          'flex w-full items-center gap-4 rounded-2xl border-2 border-dashed p-5 text-left',
          'transition-all duration-200 ease-spring active:scale-[0.995]',
          dragging ? 'border-primary bg-primary/5' : 'border-border hover:border-border-strong hover:bg-card',
        )}
      >
        <span
          className={cn(
            'icon-tile size-11 transition-colors duration-200',
            dragging ? 'bg-ios-blue' : 'bg-gradient-to-br from-ios-blue to-ios-indigo',
          )}
        >
          {uploading ? (
            <LoaderCircle className="size-5 animate-spin" />
          ) : (
            <Upload className="size-5" strokeWidth={2} />
          )}
        </span>
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

      <div className="mb-3 mt-6 flex flex-wrap items-center justify-between gap-3">
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

        <div className="relative w-full sm:w-56">
          <Search
            className="pointer-events-none absolute left-3 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground"
            aria-hidden
          />
          <Input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Filter by name"
            aria-label="Filter documents by name"
            className="h-9 pl-8 text-sm"
          />
        </div>
      </div>

      {documentsLoading ? (
        <div className="space-y-2">
          {[0, 1, 2].map((row) => (
            <Skeleton key={row} className="h-16 rounded-xl" />
          ))}
        </div>
      ) : visible.length === 0 ? (
        <EmptyState
          icon={documents.length ? Search : Upload}
          title={documents.length ? 'No matching documents' : 'Nothing here yet 📂'}
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
        <div className="list-group">
          {visible.map((document) => (
            <DocumentRow key={document.id} document={document} onOpen={() => void inspectDocument(document)} />
          ))}
        </div>
      )}
    </div>
  );
}

function DocumentRow({ document, onOpen }: { document: DocumentRecord; onOpen: () => void }) {
  const { icon: Icon, tile } = kindFor(document.type);
  const status = STATUS[document.status];
  const StatusIcon = status.icon;
  const processing = document.status === 'processing';
  const [expanded, setExpanded] = useState(false);
  const hasSummary = Boolean(document.summary);

  return (
    <div className="border-b border-border/70 last:border-b-0">
      <div className="flex min-h-[60px] items-center gap-3 px-4 transition-colors duration-fast hover:bg-muted/40">
        <button
          onClick={() => (hasSummary ? setExpanded((value) => !value) : onOpen())}
          aria-expanded={hasSummary ? expanded : undefined}
          className="flex min-w-0 flex-1 items-center gap-3 py-2.5 text-left"
        >
          <span className={cn('icon-tile size-9', tile)}>
            <Icon className="size-[18px]" strokeWidth={2} aria-hidden />
          </span>
          <span className="min-w-0">
            <span className="block truncate text-sm font-medium text-foreground">{document.name}</span>
            <span className="block truncate text-2xs text-muted-foreground">
              {document.type} · {document.size} · {document.pages} page{document.pages === 1 ? '' : 's'}
            </span>
          </span>
        </button>

        <span className="hidden shrink-0 md:block">
          <Badge tone={document.fidelity === 'OCR dependent' ? 'primary' : 'neutral'}>{document.fidelity}</Badge>
        </span>

        <span className="w-[108px] shrink-0 max-sm:w-auto">
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

        <span className="hidden w-[92px] shrink-0 text-xs text-muted-foreground lg:block">
          {processing && document.stage ? (STAGE_LABEL[document.stage] ?? document.stage) : document.updated}
        </span>

        <button
          onClick={onOpen}
          aria-label={`Open evidence for ${document.name}`}
          className="grid size-8 shrink-0 place-items-center rounded-lg text-muted-foreground transition-colors duration-fast hover:bg-muted hover:text-foreground"
        >
          <ChevronRight className="size-4" aria-hidden />
        </button>
      </div>

      {hasSummary && expanded ? (
        <div className="animate-slide-down px-4 pb-4 pl-[64px] max-sm:pl-4">
          <div className="mb-2 flex flex-wrap items-center gap-2 text-muted-foreground">
            <Sparkles className="size-3.5 text-ios-purple" aria-hidden />
            <span className="text-2xs font-semibold uppercase tracking-wider">Summary</span>
            {/* Extractive is verbatim document text; abstractive is model
                output. That changes how much a reader should trust the
                wording, so it is always labeled. */}
            <Badge tone={document.summaryMethod === 'abstractive' ? 'warning' : 'neutral'}>
              {document.summaryMethod === 'abstractive' ? 'Model written' : 'From the document'}
            </Badge>
            {document.summaryProvider ? (
              <span className="font-mono text-2xs opacity-70">{document.summaryProvider}</span>
            ) : null}
          </div>
          <p className="max-w-[76ch] text-sm leading-relaxed text-muted-foreground">{document.summary}</p>
        </div>
      ) : null}
    </div>
  );
}
