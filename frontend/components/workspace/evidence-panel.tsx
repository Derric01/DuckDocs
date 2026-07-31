'use client';

/**
 * Evidence inspector.
 *
 * Two tabs over the same evidence: the rendered source page (with the stored
 * bounding box drawn over it) and the extracted text with its provenance
 * metadata. Formats without a page image (docx, xlsx, text) fall back to the
 * passage view automatically rather than showing a broken viewer.
 */

import { AlertTriangle, FileText, PanelRight, ScanText, X } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { Badge, EmptyState, IconButton } from '@/components/ui';
import { PageViewer } from '@/components/workspace/page-viewer';
import { useWorkspace } from '@/components/workspace/workspace-provider';
import type { AnchorQuality, EvidenceRecord } from '@/lib/types';

const ANCHOR_LABEL: Record<AnchorQuality, string> = {
  line: 'Line',
  paragraph: 'Paragraph',
  cell: 'Cell',
  bbox: 'Bounding box',
};

/** Formats that can produce a rendered page image (see services/preview.py). */
const PREVIEWABLE = new Set(['pdf', 'png', 'jpg', 'jpeg', 'webp', 'tiff', 'tif', 'bmp']);

/**
 * Below this, OCR output is called out as needing verification rather than
 * presented as settled text (docs/22 Rule OCR-01: label uncertainty).
 */
const LOW_CONFIDENCE = 0.6;

type Tab = 'source' | 'text';

export function EvidencePanel({
  evidence,
  onClose,
}: {
  evidence: EvidenceRecord | null;
  onClose: () => void;
}) {
  return (
    <aside className="panel" aria-label="Evidence inspector">
      <div className="panel-head">
        <h2>Evidence</h2>
        <IconButton icon={X} label="Close evidence panel" onClick={onClose} />
      </div>
      {evidence ? <EvidenceDetail evidence={evidence} /> : <EvidenceEmpty />}
    </aside>
  );
}

function EvidenceEmpty() {
  return (
    <div className="panel-body">
      <EmptyState
        icon={PanelRight}
        title="Nothing selected"
        description="Open a citation from an answer, or inspect a document, to see the exact passage it came from."
      />
    </div>
  );
}

function EvidenceDetail({ evidence }: { evidence: EvidenceRecord }) {
  const { documents } = useWorkspace();

  const document = useMemo(
    () => documents.find((item) => item.id === evidence.documentId),
    [documents, evidence.documentId],
  );

  const canPreview = Boolean(
    evidence.documentId && document && PREVIEWABLE.has(document.type.toLowerCase()),
  );

  const [tab, setTab] = useState<Tab>(canPreview ? 'source' : 'text');
  const [page, setPage] = useState(evidence.page);

  // A new citation should jump the viewer to its page and, if the new source
  // has no page image, drop back to the text tab rather than showing an error.
  useEffect(() => {
    setPage(evidence.page);
    setTab(canPreview ? 'source' : 'text');
  }, [evidence.id, evidence.page, canPreview]);

  // The stored box belongs to the evidence's own page; don't draw it over a
  // different page the user has navigated to.
  const highlight = page === evidence.page ? evidence.bbox : null;

  return (
    <>
      {canPreview ? (
        <div className="panel-tabs" role="tablist" aria-label="Evidence view">
          <button
            className="panel-tab"
            role="tab"
            aria-selected={tab === 'source'}
            onClick={() => setTab('source')}
          >
            Source page
          </button>
          <button
            className="panel-tab"
            role="tab"
            aria-selected={tab === 'text'}
            onClick={() => setTab('text')}
          >
            Extracted text
          </button>
        </div>
      ) : null}

      {tab === 'source' && canPreview && document ? (
        <div className="panel-viewer">
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
        <div className="panel-body">
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
    <>
      <div className="evidence-source">
        <span className="doc-icon" aria-hidden="true">
          <FileText size={15} strokeWidth={1.7} />
        </span>
        <div style={{ minWidth: 0 }}>
          <strong>{evidence.documentName}</strong>
          <span>{evidence.section}</span>
        </div>
      </div>

      <div className="evidence-locator">
        <Badge>Page {evidence.page}</Badge>
        <Badge>Lines {evidence.lines}</Badge>
        <Badge tone={evidence.relevance === 'High' ? 'accent' : 'neutral'}>
          {evidence.relevance} relevance
        </Badge>
      </div>

      {isOcr ? (
        <div className={`confidence-note ${isLow ? 'low' : ''}`} role="note">
          {isLow ? (
            <AlertTriangle size={14} strokeWidth={1.8} aria-hidden="true" />
          ) : (
            <ScanText size={14} strokeWidth={1.8} aria-hidden="true" />
          )}
          <span>
            {typeof confidence === 'number' ? (
              <>
                Recognized by local OCR at <strong>{Math.round(confidence * 100)}%</strong> confidence
                {evidence.ocrEngine ? ` (${evidence.ocrEngine})` : ''}.
                {isLow ? ' Check this passage against the source before relying on it.' : ''}
              </>
            ) : (
              <>This passage came from OCR. Confidence was not recorded for it.</>
            )}
          </span>
        </div>
      ) : null}

      <div className="passage">
        <p>
          <mark className="passage-mark">{evidence.snippet}</mark>
        </p>
      </div>

      <div className="meta-grid">
        <div className="meta-cell">
          <span>Anchor</span>
          <strong>{ANCHOR_LABEL[evidence.anchorQuality ?? 'line']}</strong>
        </div>
        <div className="meta-cell">
          <span>Fidelity</span>
          <strong>{evidence.fidelity ?? 'Full layout'}</strong>
        </div>
        <div className="meta-cell">
          <span>Evidence ID</span>
          <strong>{evidence.id}</strong>
        </div>
        {evidence.bbox ? (
          <div className="meta-cell">
            <span>Region</span>
            <strong>{evidence.bbox.map((value) => value.toFixed(2)).join(', ')}</strong>
          </div>
        ) : null}
      </div>

      {showFallbackNote ? (
        <p className="field-hint" style={{ marginTop: 'var(--space-4)' }}>
          This format has no page image, so the extracted text is the source of record.
        </p>
      ) : null}
    </>
  );
}
