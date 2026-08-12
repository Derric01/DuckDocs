'use client';

/**
 * Citation rendering for answers.
 *
 * Retrieval frequently returns several passages from the same document, so a
 * flat list repeats the filename and buries how many distinct sources support
 * an answer. Citations are grouped by document and deduplicated by evidence
 * id, with per-passage rows underneath.
 */

import { ChevronDown, FileText, ScanText } from 'lucide-react';
import { useMemo, useState } from 'react';
import { cn } from '@/lib/utils';
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

  const total = groups.reduce((sum, group) => sum + group.passages.length, 0);

  return (
    <section aria-label="Sources" className="mt-5 space-y-2">
      <p className="text-2xs font-semibold uppercase tracking-wider text-muted-foreground/70">
        {total} passage{total === 1 ? '' : 's'} from {groups.length} document{groups.length === 1 ? '' : 's'}
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

  return (
    <div
      className={cn(
        'overflow-hidden rounded-xl bg-card shadow-xs ring-1 ring-inset transition-all duration-fast',
        isLow ? 'ring-warning/40' : 'ring-border hover:ring-border-strong',
      )}
    >
      <button
        aria-expanded={open}
        onClick={() => {
          if (single) {
            const only = group.passages[0];
            if (only) onSelect(only);
            return;
          }
          setOpen((value) => !value);
        }}
        className="flex w-full items-center gap-3 p-3 text-left transition-colors duration-fast hover:bg-muted/50"
      >
        <span className="grid size-7 shrink-0 place-items-center rounded-lg bg-muted text-muted-foreground">
          {isOcr ? <ScanText className="size-3.5" aria-hidden /> : <FileText className="size-3.5" aria-hidden />}
        </span>
        <span className="min-w-0 flex-1">
          <span className="block truncate text-sm font-medium text-foreground">{group.documentName}</span>
          <span className="block font-mono text-2xs text-muted-foreground">{pageSummary(group.passages)}</span>
        </span>

        {isOcr ? (
          <span
            title={`Lowest OCR confidence in this source: ${Math.round((group.minConfidence ?? 0) * 100)}%`}
            className="h-1 w-7 shrink-0 overflow-hidden rounded-full bg-muted"
          >
            {/* A track rather than a number: the exact value lives in the
                evidence panel, this only needs to convey trust at a glance. */}
            <span
              className={cn('block h-full rounded-full', isLow ? 'bg-warning' : 'bg-success')}
              style={{ width: `${(group.minConfidence ?? 0) * 100}%` }}
            />
          </span>
        ) : null}

        {!single ? (
          <ChevronDown
            className={cn(
              'size-3.5 shrink-0 text-muted-foreground transition-transform duration-200 ease-spring',
              open && 'rotate-180',
            )}
            aria-hidden
          />
        ) : null}
      </button>

      {open && !single ? (
        <ul className="animate-slide-down space-y-0.5 px-2 pb-2">
          {group.passages.map((passage) => (
            <li key={passage.id}>
              <button
                onClick={() => onSelect(passage)}
                className={cn(
                  'flex w-full items-baseline gap-3 rounded-lg px-2 py-2 text-left transition-colors duration-fast',
                  passage.id === activeId ? 'bg-primary/10' : 'hover:bg-muted',
                )}
              >
                <span className="shrink-0 font-mono text-2xs tabular-nums text-primary-vivid">p{passage.page}</span>
                <span
                  className={cn(
                    'line-clamp-2 text-xs leading-snug',
                    passage.id === activeId ? 'text-foreground' : 'text-muted-foreground',
                  )}
                >
                  {passage.snippet}
                </span>
              </button>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

function pageSummary(passages: EvidenceRecord[]): string {
  const pages = [...new Set(passages.map((passage) => passage.page))].sort((a, b) => a - b);
  if (pages.length === 0) return '';
  if (pages.length === 1) return `Page ${pages[0]}`;
  if (pages.length <= 3) return `Pages ${pages.join(', ')}`;
  return `Pages ${pages[0]}–${pages[pages.length - 1]} · ${pages.length} total`;
}
