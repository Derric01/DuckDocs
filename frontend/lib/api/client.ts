import type { AnchorQuality, DocumentRecord, EvidenceRecord, FidelityLabel } from '@/lib/types';

export interface ApiErrorShape {
  error: {
    code: string;
    message: string;
    suggested_action?: string | null;
    retryable: boolean;
    correlation_id?: string | null;
    details?: Record<string, unknown>;
  };
}

export class ApiError extends Error {
  readonly code: string;
  readonly retryable: boolean;
  readonly correlationId: string | null;

  constructor(shape: ApiErrorShape, public readonly status: number) {
    super(shape.error.message);
    this.name = 'ApiError';
    this.code = shape.error.code;
    this.retryable = shape.error.retryable;
    this.correlationId = shape.error.correlation_id ?? null;
  }
}

/** Prefer same-origin proxy (`/api/v1`) so browser calls never fight CORS. */
const apiBaseUrl = process.env.NEXT_PUBLIC_DUCKDOCS_API_URL ?? '/api/v1';

interface ApiDocument {
  id: string;
  name: string;
  file_type: string;
  mime_type: string;
  size_bytes: number;
  status: DocumentRecord['status'];
  fidelity_tier: 'full_layout' | 'structural' | 'ocr_dependent' | 'best_effort';
  pages: number;
  category: string;
  updated_at: string;
}

interface ApiEvidence {
  id: string;
  document_id: string;
  document_name: string;
  section: string;
  page: number;
  line_start: number;
  line_end: number;
  snippet: string;
  retrieval_score: number;
  relevance: EvidenceRecord['relevance'];
  anchor_quality: AnchorQuality;
  fidelity_tier: ApiDocument['fidelity_tier'];
  ocr_confidence: number | null;
}

interface ApiUploadResponse {
  items: Array<{ document: ApiDocument; ingest_job_id: string }>;
}

interface ApiGroundedResponse {
  id: string;
  outcome: 'grounded' | 'insufficient_evidence';
  answer: string | null;
  grounded: boolean;
  citations: Array<{ id: string; ordinal: number; evidence_unit_id: string; snippet: string }>;
  provider: { name: string; model: string };
  refusal_reason?: string | null;
}

export interface GroundedAnswer {
  answer: string | null;
  grounded: boolean;
  outcome: ApiGroundedResponse['outcome'];
  citations: EvidenceRecord[];
  providerLabel: string;
  refusalReason?: string | null;
}

function formatBytes(bytes: number): string {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatUpdated(value: string): string {
  const updated = new Date(value);
  if (Number.isNaN(updated.getTime())) return 'Recently';
  const diffMs = Date.now() - updated.getTime();
  const minute = 60 * 1000;
  const hour = 60 * minute;
  const day = 24 * hour;
  if (diffMs < minute) return 'Just now';
  if (diffMs < hour) return `${Math.max(1, Math.round(diffMs / minute))} min ago`;
  if (diffMs < day) return `Today, ${updated.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`;
  if (diffMs < day * 2) return `Yesterday, ${updated.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`;
  return updated.toLocaleDateString([], { month: 'short', day: 'numeric' });
}

function mapFidelity(value: ApiDocument['fidelity_tier']): FidelityLabel {
  if (value === 'full_layout') return 'Full layout';
  if (value === 'ocr_dependent') return 'OCR dependent';
  if (value === 'best_effort') return 'Best effort';
  return 'Structural';
}

function mapDocument(document: ApiDocument): DocumentRecord {
  return {
    id: document.id,
    name: document.name,
    type: document.file_type.toUpperCase(),
    size: formatBytes(document.size_bytes),
    updated: formatUpdated(document.updated_at),
    status: document.status,
    pages: document.pages,
    category: document.category,
    fidelity: mapFidelity(document.fidelity_tier),
  };
}

function mapEvidence(evidence: ApiEvidence): EvidenceRecord {
  return {
    id: evidence.id,
    documentId: evidence.document_id,
    documentName: evidence.document_name,
    section: evidence.section,
    page: evidence.page,
    lines: `${evidence.line_start}-${evidence.line_end}`,
    relevance: evidence.relevance,
    snippet: evidence.snippet,
    fidelity: mapFidelity(evidence.fidelity_tier),
    anchorQuality: evidence.anchor_quality,
    ocrConfidence: evidence.ocr_confidence,
  };
}

export interface ProviderConfigRecord {
  id: string;
  role: 'chat' | 'embedding';
  providerType: string;
  modelName: string;
  baseUrl: string | null;
  isDefault: boolean;
  connected: boolean;
  local: boolean;
}

interface ApiProviderConfig {
  id: string;
  role: 'chat' | 'embedding';
  provider_type: string;
  model_name: string;
  base_url: string | null;
  is_default: boolean;
  connected: boolean;
  local: boolean;
}

function mapProviderConfig(config: ApiProviderConfig): ProviderConfigRecord {
  return {
    id: config.id,
    role: config.role,
    providerType: config.provider_type,
    modelName: config.model_name,
    baseUrl: config.base_url,
    isDefault: config.is_default,
    connected: config.connected,
    local: config.local,
  };
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${apiBaseUrl}${path}`, {
      ...init,
      headers: { Accept: 'application/json', ...init?.headers },
    });
  } catch (error) {
    throw new ApiError(
      {
        error: {
          code: 'NETWORK_ERROR',
          message: error instanceof Error ? error.message : 'DuckDocs API is not reachable.',
          suggested_action: 'Confirm the backend is running, then retry.',
          retryable: true,
        },
      },
      0,
    );
  }
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as ApiErrorShape | { detail?: unknown } | null;
    if (body && typeof body === 'object' && 'error' in body && body.error && typeof body.error.message === 'string') {
      throw new ApiError(body as ApiErrorShape, response.status);
    }
    const detail =
      body && typeof body === 'object' && 'detail' in body
        ? typeof body.detail === 'string'
          ? body.detail
          : JSON.stringify(body.detail)
        : `Request failed with status ${response.status}`;
    throw new ApiError(
      {
        error: {
          code: 'HTTP_ERROR',
          message: detail,
          suggested_action: 'Retry the request or check Settings for the active model.',
          retryable: response.status >= 500,
        },
      },
      response.status,
    );
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

export const duckDocsApi = {
  listDocuments: async () => {
    const response = await request<{ items: ApiDocument[]; has_more: boolean }>('/documents');
    return { ...response, items: response.items.map(mapDocument) };
  },
  getEvidence: async (id: string) => mapEvidence(await request<ApiEvidence>(`/evidence/${id}`)),
  search: async (query: string) => {
    const response = await request<{ results: Array<{ evidence: ApiEvidence; score: number }> }>('/search', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query, scope: { type: 'library' } }),
    });
    return { results: response.results.map((item) => ({ ...item, evidence: mapEvidence(item.evidence) })) };
  },
  uploadDocuments: async (files: FileList | File[]) => {
    const formData = new FormData();
    Array.from(files).forEach((file) => formData.append('files', file));
    const response = await request<ApiUploadResponse>('/documents', { method: 'POST', body: formData });
    return response.items.map((item) => mapDocument(item.document));
  },
  ask: async (query: string): Promise<GroundedAnswer> => {
    const response = await request<ApiGroundedResponse>('/ask', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query, scope: { type: 'library' } }),
    });
    const citations = await Promise.all(
      response.citations.map(async (citation) => {
        try {
          return await duckDocsApi.getEvidence(citation.evidence_unit_id);
        } catch {
          return {
            id: citation.evidence_unit_id,
            documentName: 'Retrieved evidence',
            section: `Citation ${citation.ordinal}`,
            page: 1,
            lines: '1-1',
            relevance: 'Medium' as const,
            snippet: citation.snippet,
          };
        }
      }),
    );
    return {
      answer: response.answer,
      grounded: response.grounded,
      outcome: response.outcome,
      citations,
      providerLabel: `${response.provider.name} ${response.provider.model}`.trim(),
      refusalReason: response.refusal_reason,
    };
  },
  listProviderConfigs: async () => {
    const response = await request<ApiProviderConfig[]>('/settings/providers');
    return response.map(mapProviderConfig);
  },
  createProviderConfig: async (payload: {
    role: 'chat' | 'embedding';
    providerType: string;
    modelName: string;
    baseUrl?: string | null;
    apiKey?: string | null;
    isDefault?: boolean;
  }) => {
    const response = await request<ApiProviderConfig>('/settings/providers', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        role: payload.role,
        provider_type: payload.providerType,
        model_name: payload.modelName,
        base_url: payload.baseUrl ?? null,
        api_key: payload.apiKey ?? null,
        is_default: payload.isDefault ?? false,
      }),
    });
    return mapProviderConfig(response);
  },
  testProviderConfig: async (id: string) =>
    request<{ reachable: boolean; latency_ms: number | null; error: string | null }>(`/settings/providers/${id}/test`, {
      method: 'POST',
    }),
};
