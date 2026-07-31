'use client';

import { AlertTriangle, ArrowUp, Copy, FileText, LockKeyhole, Paperclip } from 'lucide-react';
import { memo, useCallback, useEffect, useRef, useState } from 'react';
import { EmptyState, useToast } from '@/components/ui';
import { CitationList } from '@/components/workspace/citations';
import { useWorkspace } from '@/components/workspace/workspace-provider';
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

  // Stable identity so memoized turns don't re-render on every keystroke.
  const handleCopy = useCallback(() => notify('Copied to clipboard'), [notify]);

  const [question, setQuestion] = useState('');
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  /**
   * Follow the conversation as turns arrive — but only when the user is
   * already near the bottom. Yanking the view down while they are reading an
   * earlier answer is the single most disruptive thing a chat surface can do.
   */
  useEffect(() => {
    const node = scrollRef.current;
    if (!node) return;
    const distanceFromBottom = node.scrollHeight - node.scrollTop - node.clientHeight;
    if (distanceFromBottom > 240) return;
    node.scrollTo({ top: node.scrollHeight, behavior: prefersReducedMotion() ? 'auto' : 'smooth' });
  }, [messages.length, asking]);

  // Grow the composer with its content, up to the CSS max-height.
  useEffect(() => {
    const node = textareaRef.current;
    if (!node) return;
    node.style.height = 'auto';
    node.style.height = `${node.scrollHeight}px`;
  }, [question]);

  const submit = () => {
    const trimmed = question.trim();
    if (!trimmed || asking) return;
    setQuestion('');
    // Keep the caret in the composer so a follow-up question needs no click.
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
    <div className="chat">
      <div className="chat-scroll" ref={scrollRef}>
        <div className="chat-thread">
          {empty ? (
            <EmptyState
              icon={FileText}
              title="Your library is empty"
              description="Add documents to build a local evidence index. Scanned pages and images are recognized with on-device OCR."
              action={
                <button className="btn btn-primary" onClick={() => fileRef.current?.click()}>
                  <Paperclip size={15} strokeWidth={1.8} aria-hidden="true" />
                  Add documents
                </button>
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
            <div className="turn">
              <div className="turn-meta">
                <span className="turn-name">DuckDocs</span>
              </div>
              <p className="thinking">
                <span className="thinking-dots" aria-hidden="true">
                  <i />
                  <i />
                  <i />
                </span>
                Retrieving evidence
              </p>
            </div>
          ) : null}
        </div>
      </div>

      <div className="composer-dock">
        <div className="composer-inner">
          {!empty && messages.length <= 1 ? (
            <div className="suggestions">
              {SUGGESTIONS.map((item) => (
                <button key={item} onClick={() => setQuestion(item)}>
                  {item}
                </button>
              ))}
            </div>
          ) : null}

          <form
            className={`composer ${dragging ? 'dragging' : ''}`}
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
            />
            <div className="composer-bar">
              <div className="composer-left">
                <button
                  type="button"
                  className="composer-scope"
                  onClick={() => fileRef.current?.click()}
                  disabled={uploading || connection === 'offline'}
                >
                  <Paperclip size={14} strokeWidth={1.8} aria-hidden="true" />
                  {uploading ? 'Adding…' : 'Attach'}
                </button>
                <input
                  ref={fileRef}
                  type="file"
                  multiple
                  accept={ACCEPT}
                  className="visually-hidden"
                  onChange={(event) => void addFiles(event.target.files)}
                />
              </div>
              <button className="send-btn" type="submit" disabled={!question.trim() || asking} aria-label="Send">
                <ArrowUp size={16} strokeWidth={2} aria-hidden="true" />
              </button>
            </div>
          </form>

          <p className="composer-note">
            <LockKeyhole size={11} strokeWidth={1.8} aria-hidden="true" />
            {connection === 'ready'
              ? 'Answers cite retrieved passages only. Nothing leaves this machine.'
              : 'Local API offline — start the backend to ask questions.'}
          </p>
        </div>
      </div>
    </div>
  );
}

/**
 * Memoized: a long thread re-renders every turn on each keystroke in the
 * composer otherwise, and citation grouping is not free.
 */
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
      <article className="turn turn-user">
        <div className="bubble">{message.content}</div>
      </article>
    );
  }

  const refused = message.state === 'insufficient_evidence';
  const errored = message.state === 'error';

  return (
    <article className="turn">
      <div className="turn-meta">
        <span className="turn-name">DuckDocs</span>
        {message.timestamp ? <span className="turn-time">{message.timestamp}</span> : null}
      </div>

      {refused || errored ? (
        <div className="refusal">
          <AlertTriangle size={15} strokeWidth={1.8} aria-hidden="true" />
          <div>
            <strong>{errored ? 'Could not reach the API' : 'Not enough evidence'}</strong>
            <p>{message.content}</p>
          </div>
        </div>
      ) : (
        <div className="answer">
          <p>{message.content}</p>
        </div>
      )}

      {message.citations && message.citations.length > 0 ? (
        <CitationList citations={message.citations} activeId={activeEvidenceId} onSelect={onCitation} />
      ) : null}

      {!errored ? (
        <div className="turn-tools">
          <button
            onClick={() => {
              void navigator.clipboard?.writeText(message.content);
              onCopy();
            }}
          >
            <Copy size={13} strokeWidth={1.8} aria-hidden="true" />
            Copy
          </button>
          {message.provider ? <span className="turn-time mono">{message.provider}</span> : null}
        </div>
      ) : null}
    </article>
  );
});
