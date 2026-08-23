'use client';

/**
 * Shared workspace state.
 *
 * Every surface reads from one provider rather than a single monolithic
 * component, so routes stay independent while the document list, evidence
 * selection, and connection status remain consistent across them.
 */

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { ApiError, duckDocsApi, type ProviderConfigRecord } from '@/lib/api/client';
import type { DocumentRecord, EvidenceRecord, MessageRecord } from '@/lib/types';
import { useToast } from '@/components/ui';

export type ConnectionState = 'connecting' | 'ready' | 'offline';

interface WorkspaceValue {
  connection: ConnectionState;
  documents: DocumentRecord[];
  documentsLoading: boolean;
  refreshDocuments: () => Promise<void>;
  uploadDocuments: (files: FileList | File[]) => Promise<void>;

  evidence: EvidenceRecord | null;
  selectEvidence: (evidence: EvidenceRecord | null) => void;
  inspectDocument: (document: DocumentRecord) => Promise<void>;

  messages: MessageRecord[];
  asking: boolean;
  /** Tokens received so far for the in-flight answer; empty until the first arrives. */
  draft: string;
  ask: (question: string) => Promise<void>;
  stopAsking: () => void;

  providers: ProviderConfigRecord[];
  providersLoading: boolean;
  refreshProviders: () => Promise<void>;
}

const WorkspaceContext = createContext<WorkspaceValue | null>(null);

function timestamp(): string {
  return new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function describeError(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  return 'DuckDocs API is not reachable. Start the backend to continue.';
}

function isOfflineError(error: unknown): boolean {
  return (
    error instanceof ApiError && (error.code === 'NETWORK_ERROR' || error.status === 0 || error.status === 502)
  );
}

const WELCOME: MessageRecord = {
  id: 'welcome',
  role: 'assistant',
  timestamp: '',
  content:
    'Ask a question about your library and I will answer only from retrieved passages, with a citation for each claim. If the evidence is not there, I will say so instead of guessing.',
  state: 'grounded',
};

export function WorkspaceProvider({ children }: { children: ReactNode }) {
  const { notify } = useToast();

  const [connection, setConnection] = useState<ConnectionState>('connecting');
  const [documents, setDocuments] = useState<DocumentRecord[]>([]);
  const [documentsLoading, setDocumentsLoading] = useState(true);
  const [evidence, setEvidence] = useState<EvidenceRecord | null>(null);
  const [messages, setMessages] = useState<MessageRecord[]>([WELCOME]);
  const [asking, setAsking] = useState(false);
  const [draft, setDraft] = useState('');
  const abortRef = useRef<AbortController | null>(null);
  const [providers, setProviders] = useState<ProviderConfigRecord[]>([]);
  const [providersLoading, setProvidersLoading] = useState(false);

  const refreshDocuments = useCallback(async () => {
    try {
      const response = await duckDocsApi.listDocuments();
      setDocuments(response.items);
      setConnection('ready');
    } catch {
      setDocuments([]);
      setConnection('offline');
    } finally {
      setDocumentsLoading(false);
    }
  }, []);

  const refreshProviders = useCallback(async () => {
    setProvidersLoading(true);
    try {
      setProviders(await duckDocsApi.listProviderConfigs());
      setConnection('ready');
    } catch {
      setProviders([]);
    } finally {
      setProvidersLoading(false);
    }
  }, []);

  useEffect(() => {
    void refreshDocuments();
  }, [refreshDocuments]);

  /**
   * Poll while anything is still ingesting.
   *
   * Ingestion is asynchronous and OCR on a long scanned document can take a
   * while, so a single delayed refresh would leave rows stuck on
   * "Processing" until a manual reload. Polling stops as soon as nothing is
   * in flight, so an idle library costs no requests.
   */
  const processingCount = documents.filter((document) => document.status === 'processing').length;
  const pollRef = useRef<number | null>(null);

  useEffect(() => {
    if (processingCount === 0 || connection === 'offline') {
      if (pollRef.current) {
        window.clearInterval(pollRef.current);
        pollRef.current = null;
      }
      return;
    }
    pollRef.current = window.setInterval(() => {
      void refreshDocuments();
    }, 1500);
    return () => {
      if (pollRef.current) window.clearInterval(pollRef.current);
      pollRef.current = null;
    };
  }, [processingCount, connection, refreshDocuments]);

  const uploadDocuments = useCallback(
    async (files: FileList | File[]) => {
      const list = Array.from(files);
      if (list.length === 0) return;
      if (connection === 'offline') {
        notify('Start the DuckDocs API to add documents.', 'error');
        return;
      }
      try {
        const uploaded = await duckDocsApi.uploadDocuments(list);
        setDocuments((current) => [
          ...uploaded,
          ...current.filter((document) => !uploaded.some((item) => item.id === document.id)),
        ]);
        setConnection('ready');
        notify(
          `${uploaded.length} document${uploaded.length === 1 ? '' : 's'} added. Indexing locally.`,
          'success',
        );
      } catch (error) {
        notify(describeError(error), 'error');
        if (isOfflineError(error)) setConnection('offline');
      }
    },
    [connection, notify],
  );

  const selectEvidence = useCallback((next: EvidenceRecord | null) => {
    setEvidence(next);
  }, []);

  const inspectDocument = useCallback(
    async (document: DocumentRecord) => {
      if (connection !== 'ready') {
        notify('Start the DuckDocs API to inspect evidence.', 'error');
        return;
      }
      try {
        const response = await duckDocsApi.search(document.name);
        const first = response.results.find((result) => result.evidence.documentId === document.id)?.evidence;
        if (first) {
          setEvidence(first);
        } else {
          setEvidence(null);
          notify(`${document.name} has no indexed evidence yet.`);
        }
      } catch (error) {
        notify(describeError(error), 'error');
      }
    },
    [connection, notify],
  );

  /**
   * Answers stream, so the reader sees text forming instead of a spinner. The
   * committed turn always comes from the terminal `done` payload — a partial
   * token run has no citations, and an uncited answer must never enter the
   * transcript.
   */
  const ask = useCallback(
    async (question: string) => {
      const trimmed = question.trim();
      if (!trimmed || asking) return;

      setMessages((current) => [
        ...current,
        { id: `user_${Date.now()}`, role: 'user', timestamp: timestamp(), content: trimmed },
      ]);
      setAsking(true);
      setDraft('');
      const controller = new AbortController();
      abortRef.current = controller;

      try {
        const answer = await duckDocsApi.askStream(trimmed, {
          signal: controller.signal,
          onToken: (token) => setDraft((current) => current + token),
        });
        setConnection('ready');
        setMessages((current) => [
          ...current,
          {
            id: `assistant_${Date.now()}`,
            role: 'assistant',
            timestamp: timestamp(),
            content:
              answer.answer ??
              'I could not find enough evidence in your library to answer that. Try narrowing the question, or add a source document.',
            citations: answer.citations,
            state: answer.outcome === 'grounded' ? 'grounded' : 'insufficient_evidence',
            provider: answer.providerLabel,
          },
        ]);
        if (answer.citations[0]) setEvidence(answer.citations[0]);
      } catch (error) {
        if (controller.signal.aborted) {
          setMessages((current) => [
            ...current,
            {
              id: `assistant_${Date.now()}`,
              role: 'assistant',
              timestamp: timestamp(),
              content: 'Stopped before the answer was grounded, so nothing was cited.',
              state: 'error',
            },
          ]);
        } else {
          const message = describeError(error);
          setMessages((current) => [
            ...current,
            {
              id: `assistant_${Date.now()}`,
              role: 'assistant',
              timestamp: timestamp(),
              content: message,
              state: 'error',
            },
          ]);
          if (isOfflineError(error)) setConnection('offline');
        }
      } finally {
        abortRef.current = null;
        setDraft('');
        setAsking(false);
      }
    },
    [asking],
  );

  const stopAsking = useCallback(() => {
    abortRef.current?.abort();
  }, []);

  // A navigation mid-answer must not leave the request running.
  useEffect(() => () => abortRef.current?.abort(), []);

  const value = useMemo<WorkspaceValue>(
    () => ({
      connection,
      documents,
      documentsLoading,
      refreshDocuments,
      uploadDocuments,
      evidence,
      selectEvidence,
      inspectDocument,
      messages,
      asking,
      draft,
      ask,
      stopAsking,
      providers,
      providersLoading,
      refreshProviders,
    }),
    [
      connection,
      documents,
      documentsLoading,
      refreshDocuments,
      uploadDocuments,
      evidence,
      selectEvidence,
      inspectDocument,
      messages,
      asking,
      draft,
      ask,
      stopAsking,
      providers,
      providersLoading,
      refreshProviders,
    ],
  );

  return <WorkspaceContext.Provider value={value}>{children}</WorkspaceContext.Provider>;
}

export function useWorkspace(): WorkspaceValue {
  const context = useContext(WorkspaceContext);
  if (!context) throw new Error('useWorkspace must be used inside WorkspaceProvider');
  return context;
}
