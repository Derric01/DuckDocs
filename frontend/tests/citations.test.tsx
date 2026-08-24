/**
 * Citation grouping is where the product's honesty rules meet the UI: a
 * repeated passage must not inflate the source count, and the confidence a
 * card shows must be the worst one in the group, never an average that hides
 * a bad scan.
 */

import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { CitationList, groupCitations } from '@/components/workspace/citations';
import { at } from './helpers';
import type { EvidenceRecord } from '@/lib/types';

function evidence(overrides: Partial<EvidenceRecord> & { id: string }): EvidenceRecord {
  return {
    documentId: 'doc_1',
    documentName: 'lease.pdf',
    section: 'Section 4',
    page: 1,
    lines: '1-4',
    relevance: 'High',
    snippet: 'The tenant shall provide notice.',
    ...overrides,
  };
}

describe('groupCitations', () => {
  it('collapses passages from the same document into one group', () => {
    const groups = groupCitations([
      evidence({ id: 'ev_1', page: 3 }),
      evidence({ id: 'ev_2', page: 1 }),
      evidence({ id: 'ev_3', documentId: 'doc_2', documentName: 'policy.pdf' }),
    ]);

    expect(groups).toHaveLength(2);
    expect(at(groups, 0).passages.map((passage) => passage.id)).toEqual(['ev_2', 'ev_1']);
  });

  it('sorts passages by page so the reader follows the document order', () => {
    const groups = groupCitations([
      evidence({ id: 'ev_1', page: 9 }),
      evidence({ id: 'ev_2', page: 2 }),
      evidence({ id: 'ev_3', page: 5 }),
    ]);
    expect(at(groups, 0).passages.map((passage) => passage.page)).toEqual([2, 5, 9]);
  });

  it('shows a passage once even when the answer cites it twice', () => {
    const groups = groupCitations([evidence({ id: 'ev_1' }), evidence({ id: 'ev_1' })]);
    expect(at(groups, 0).passages).toHaveLength(1);
  });

  it('reports the lowest OCR confidence, not an average that would hide it', () => {
    const groups = groupCitations([
      evidence({ id: 'ev_1', ocrConfidence: 0.98 }),
      evidence({ id: 'ev_2', ocrConfidence: 0.31 }),
    ]);
    expect(at(groups, 0).minConfidence).toBe(0.31);
  });

  it('leaves confidence null for text that was never OCR’d', () => {
    expect(at(groupCitations([evidence({ id: 'ev_1' })]), 0).minConfidence).toBeNull();
  });

  it('falls back to the document name when no id came back', () => {
    const groups = groupCitations([
      evidence({ id: 'ev_1', documentId: undefined }),
      evidence({ id: 'ev_2', documentId: undefined }),
    ]);
    expect(groups).toHaveLength(1);
    expect(at(groups, 0).documentId).toBe('lease.pdf');
  });
});

describe('CitationList', () => {
  it('states how many passages came from how many documents', () => {
    render(
      <CitationList
        citations={[
          evidence({ id: 'ev_1', page: 1 }),
          evidence({ id: 'ev_2', page: 2 }),
          evidence({ id: 'ev_3', documentId: 'doc_2', documentName: 'policy.pdf' }),
        ]}
        onSelect={() => {}}
      />,
    );
    expect(screen.getByText('3 passages from 2 documents')).toBeInTheDocument();
  });

  it('uses the singular for one passage from one document', () => {
    render(<CitationList citations={[evidence({ id: 'ev_1' })]} onSelect={() => {}} />);
    expect(screen.getByText('1 passage from 1 document')).toBeInTheDocument();
  });

  it('renders nothing when there are no citations', () => {
    const { container } = render(<CitationList citations={[]} onSelect={() => {}} />);
    expect(container).toBeEmptyDOMElement();
  });

  it('selects the passage directly when a source has only one', async () => {
    const onSelect = vi.fn();
    render(<CitationList citations={[evidence({ id: 'ev_1' })]} onSelect={onSelect} />);

    await userEvent.click(screen.getByRole('button', { name: /lease\.pdf/ }));
    expect(onSelect).toHaveBeenCalledWith(expect.objectContaining({ id: 'ev_1' }));
  });

  it('expands to per-passage rows when a source has several', async () => {
    const onSelect = vi.fn();
    render(
      <CitationList
        citations={[evidence({ id: 'ev_1', page: 1 }), evidence({ id: 'ev_2', page: 7 })]}
        onSelect={onSelect}
      />,
    );

    const disclosure = screen.getByRole('button', { name: /lease\.pdf/ });
    expect(disclosure).toHaveAttribute('aria-expanded', 'false');

    await userEvent.click(disclosure);
    expect(disclosure).toHaveAttribute('aria-expanded', 'true');

    await userEvent.click(screen.getByText('p7'));
    expect(onSelect).toHaveBeenCalledWith(expect.objectContaining({ page: 7 }));
  });

  it('summarizes a page range rather than listing every page', () => {
    render(
      <CitationList
        citations={[1, 2, 3, 4, 9].map((page) => evidence({ id: `ev_${page}`, page }))}
        onSelect={() => {}}
      />,
    );
    expect(screen.getByText('Pages 1–9 · 5 total')).toBeInTheDocument();
  });

  it('surfaces low OCR confidence instead of quietly rendering the text', () => {
    render(<CitationList citations={[evidence({ id: 'ev_1', ocrConfidence: 0.22 })]} onSelect={() => {}} />);
    expect(screen.getByTitle('Lowest OCR confidence in this source: 22%')).toBeInTheDocument();
  });
});
