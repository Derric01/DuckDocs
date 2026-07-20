export type Surface = 'library' | 'intelligence' | 'review' | 'settings';
export type DocumentStatus = 'ready' | 'processing' | 'review' | 'failed';

export interface DocumentRecord {
  id: string;
  name: string;
  type: string;
  size: string;
  updated: string;
  status: DocumentStatus;
  pages: number;
  category: string;
  fidelity: 'Full layout' | 'Structural' | 'OCR dependent';
}

export interface EvidenceRecord {
  id: string;
  documentId?: string;
  documentName: string;
  section: string;
  page: number;
  lines: string;
  relevance: 'High' | 'Medium' | 'Low';
  snippet: string;
}

export interface MessageRecord {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  citations?: EvidenceRecord[];
  timestamp: string;
  state?: 'grounded' | 'insufficient_evidence' | 'error' | 'thinking';
}
