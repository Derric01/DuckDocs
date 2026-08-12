'use client';

import { AlertTriangle, ArrowUp, Copy, FileText, LockKeyhole, Paperclip } from 'lucide-react';
import { memo, useCallback, useEffect, useRef, useState } from 'react';
import { Button, EmptyState, useToast } from '@/components/ui';
import { CitationList } from '@/components/workspace/citations';
import { useWorkspace } from '@/components/workspace/workspace-provider';
import { cn } from '@/lib/utils';
import type { EvidenceRecord, MessageRecord } from '@/lib/types';

const ACCEPT =
  '.pdf,.docx,.xlsx,.pptx,.txt,.md,.csv,.html,.htm,.json,.xml,.yaml,.yml,.png,.jpg,.jpeg,.webp,.tiff,.tif,.bmp,.ts,.tsx,.js,.jsx,.py,.java,.c,.cpp,.cs,.go,.rs,.sql,.css,.sh,.rb,.php,.kt,.swift';

const SUGGESTIONS = [
  'What changed since the last version?',
  'Summarize the retention rules',
  'List the open obligations',
];

function prefersReducedMotion(): boolean {
  if (typeof window === 'undefined') return false;
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}

export function AskSurface() {
  const { messages, asking, ask, documents, uploadDocuments, selectEvidence, evidence, connection } =
    useWorkspace();
  const { notify } = useToast();

  const [question, setQuestion] = useState('');
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const handleCopy = useCallback(() => notify('Copied to clipboard'), [notify]);

  /**
   * Follow the conversation as turns arrive — but only when the reader is
   * already near the bottom. Yanking the view down while they read an earlier
   * answer is the most disruptive thing a chat surface can do.
   */
  useEffect(() => {
    const node = scrollRef.current;
    if (!node) return;
    if (node.scrollHeight - node.scrollTop - node.clientHeight > 240) return;
    node.scrollTo({ top: node.scrollHeight, behavior: prefersReducedMotion() ? 'auto' : 'smooth' });
  }, [messages.length, asking]);

  // Grow the composer with its content, up to a capped height.
  useEffect(() => {
    const node = textareaRef.current;
    if (!node) return;
    node.style.height = 'auto';
    node.style.height = `${Math.min(node.scrollHeight, 200)}px`;
  }, [question]);

  const submit = () => {
    const trimmed = question.trim();
    if (!trimmed || asking) return;
    setQuestion('');
    // Keep the caret in the composer so a follow-up needs no click.
    textareaRef.current?.focus();
    void ask(trimmed);
  };

  const addFiles = async (files: FileList | File[] | null) => {
    if (!files || Array.from(files).length === 0) return;
    setUploading(true);
    try {
      await uploadDocuments(files);
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = '';
    }
  };

  const empty = messages.length <= 1 && documents.length === 0;

  return (
    <div className="flex h-full flex-col">
      <div ref={scrollRef} className="flex-1 overflow-y-auto px-6 pb-6 pt-8 max-sm:px-4">
        <div className="mx-auto max-w-3xl">
          {empty ? (
            <EmptyState
              icon={FileText}
              title="Your library is empty"
              description="Add documents to build a local evidence index. Scanned pages and images are recognized with on-device OCR."
              action={
                <Button variant="primary" size="lg" onClick={() => fileRef.current?.click()}>
                  <Paperclip className="size-4" aria-hidden />
                  Add documents
                </Button>
              }
            />
          ) : (
            messages.map((message) => (
              <Turn
                key={message.id}
                message={message}
                activeEvidenceId={evidence?.id ?? null}
                onCitation={selectEvidence}
                onCopy={handleCopy}
              />
            ))
          )}

          {asking ? (
            <div className="mb-8 animate-slide-up">
              <p className="mb-3 text-xs font-semibold text-foreground">DuckDocs</p>
              <p className="flex items-center gap-2 text-sm text-muted-foreground">
                <span className="flex gap-1" aria-hidden>
                  <i className="size-1 animate-pulse rounded-full bg-muted-foreground [animation-delay:0ms]" />
                  <i className="size-1 animate-pulse rounded-full bg-muted-foreground [animation-delay:150ms]" />
                  <i className="size-1 animate-pulse rounded-full bg-muted-foreground [animation-delay:300ms]" />
                </span>
                Retrieving evidence
              </p>
            </div>
          ) : null}
        </div>
      </div>

      <div className="shrink-0 px-6 pb-6 max-sm:px-4">
        <div className="mx-auto max-w-3xl">
          {!empty && messages.length <= 1 ? (
            <div className="mb-3 flex flex-wrap gap-2">
              {SUGGESTIONS.map((item) => (
                <button
                  key={item}
                  onClick={() => setQuestion(item)}
                  className="h-8 rounded-full bg-card px-3.5 text-xs text-muted-foreground shadow-xs ring-1 ring-inset ring-border transition-all duration-fast ease-spring hover:text-foreground active:scale-[0.97]"
                >
                  {item}
                </button>
              ))}
            </div>
          ) : null}

          <form
            onSubmit={(event) => {
              event.preventDefault();
              submit();
            }}
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
              'rounded-2xl bg-card shadow-md ring-1 ring-inset transition-all duration-200 ease-spring',
              dragging ? 'ring-2 ring-primary' : 'ring-border focus-within:ring-border-strong',
            )}
          >
            <textarea
              ref={textareaRef}
              value={question}
              rows={1}
              aria-label="Ask a question about your library"
              placeholder={dragging ? 'Drop files to add them' : 'Ask a question about your library…'}
              onChange={(event) => setQuestion(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter' && !event.shiftKey) {
                  event.preventDefault();
                  submit();
                }
              }}
              className="block w-full resize-none bg-transparent px-4 pb-2 pt-4 text-base leading-relaxed text-foreground outline-none placeholder:text-muted-foreground/70"
            />
            <div className="flex items-center justify-between gap-3 p-2 pl-3">
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => fileRef.current?.click()}
                disabled={uploading || connection === 'offline'}
              >
                <Paperclip className="size-3.5" aria-hidden />
                {uploading ? 'Adding…' : 'Attach'}
              </Button>
              <input
                ref={fileRef}
                type="file"
                multiple
                accept={ACCEPT}
                className="sr-only"
                onChange={(event) => void addFiles(event.target.files)}
              />
              <Button
                type="submit"
                variant="primary"
                size="sm"
                className="size-9 rounded-full p-0"
                disabled={!question.trim() || asking}
                aria-label="Send"
              >
                <ArrowUp className="size-4" strokeWidth={2.4} />
              </Button>
            </div>
          </form>

          <p className="mt-3 flex items-center justify-center gap-1.5 text-2xs text-muted-foreground">
            <LockKeyhole className="size-3" aria-hidden />
            {connection === 'ready'
              ? 'Answers cite retrieved passages only. Nothing leaves this machine.'
              : 'Local API offline — start the backend to ask questions.'}
          </p>
        </div>
      </div>
    </div>
  );
}

/** Memoized: a long thread would otherwise re-render on every keystroke. */
const Turn = memo(function Turn({
  message,
  activeEvidenceId,
  onCitation,
  onCopy,
}: {
  message: MessageRecord;
  activeEvidenceId: string | null;
  onCitation: (evidence: EvidenceRecord) => void;
  onCopy: () => void;
}) {
  if (message.role === 'user') {
    return (
      <article className="mb-8 flex animate-slide-up justify-end">
        <div className="max-w-[80%] rounded-2xl rounded-br-md bg-primary px-4 py-2.5 text-base leading-relaxed text-primary-foreground shadow-xs">
          {message.content}
        </div>
      </article>
    );
  }

  const refused = message.state === 'insufficient_evidence';
  const errored = message.state === 'error';

  return (
    <article className="group mb-8 animate-slide-up">
      <div className="mb-3 flex items-center gap-2">
        <span className="text-xs font-semibold text-foreground">DuckDocs</span>
        {message.timestamp ? (
          <span className="font-mono text-2xs tabular-nums text-muted-foreground/70">{message.timestamp}</span>
        ) : null}
      </div>

      {refused || errored ? (
        <div className="flex gap-3 rounded-xl bg-warning-muted p-4">
          <AlertTriangle className="mt-0.5 size-4 shrink-0 text-warning" aria-hidden />
          <div>
            <p className="text-sm font-semibold text-foreground">
              {errored ? 'Could not reach the API' : 'Not enough evidence'}
            </p>
            <p className="mt-1 text-sm leading-relaxed text-muted-foreground">{message.content}</p>
          </div>
        </div>
      ) : (
        <div className="text-base leading-[1.7] text-foreground">{message.content}</div>
      )}

      {message.citations && message.citations.length > 0 ? (
        <CitationList citations={message.citations} activeId={activeEvidenceId} onSelect={onCitation} />
      ) : null}

      {!errored ? (
        <div className="mt-3 flex items-center gap-1 opacity-0 transition-opacity duration-200 group-hover:opacity-100 group-focus-within:opacity-100">
          <Button
            variant="ghost"
            size="sm"
            className="h-7 gap-1.5 px-2 text-2xs"
            onClick={() => {
              void navigator.clipboard?.writeText(message.content);
              onCopy();
            }}
          >
            <Copy className="size-3" aria-hidden />
            Copy
          </Button>
          {message.provider ? (
            <span className="font-mono text-2xs text-muted-foreground/70">{message.provider}</span>
          ) : null}
        </div>
      ) : null}
    </article>
  );
});
