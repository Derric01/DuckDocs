'use client';

/**
 * Evidence inspector: the rendered source page with the stored bounding box
 * drawn over it, or the extracted text with its provenance metadata. Formats
 * without a page image fall back to the text view automatically.
 */

import { AlertTriangle, FileText, PanelRight, ScanText, X } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { Badge, Button, EmptyState, Tabs, TabsList, TabsTrigger } from '@/components/ui';
import { PageViewer } from '@/components/workspace/page-viewer';
import { useWorkspace } from '@/components/workspace/workspace-provider';
import { cn } from '@/lib/utils';
import type { AnchorQuality, EvidenceRecord } from '@/lib/types';

const ANCHOR_LABEL: Record<AnchorQuality, string> = {
  line: 'Line',
  paragraph: 'Paragraph',
  cell: 'Cell',
  bbox: 'Bounding box',
};

/** Formats that can produce a rendered page image (see services/preview.py). */
const PREVIEWABLE = new Set(['pdf', 'png', 'jpg', 'jpeg', 'webp', 'tiff', 'tif', 'bmp']);

/** Below this, OCR output is flagged for verification (docs/22 Rule OCR-01). */
const LOW_CONFIDENCE = 0.6;

export function EvidencePanel({
  evidence,
  onClose,
}: {
  evidence: EvidenceRecord | null;
  onClose: () => void;
}) {
  return (
    <aside
      aria-label="Evidence inspector"
      className="flex h-full flex-col border-l border-border bg-background max-lg:fixed max-lg:inset-y-0 max-lg:right-0 max-lg:z-50 max-lg:w-[min(440px,92vw)] max-lg:animate-slide-in-right max-lg:shadow-xl"
    >
      <div className="flex h-12 shrink-0 items-center justify-between gap-3 border-b border-border px-3.5">
        <h2 className="eyebrow">Evidence</h2>
        <Button variant="ghost" size="sm" className="size-7 p-0" aria-label="Close evidence panel" onClick={onClose}>
          <X className="size-4" />
        </Button>
      </div>
      {evidence ? (
        <EvidenceDetail evidence={evidence} />
      ) : (
        <div className="flex-1 overflow-y-auto">
          <EmptyState
            icon={PanelRight}
            title="Nothing selected"
            description="Open a citation from an answer, or inspect a document, to see the exact passage it came from."
          />
        </div>
      )}
    </aside>
  );
}

function EvidenceDetail({ evidence }: { evidence: EvidenceRecord }) {
  const { documents } = useWorkspace();

  const document = useMemo(
    () => documents.find((item) => item.id === evidence.documentId),
    [documents, evidence.documentId],
  );

  const canPreview = Boolean(evidence.documentId && document && PREVIEWABLE.has(document.type.toLowerCase()));

  const [tab, setTab] = useState<'source' | 'text'>(canPreview ? 'source' : 'text');
  const [page, setPage] = useState(evidence.page);

  // A new citation jumps the viewer to its page; if the new source has no page
  // image, drop back to text rather than showing an error.
  useEffect(() => {
    setPage(evidence.page);
    setTab(canPreview ? 'source' : 'text');
  }, [evidence.id, evidence.page, canPreview]);

  // The stored box belongs to this evidence's page; don't draw it elsewhere.
  const highlight = page === evidence.page ? evidence.bbox : null;

  return (
    <>
      {canPreview ? (
        <div className="shrink-0 border-b border-border px-3.5 py-1">
          <Tabs value={tab} onValueChange={(value) => setTab(value as 'source' | 'text')}>
            <TabsList className="w-full">
              <TabsTrigger value="source" className="flex-1">
                Source page
              </TabsTrigger>
              <TabsTrigger value="text" className="flex-1">
                Extracted text
              </TabsTrigger>
            </TabsList>
          </Tabs>
        </div>
      ) : null}

      {tab === 'source' && canPreview && document ? (
        <div className="flex min-h-0 flex-1 flex-col">
          <PageViewer
            documentId={document.id}
            documentName={document.name}
            pageCount={document.pages}
            page={page}
            onPageChange={setPage}
            highlight={highlight}
          />
        </div>
      ) : (
        <div className="flex-1 overflow-y-auto p-4">
          <EvidenceText evidence={evidence} showFallbackNote={!canPreview} />
        </div>
      )}
    </>
  );
}

function EvidenceText({
  evidence,
  showFallbackNote,
}: {
  evidence: EvidenceRecord;
  showFallbackNote: boolean;
}) {
  const confidence = evidence.ocrConfidence;
  const isOcr = evidence.fidelity === 'OCR dependent' || typeof confidence === 'number';
  const isLow = typeof confidence === 'number' && confidence < LOW_CONFIDENCE;

  return (
    <div className="space-y-4">
      <div className="flex items-start gap-2.5">
        <span className="grid size-8 shrink-0 place-items-center rounded-sm border border-border bg-muted text-muted-foreground">
          <FileText className="size-4" strokeWidth={1.7} aria-hidden />
        </span>
        <div className="min-w-0">
          <p className="truncate text-sm font-medium text-foreground">{evidence.documentName}</p>
          <p className="truncate text-2xs text-muted-foreground">{evidence.section}</p>
        </div>
      </div>

      <div className="flex flex-wrap gap-1.5">
        <Badge tone="outline">Page {evidence.page}</Badge>
        <Badge tone="outline">Lines {evidence.lines}</Badge>
        <Badge tone={evidence.relevance === 'High' ? 'accent' : 'neutral'}>
          {evidence.relevance} relevance
        </Badge>
      </div>

      {isOcr ? (
        <div
          role="note"
          className={cn(
            'flex items-start gap-2.5 rounded-lg border p-3 text-xs leading-snug',
            isLow ? 'border-warning/25 bg-warning-muted text-warning' : 'border-border bg-muted text-muted-foreground',
          )}
        >
          {isLow ? (
            <AlertTriangle className="mt-px size-3.5 shrink-0" aria-hidden />
          ) : (
            <ScanText className="mt-px size-3.5 shrink-0" aria-hidden />
          )}
          <span>
            {typeof confidence === 'number' ? (
              <>
                Recognized by local OCR at <strong className="font-semibold">{Math.round(confidence * 100)}%</strong>{' '}
                confidence{evidence.ocrEngine ? ` (${evidence.ocrEngine})` : ''}.
                {isLow ? ' Check this passage against the source before relying on it.' : ''}
              </>
            ) : (
              <>This passage came from OCR. Confidence was not recorded for it.</>
            )}
          </span>
        </div>
      ) : null}

      <div className="rounded-lg border border-border bg-card p-3.5">
        <p className="text-sm leading-relaxed text-foreground">
          <mark className="bg-accent-muted text-foreground">{evidence.snippet}</mark>
        </p>
      </div>

      <dl className="grid grid-cols-2 gap-x-4 gap-y-3 border-t border-border pt-4">
        <Meta label="Anchor" value={ANCHOR_LABEL[evidence.anchorQuality ?? 'line']} />
        <Meta label="Fidelity" value={evidence.fidelity ?? 'Full layout'} />
        <Meta label="Evidence ID" value={evidence.id} />
        {evidence.bbox ? (
          <Meta label="Region" value={evidence.bbox.map((value) => value.toFixed(2)).join(', ')} />
        ) : null}
      </dl>

      {showFallbackNote ? (
        <p className="text-xs leading-snug text-muted-foreground">
          This format has no page image, so the extracted text is the source of record.
        </p>
      ) : null}
    </div>
  );
}

function Meta({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0">
      <dt className="eyebrow">{label}</dt>
      <dd className="mt-1 truncate font-mono text-2xs text-foreground/80">{value}</dd>
    </div>
  );
}
