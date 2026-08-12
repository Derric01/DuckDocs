/**
 * The API boundary: snake_case wire shapes mapped to the UI's records, and the
 * SSE stream that carries a grounded answer. A mapping slip here is invisible
 * in typecheck (both sides are strings) but shows up as a blank field.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError, duckDocsApi, parseSseFrame } from '@/lib/api/client';
import { at } from './helpers';

const fetchMock = vi.fn();

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal('fetch', fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

function jsonResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
    body: null,
  } as unknown as Response;
}

/** A Response whose body streams the given SSE text in one chunk per frame. */
function sseResponse(frames: string[]): Response {
  const encoder = new TextEncoder();
  let index = 0;
  return {
    ok: true,
    status: 200,
    body: {
      getReader: () => ({
        read: async () =>
          index < frames.length
            ? { done: false, value: encoder.encode(frames[index++]) }
            : { done: true, value: undefined },
        releaseLock: () => {},
      }),
    },
  } as unknown as Response;
}

const GROUNDED = {
  id: 'ans_1',
  outcome: 'grounded',
  answer: 'Notice must be given 30 days ahead.',
  grounded: true,
  citations: [{ id: 'c1', ordinal: 1, evidence_unit_id: 'ev_1', snippet: 'thirty days' }],
  provider: { name: 'ollama', model: 'llama3' },
};

const EVIDENCE = {
  id: 'ev_1',
  document_id: 'doc_1',
  document_name: 'lease.pdf',
  section: 'Section 4',
  page: 3,
  line_start: 10,
  line_end: 14,
  snippet: 'thirty days',
  retrieval_score: 0.8,
  relevance: 'High',
  anchor_quality: 'bbox',
  fidelity_tier: 'ocr_dependent',
  ocr_confidence: 0.42,
  ocr_engine: 'rapidocr',
  bbox: [0.1, 0.2, 0.3, 0.05],
};

describe('parseSseFrame', () => {
  it('reads the event name and JSON payload', () => {
    expect(parseSseFrame('event: token\ndata: {"text":"hi"}')).toEqual({ event: 'token', data: { text: 'hi' } });
  });

  it('defaults to the "message" event when none is named', () => {
    expect(parseSseFrame('data: {"a":1}')?.event).toBe('message');
  });

  it('joins multi-line data as the spec requires', () => {
    expect(parseSseFrame('event: done\ndata: {"a":\ndata: 1}')?.data).toEqual({ a: 1 });
  });

  it('returns null for a frame with no data or invalid JSON', () => {
    expect(parseSseFrame('event: ping')).toBeNull();
    expect(parseSseFrame('data: not json')).toBeNull();
  });
});

describe('mapping', () => {
  it('carries OCR provenance through to the evidence record', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(EVIDENCE));
    const record = await duckDocsApi.getEvidence('ev_1');

    expect(record).toMatchObject({
      documentName: 'lease.pdf',
      lines: '10-14',
      fidelity: 'OCR dependent',
      anchorQuality: 'bbox',
      ocrConfidence: 0.42,
      ocrEngine: 'rapidocr',
      bbox: [0.1, 0.2, 0.3, 0.05],
    });
  });

  it('labels each fidelity tier with its human name', async () => {
    for (const [tier, label] of [
      ['full_layout', 'Full layout'],
      ['structural', 'Structural'],
      ['ocr_dependent', 'OCR dependent'],
      ['best_effort', 'Best effort'],
    ] as const) {
      fetchMock.mockResolvedValueOnce(jsonResponse({ ...EVIDENCE, fidelity_tier: tier }));
      expect((await duckDocsApi.getEvidence('ev_1')).fidelity).toBe(label);
    }
  });

  it('keeps the summary and how it was produced', async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({
        items: [
          {
            id: 'doc_1',
            name: 'lease.pdf',
            file_type: 'pdf',
            mime_type: 'application/pdf',
            size_bytes: 2_400_000,
            status: 'ready',
            fidelity_tier: 'structural',
            pages: 12,
            category: 'Contracts',
            updated_at: new Date().toISOString(),
            summary: 'A commercial lease with a 30-day notice clause.',
            summary_method: 'extractive',
            summary_provider: null,
          },
        ],
        has_more: false,
      }),
    );

    const [document] = (await duckDocsApi.listDocuments()).items;
    expect(document).toMatchObject({
      type: 'PDF',
      size: '2.3 MB',
      summaryMethod: 'extractive',
      summary: 'A commercial lease with a 30-day notice clause.',
    });
  });

  it('raises a typed error carrying the backend envelope', async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse(
        { error: { code: 'not_found', message: 'Evidence was not found.', retryable: false } },
        404,
      ),
    );
    await expect(duckDocsApi.getEvidence('nope')).rejects.toMatchObject({
      name: 'ApiError',
      code: 'not_found',
      status: 404,
      retryable: false,
    });
  });

  it('reports an unreachable API as retryable rather than throwing raw', async () => {
    fetchMock.mockRejectedValueOnce(new TypeError('Failed to fetch'));
    const error = await duckDocsApi.getEvidence('ev_1').catch((caught: unknown) => caught);
    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).retryable).toBe(true);
  });
});

describe('askStream', () => {
  it('emits tokens as they arrive and resolves from the terminal event', async () => {
    fetchMock
      .mockResolvedValueOnce(
        sseResponse([
          'event: token\ndata: {"index":0,"text":"Notice "}\n\n',
          'event: token\ndata: {"index":1,"text":"is required."}\n\n',
          `event: done\ndata: ${JSON.stringify(GROUNDED)}\n\n`,
        ]),
      )
      .mockResolvedValueOnce(jsonResponse(EVIDENCE));

    const tokens: string[] = [];
    const answer = await duckDocsApi.askStream('notice period', { onToken: (token) => tokens.push(token) });

    expect(tokens).toEqual(['Notice ', 'is required.']);
    expect(answer.outcome).toBe('grounded');
    expect(answer.providerLabel).toBe('ollama llama3');
    expect(answer.citations[0]).toMatchObject({ documentName: 'lease.pdf', page: 3 });
  });

  it('reassembles frames split across chunk boundaries', async () => {
    fetchMock
      .mockResolvedValueOnce(
        sseResponse([
          'event: token\ndata: {"index":0,"te',
          'xt":"split"}\n\nevent: done\ndata: ',
          `${JSON.stringify(GROUNDED)}\n\n`,
        ]),
      )
      .mockResolvedValueOnce(jsonResponse(EVIDENCE));

    const tokens: string[] = [];
    await duckDocsApi.askStream('q', { onToken: (token) => tokens.push(token) });
    expect(tokens).toEqual(['split']);
  });

  it('falls back to the blocking call when the stream never sends "done"', async () => {
    fetchMock
      .mockResolvedValueOnce(sseResponse(['event: token\ndata: {"index":0,"text":"partial"}\n\n']))
      .mockResolvedValueOnce(jsonResponse(GROUNDED))
      .mockResolvedValueOnce(jsonResponse(EVIDENCE));

    const answer = await duckDocsApi.askStream('q');
    expect(answer.answer).toBe('Notice must be given 30 days ahead.');
    expect(at(at(fetchMock.mock.calls, 1), 0)).toContain('/ask');
  });

  it('falls back when the streaming endpoint is unavailable', async () => {
    fetchMock
      .mockResolvedValueOnce(jsonResponse({ detail: 'nope' }, 404))
      .mockResolvedValueOnce(jsonResponse({ ...GROUNDED, citations: [] }))
      .mockResolvedValue(jsonResponse(EVIDENCE));

    expect((await duckDocsApi.askStream('q')).grounded).toBe(true);
  });

  it('keeps a refusal as a refusal rather than dressing it as an answer', async () => {
    const refusal = {
      ...GROUNDED,
      outcome: 'insufficient_evidence',
      answer: null,
      grounded: false,
      citations: [],
      refusal_reason: 'No passage met the grounding threshold.',
    };
    fetchMock.mockResolvedValueOnce(sseResponse([`event: done\ndata: ${JSON.stringify(refusal)}\n\n`]));

    const answer = await duckDocsApi.askStream('q');
    expect(answer.outcome).toBe('insufficient_evidence');
    expect(answer.answer).toBeNull();
    expect(answer.refusalReason).toBe('No passage met the grounding threshold.');
  });

  it('keeps a citation whose evidence lookup fails instead of dropping it', async () => {
    fetchMock
      .mockResolvedValueOnce(sseResponse([`event: done\ndata: ${JSON.stringify(GROUNDED)}\n\n`]))
      .mockResolvedValueOnce(jsonResponse({ error: { code: 'not_found', message: 'gone', retryable: false } }, 404));

    const answer = await duckDocsApi.askStream('q');
    expect(answer.citations).toHaveLength(1);
    expect(at(answer.citations, 0).snippet).toBe('thirty days');
  });

  it('propagates an abort rather than silently retrying', async () => {
    const controller = new AbortController();
    controller.abort();
    fetchMock.mockRejectedValueOnce(new DOMException('Aborted', 'AbortError'));

    await expect(duckDocsApi.askStream('q', { signal: controller.signal })).rejects.toThrow();
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});
