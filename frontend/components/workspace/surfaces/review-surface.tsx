'use client';

import { AlertCircle, CheckCircle2, ChevronRight, ScanText } from 'lucide-react';
import { Badge, EmptyState } from '@/components/ui';
import { useWorkspace } from '@/components/workspace/workspace-provider';
import type { DocumentRecord } from '@/lib/types';

function reason(document: DocumentRecord): string {
  if (document.status === 'failed') {
    return 'Processing failed. Check the file, then add it again.';
  }
  return 'No readable text was found, even after OCR. The file is stored but is not searchable.';
}

export function ReviewSurface() {
  const { documents, inspectDocument } = useWorkspace();

  const attention = documents.filter(
    (document) => document.status === 'review' || document.status === 'failed',
  );
  const ready = documents.filter((document) => document.status === 'ready');
  const ocrCount = documents.filter((document) => document.fidelity === 'OCR dependent').length;
  const coverage = documents.length ? Math.round((ready.length / documents.length) * 100) : 0;

  return (
    <div className="surface surface-narrow">
      <header className="surface-head">
        <div className="surface-head-row">
          <div>
            <h2>Review</h2>
            <p>Documents that need attention before they can be cited, and how much of your library is searchable.</p>
          </div>
        </div>
      </header>

      <div className="stat-grid">
        <div className="stat">
          <p className="stat-label">Searchable</p>
          <p className="stat-value">{coverage}%</p>
        </div>
        <div className="stat">
          <p className="stat-label">Ready documents</p>
          <p className="stat-value">{ready.length}</p>
        </div>
        <div className="stat">
          <p className="stat-label">Needs attention</p>
          <p className="stat-value">{attention.length}</p>
        </div>
        <div className="stat">
          <p className="stat-label">OCR-derived</p>
          <p className="stat-value">{ocrCount}</p>
        </div>
      </div>

      {attention.length === 0 ? (
        <EmptyState
          icon={CheckCircle2}
          title="Nothing needs review"
          description={
            documents.length
              ? 'Every document in your library parsed cleanly and is searchable.'
              : 'Add documents to your library and anything that needs attention will appear here.'
          }
        />
      ) : (
        <div className="review-list">
          {attention.map((document) => (
            <button key={document.id} className="review-row" onClick={() => void inspectDocument(document)}>
              <span className="doc-icon" aria-hidden="true">
                {document.status === 'failed' ? (
                  <AlertCircle size={15} strokeWidth={1.7} />
                ) : (
                  <ScanText size={15} strokeWidth={1.7} />
                )}
              </span>
              <span className="review-copy">
                <strong>{document.name}</strong>
                <p>{reason(document)}</p>
              </span>
              <Badge tone={document.status === 'failed' ? 'danger' : 'warning'}>
                {document.status === 'failed' ? 'Failed' : 'Needs review'}
              </Badge>
              <ChevronRight size={15} strokeWidth={1.8} className="doc-chevron" aria-hidden="true" />
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
