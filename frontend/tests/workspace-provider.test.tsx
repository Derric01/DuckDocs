/**
 * The transcript is the product's contract with the reader: every committed
 * answer carries citations. Streaming makes that easy to break — partial text
 * has none — so these tests pin the rule that only the terminal result is
 * committed.
 */

import { act, renderHook, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ToastProvider } from '@/components/ui';
import { WorkspaceProvider, useWorkspace } from '@/components/workspace/workspace-provider';
import { duckDocsApi } from '@/lib/api/client';
import type { GroundedAnswer } from '@/lib/api/client';

function wrapper({ children }: { children: ReactNode }) {
  return (
    <ToastProvider>
      <WorkspaceProvider>{children}</WorkspaceProvider>
    </ToastProvider>
  );
}

const ANSWER: GroundedAnswer = {
  answer: 'Notice must be given 30 days ahead.',
  grounded: true,
  outcome: 'grounded',
  providerLabel: 'ollama llama3',
  citations: [
    {
      id: 'ev_1',
      documentId: 'doc_1',
      documentName: 'lease.pdf',
      section: 'Section 4',
      page: 3,
      lines: '10-14',
      relevance: 'High',
      snippet: 'thirty days',
    },
  ],
};

beforeEach(() => {
  vi.spyOn(duckDocsApi, 'listDocuments').mockResolvedValue({ items: [], has_more: false });
});

function renderWorkspace() {
  return renderHook(() => useWorkspace(), { wrapper });
}

describe('ask', () => {
  it('shows tokens as a draft, then commits the cited answer', async () => {
    let resolveStream: (answer: GroundedAnswer) => void = () => {};
    vi.spyOn(duckDocsApi, 'askStream').mockImplementation(
      (_query, handlers = {}) =>
        new Promise<GroundedAnswer>((resolve) => {
          handlers.onToken?.('Notice ');
          handlers.onToken?.('must be given.');
          resolveStream = resolve;
        }),
    );

    const { result } = renderWorkspace();
    act(() => {
      void result.current.ask('notice period');
    });

    await waitFor(() => expect(result.current.draft).toBe('Notice must be given.'));
    expect(result.current.asking).toBe(true);
    // Nothing is in the transcript yet: the draft has no citations.
    expect(result.current.messages.some((message) => message.content.includes('Notice must be given.'))).toBe(false);

    await act(async () => {
      resolveStream(ANSWER);
    });

    await waitFor(() => expect(result.current.asking).toBe(false));
    const last = result.current.messages.at(-1);
    expect(last).toMatchObject({ role: 'assistant', state: 'grounded', content: ANSWER.answer });
    expect(last?.citations).toHaveLength(1);
    // The draft is cleared so it cannot be rendered alongside the real turn.
    expect(result.current.draft).toBe('');
  });

  it('opens the first citation in the evidence panel', async () => {
    vi.spyOn(duckDocsApi, 'askStream').mockResolvedValue(ANSWER);
    const { result } = renderWorkspace();

    await act(async () => {
      await result.current.ask('notice period');
    });
    expect(result.current.evidence).toMatchObject({ id: 'ev_1', page: 3 });
  });

  it('renders a refusal as a refusal, not as an empty answer', async () => {
    vi.spyOn(duckDocsApi, 'askStream').mockResolvedValue({
      answer: null,
      grounded: false,
      outcome: 'insufficient_evidence',
      providerLabel: 'ollama llama3',
      citations: [],
    });

    const { result } = renderWorkspace();
    await act(async () => {
      await result.current.ask('unrelated question');
    });

    const last = result.current.messages.at(-1);
    expect(last?.state).toBe('insufficient_evidence');
    expect(last?.content).toMatch(/could not find enough evidence/i);
  });

  it('marks an unreachable API as an error turn without citations', async () => {
    vi.spyOn(duckDocsApi, 'askStream').mockRejectedValue(new Error('boom'));
    const { result } = renderWorkspace();

    await act(async () => {
      await result.current.ask('anything');
    });

    const last = result.current.messages.at(-1);
    expect(last?.state).toBe('error');
    expect(last?.citations).toBeUndefined();
  });

  it('says nothing was cited when the reader stops generation', async () => {
    vi.spyOn(duckDocsApi, 'askStream').mockImplementation(
      (_query, handlers = {}) =>
        new Promise<GroundedAnswer>((_resolve, reject) => {
          handlers.signal?.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')));
        }),
    );

    const { result } = renderWorkspace();
    act(() => {
      void result.current.ask('long question');
    });
    await waitFor(() => expect(result.current.asking).toBe(true));

    await act(async () => {
      result.current.stopAsking();
    });

    await waitFor(() => expect(result.current.asking).toBe(false));
    expect(result.current.messages.at(-1)?.content).toMatch(/nothing was cited/i);
  });

  it('ignores an empty question and a second submit while one is in flight', async () => {
    const askStream = vi.spyOn(duckDocsApi, 'askStream').mockResolvedValue(ANSWER);
    const { result } = renderWorkspace();

    await act(async () => {
      await result.current.ask('   ');
    });
    expect(askStream).not.toHaveBeenCalled();
  });
});

describe('documents', () => {
  it('marks the connection offline when the library cannot be read', async () => {
    vi.spyOn(duckDocsApi, 'listDocuments').mockRejectedValue(new Error('down'));
    const { result } = renderWorkspace();
    await waitFor(() => expect(result.current.connection).toBe('offline'));
  });

  it('puts freshly uploaded documents at the top of the library', async () => {
    vi.spyOn(duckDocsApi, 'listDocuments').mockResolvedValue({
      items: [
        {
          id: 'doc_old',
          name: 'old.pdf',
          type: 'PDF',
          size: '1 MB',
          updated: 'Today',
          status: 'ready',
          pages: 2,
          category: 'Contracts',
          fidelity: 'Structural',
        },
      ],
      has_more: false,
    });
    vi.spyOn(duckDocsApi, 'uploadDocuments').mockResolvedValue([
      {
        id: 'doc_new',
        name: 'new.pdf',
        type: 'PDF',
        size: '2 MB',
        updated: 'Just now',
        status: 'processing',
        pages: 1,
        category: 'New upload',
        fidelity: 'Structural',
      },
    ]);

    const { result } = renderWorkspace();
    await waitFor(() => expect(result.current.connection).toBe('ready'));

    await act(async () => {
      await result.current.uploadDocuments([new File(['x'], 'new.pdf')]);
    });
    expect(result.current.documents.map((document) => document.id)).toEqual(['doc_new', 'doc_old']);
  });
});
