'use client';

/**
 * Citation rendering for answers.
 *
 * Retrieval frequently returns several passages from the same document, so a
 * flat list repeats the filename and buries how many distinct sources actually
 * support an answer. Citations are therefore grouped by document and
 * deduplicated by evidence id, with per-passage rows underneath.
 */

import { ChevronDown, FileText, ScanText } from 'lucide-react';
import { useMemo, useState } from 'react';
import type { EvidenceRecord } from '@/lib/types';

const LOW_CONFIDENCE = 0.6;

interface CitationGroup {
  documentId: string;
  documentName: string;
  passages: EvidenceRecord[];
  /** Lowest OCR confidence in the group; drives the honesty indicator. */
  minConfidence: number | null;
}

export function groupCitations(citations: EvidenceRecord[]): CitationGroup[] {
  const seen = new Set<string>();
  const groups = new Map<string, CitationGroup>();

  for (const citation of citations) {
    // The same passage can be cited more than once in an answer; show it once.
    if (seen.has(citation.id)) continue;
    seen.add(citation.id);

    const key = citation.documentId ?? citation.documentName;
    const existing = groups.get(key);
    if (existing) {
      existing.passages.push(citation);
      if (typeof citation.ocrConfidence === 'number') {
        existing.minConfidence =
          existing.minConfidence === null
            ? citation.ocrConfidence
            : Math.min(existing.minConfidence, citation.ocrConfidence);
      }
    } else {
      groups.set(key, {
        documentId: key,
        documentName: citation.documentName,
        passages: [citation],
        minConfidence: typeof citation.ocrConfidence === 'number' ? citation.ocrConfidence : null,
      });
    }
  }

  // Sort pages within a document so passages read in document order.
  for (const group of groups.values()) {
    group.passages.sort((a, b) => a.page - b.page);
  }
  return [...groups.values()];
}

export function CitationList({
  citations,
  activeId,
  onSelect,
}: {
  citations: EvidenceRecord[];
  activeId?: string | null;
  onSelect: (evidence: EvidenceRecord) => void;
}) {
  const groups = useMemo(() => groupCitations(citations), [citations]);
  if (groups.length === 0) return null;

  const totalPassages = groups.reduce((total, group) => total + group.passages.length, 0);

  return (
    <section className="citations" aria-label="Sources">
      <p className="citations-summary">
        {totalPassages} passage{totalPassages === 1 ? '' : 's'} from {groups.length} document
        {groups.length === 1 ? '' : 's'}
      </p>
      {groups.map((group) => (
        <CitationCard key={group.documentId} group={group} activeId={activeId} onSelect={onSelect} />
      ))}
    </section>
  );
}

function CitationCard({
  group,
  activeId,
  onSelect,
}: {
  group: CitationGroup;
  activeId?: string | null;
  onSelect: (evidence: EvidenceRecord) => void;
}) {
  // A single passage needs no disclosure; multiples start collapsed so a
  // heavily-cited answer stays scannable.
  const single = group.passages.length === 1;
  const [open, setOpen] = useState(single);

  const isOcr = group.minConfidence !== null;
  const isLow = group.minConfidence !== null && group.minConfidence < LOW_CONFIDENCE;
  const pageRange = pageSummary(group.passages);

  return (
    <article className={`citation-card ${isLow ? 'is-low' : ''}`}>
      <button
        className="citation-card-head"
        aria-expanded={open}
        onClick={() => {
          if (single) {
            const only = group.passages[0];
            if (only) onSelect(only);
            return;
          }
          setOpen((value) => !value);
        }}
      >
        <span className="citation-card-icon" aria-hidden="true">
          {isOcr ? <ScanText size={14} strokeWidth={1.7} /> : <FileText size={14} strokeWidth={1.7} />}
        </span>
        <span className="citation-card-copy">
          <strong>{group.documentName}</strong>
          <span className="mono">{pageRange}</span>
        </span>
        {isOcr ? (
          <span
            className={`confidence-pip ${isLow ? 'low' : ''}`}
            title={`Lowest OCR confidence in this source: ${Math.round((group.minConfidence ?? 0) * 100)}%`}
          >
            <span className="confidence-pip-fill" style={{ width: `${(group.minConfidence ?? 0) * 100}%` }} />
          </span>
        ) : null}
        {!single ? (
          <ChevronDown
            size={14}
            strokeWidth={1.8}
            className="citation-card-chevron"
            data-open={open}
            aria-hidden="true"
          />
        ) : null}
      </button>

      {open && !single ? (
        <ul className="citation-passages">
          {group.passages.map((passage) => (
            <li key={passage.id}>
              <button
                className="citation-passage"
                data-active={passage.id === activeId}
                onClick={() => onSelect(passage)}
              >
                <span className="mono citation-passage-page">p{passage.page}</span>
                <span className="citation-passage-text">{passage.snippet}</span>
              </button>
            </li>
          ))}
        </ul>
      ) : null}
    </article>
  );
}

function pageSummary(passages: EvidenceRecord[]): string {
  const pages = [...new Set(passages.map((passage) => passage.page))].sort((a, b) => a - b);
  if (pages.length === 0) return '';
  if (pages.length === 1) return `p${pages[0]}`;
  if (pages.length <= 3) return pages.map((page) => `p${page}`).join(', ');
  return `p${pages[0]}–p${pages[pages.length - 1]} · ${pages.length} pages`;
}
