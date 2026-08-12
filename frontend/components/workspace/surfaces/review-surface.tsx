'use client';

import { AlertCircle, CheckCircle2, ChevronRight, ScanText } from 'lucide-react';
import { Badge, Card, EmptyState } from '@/components/ui';
import { useWorkspace } from '@/components/workspace/workspace-provider';
import type { DocumentRecord } from '@/lib/types';

function reason(document: DocumentRecord): string {
  if (document.status === 'failed') return 'Processing failed. Check the file, then add it again.';
  return 'No readable text was found, even after OCR. The file is stored but is not searchable.';
}

export function ReviewSurface() {
  const { documents, inspectDocument } = useWorkspace();

  const attention = documents.filter((d) => d.status === 'review' || d.status === 'failed');
  const ready = documents.filter((d) => d.status === 'ready');
  const ocrCount = documents.filter((d) => d.fidelity === 'OCR dependent').length;
  const coverage = documents.length ? Math.round((ready.length / documents.length) * 100) : 0;

  return (
    <div className="mx-auto max-w-4xl px-8 pb-16 pt-8 max-sm:px-4 max-sm:pt-5">
      <header className="mb-6">
        <h2 className="text-3xl font-bold tracking-tight">Review</h2>
        <p className="mt-1.5 max-w-prose text-sm text-muted-foreground">
          Documents that need attention before they can be cited, and how much of your library is searchable.
        </p>
      </header>

      <div className="mb-6 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label="Searchable" value={`${coverage}%`} />
        <Stat label="Ready documents" value={String(ready.length)} />
        <Stat label="Needs attention" value={String(attention.length)} />
        <Stat label="OCR-derived" value={String(ocrCount)} />
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
        <div className="list-group">
          {attention.map((document) => (
            <button
              key={document.id}
              onClick={() => void inspectDocument(document)}
              className="flex w-full items-center gap-4 border-b border-border/70 p-4 text-left transition-colors duration-fast last:border-b-0 hover:bg-muted/40"
            >
              <span className="grid size-9 shrink-0 place-items-center rounded-lg bg-muted text-muted-foreground">
                {document.status === 'failed' ? (
                  <AlertCircle className="size-4" strokeWidth={1.8} aria-hidden />
                ) : (
                  <ScanText className="size-4" strokeWidth={1.8} aria-hidden />
                )}
              </span>
              <span className="min-w-0 flex-1">
                <span className="block truncate text-sm font-medium text-foreground">{document.name}</span>
                <span className="mt-0.5 block text-xs text-muted-foreground">{reason(document)}</span>
              </span>
              <Badge tone={document.status === 'failed' ? 'destructive' : 'warning'}>
                {document.status === 'failed' ? 'Failed' : 'Needs review'}
              </Badge>
              <ChevronRight className="size-4 shrink-0 text-muted-foreground" aria-hidden />
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <Card className="p-4">
      <p className="text-2xs text-muted-foreground">{label}</p>
      <p className="mt-1.5 text-2xl font-semibold tabular-nums tracking-tight">{value}</p>
    </Card>
  );
}
