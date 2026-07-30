export type Surface = 'library' | 'intelligence' | 'review' | 'settings';
export type DocumentStatus = 'ready' | 'processing' | 'review' | 'failed';

export type FidelityLabel = 'Full layout' | 'Structural' | 'OCR dependent' | 'Best effort';
export type AnchorQuality = 'line' | 'paragraph' | 'bbox' | 'cell';

export interface DocumentRecord {
  id: string;
  name: string;
  type: string;
  size: string;
  updated: string;
  status: DocumentStatus;
  pages: number;
  category: string;
  fidelity: FidelityLabel;
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
  /** Chunk-level fidelity; a document's overall tier can be pulled down by any low-quality chunk. */
  fidelity?: FidelityLabel;
  anchorQuality?: AnchorQuality;
  /** 0-1 OCR confidence. Present only when this chunk came from OCR -- never hidden when low (RULE-10). */
  ocrConfidence?: number | null;
}

export interface MessageRecord {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  citations?: EvidenceRecord[];
  timestamp: string;
  state?: 'grounded' | 'insufficient_evidence' | 'error' | 'thinking';
}
