export type ClaimVerdict = 'supported' | 'contradicted' | 'unsupported' | 'needs_human';
export type OverallVerificationStatus = 'approved' | 'rejected' | 'flagged';

export interface VerificationEvidence {
  chunk_id: number | null;
  document_id: string | null;
  document_title: string | null;
  source_text: string;
  relevance_score: number | null;
}

export interface ClaimVerificationResult {
  text: string;
  type: string;
  start_char: number;
  end_char: number;
  verdict: ClaimVerdict;
  explanation: string;
  confidence: number;
  evidence: VerificationEvidence[];
}

export interface VerificationCheckRequest {
  business_id: string;
  draft_text: string;
}

export interface VerificationCheckResponse {
  draft_id: number;
  business_id: string;
  overall_status: OverallVerificationStatus;
  total_claims: number;
  supported_count: number;
  contradicted_count: number;
  unsupported_count: number;
  needs_human_count: number;
  claims: ClaimVerificationResult[];
}

export interface DocumentMetadata {
  document_id: string;
  business_id: string;
  title: string;
  document_type: string;
  file_type: string;
  file_hash: string;
  version: number;
  status: string;
  extracted_character_count: number;
  page_count: number;
  created_at: string;
}

export interface DocumentUploadResponse extends Omit<DocumentMetadata, 'page_count'> {}

export interface BusinessDocumentsResponse {
  items: DocumentMetadata[];
  total: number;
}

export interface DocumentChunk {
  chunk_id: number;
  chunk_index: number;
  char_count: number;
  start_char: number;
  end_char: number;
  has_embedding: boolean;
  metadata: Record<string, unknown>;
}

export interface DocumentChunksResponse {
  document_id: string;
  total_chunks: number;
  items: DocumentChunk[];
}

export interface ProcessingResponse {
  document_id: string;
  business_id: string;
  processing_status: string;
  chunk_count: number;
  embedding_count: number;
  embedding_model: string;
  embedding_dimension: number;
  processing_duration_ms: number;
}

export interface ReviewEvidence {
  evidence_id: number;
  chunk_id: number | null;
  evidence_text: string;
  relevance_score: number | null;
}

export interface ClaimItem {
  claim_id: number;
  claim_text: string;
  claim_type: string;
  start_char: number;
  end_char: number;
  verdict: ClaimVerdict;
  rationale: string;
  confidence: number | null;
  evidence: ReviewEvidence[];
  eligible_for_review: boolean;
  human_decision: 'approved' | 'rejected' | null;
  reviewer_notes: string | null;
  reviewed_at: string | null;
}

export interface VerificationReview {
  verification_id: number;
  draft_id: number;
  business_id: string;
  draft_content: string;
  draft_status: string;
  total_claims: number;
  pending_review_count: number;
  claims: ClaimItem[];
}

export interface HumanReviewResponse {
  review_id: number;
  verification_id: number;
  claim_id: number;
  claim_text: string;
  automated_verdict: string;
  human_decision: string;
  notes: string | null;
  created_at: string;
}
