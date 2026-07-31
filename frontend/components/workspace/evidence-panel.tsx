'use client';

import { AlertTriangle, FileText, PanelRight, ScanText, X } from 'lucide-react';
import { Badge, EmptyState, IconButton } from '@/components/ui';
import type { AnchorQuality, EvidenceRecord } from '@/lib/types';

const ANCHOR_LABEL: Record<AnchorQuality, string> = {
  line: 'Line',
  paragraph: 'Paragraph',
  cell: 'Cell',
  bbox: 'Bounding box',
};

/**
 * Below this, OCR output is called out as needing verification rather than
 * presented as settled text. Mirrors the backend's confidence threshold
 * intent in docs/22 (Rule OCR-01): label uncertainty, never hide it.
 */
const LOW_CONFIDENCE = 0.6;

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
      <div className="panel-body">
        {evidence ? <EvidenceDetail evidence={evidence} /> : <EvidenceEmpty />}
      </div>
    </aside>
  );
}

function EvidenceEmpty() {
  return (
    <EmptyState
      icon={PanelRight}
      title="Nothing selected"
      description="Open a citation from an answer, or inspect a document, to see the exact passage it came from."
    />
  );
}

function EvidenceDetail({ evidence }: { evidence: EvidenceRecord }) {
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
        <Badge tone={evidence.relevance === 'High' ? 'accent' : 'neutral'}>{evidence.relevance} relevance</Badge>
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
            <strong>
              {evidence.bbox.map((value) => value.toFixed(2)).join(', ')}
            </strong>
          </div>
        ) : null}
      </div>
    </>
  );
}
