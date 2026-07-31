export type Surface = 'library' | 'intelligence' | 'review' | 'settings';
export type DocumentStatus = 'ready' | 'processing' | 'review' | 'failed';

export type FidelityLabel = 'Full layout' | 'Structural' | 'OCR dependent' | 'Best effort';
export type AnchorQuality = 'line' | 'paragraph' | 'bbox' | 'cell';
export type Relevance = 'High' | 'Medium' | 'Low';

/** Normalized page-relative box: [x, y, width, height], top-left origin. */
export type BBox = [number, number, number, number];

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
  /** 0-100 ingest progress; present only while status is 'processing'. */
  progress?: number;
  stage?: string;
}

export interface EvidenceRecord {
  id: string;
  documentId?: string;
  documentName: string;
  section: string;
  page: number;
  lines: string;
  relevance: Relevance;
  snippet: string;
  fidelity?: FidelityLabel;
  anchorQuality?: AnchorQuality;
  /** 0-1 OCR confidence. Present only for OCR chunks; never hidden when low. */
  ocrConfidence?: number | null;
  /** Which engine recognized this chunk, when OCR produced it. */
  ocrEngine?: string | null;
  bbox?: BBox | null;
}

export interface MessageRecord {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  citations?: EvidenceRecord[];
  timestamp: string;
  state?: 'grounded' | 'insufficient_evidence' | 'error';
  provider?: string;
}
