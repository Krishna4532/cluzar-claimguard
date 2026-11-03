import { apiFetch } from '@/lib/apiClient';
import type {
  BusinessDocumentsResponse,
  DocumentChunksResponse,
  DocumentMetadata,
  DocumentUploadResponse,
  HumanReviewResponse,
  ProcessingResponse,
  VerificationCheckRequest,
  VerificationCheckResponse,
  VerificationReview,
} from '@/types';

export const workspaceService = {
  validateBusiness: (businessId: string, signal?: AbortSignal) =>
    apiFetch<BusinessDocumentsResponse>(
      `/api/businesses/${encodeURIComponent(businessId)}/documents`,
      { signal }
    ),
};

export const documentService = {
  list: (businessId: string, signal?: AbortSignal) =>
    apiFetch<BusinessDocumentsResponse>(
      `/api/businesses/${encodeURIComponent(businessId)}/documents`,
      { signal }
    ),

  get: (documentId: string, signal?: AbortSignal) =>
    apiFetch<DocumentMetadata>(`/api/documents/${encodeURIComponent(documentId)}`, { signal }),

  getChunks: (documentId: string, signal?: AbortSignal) =>
    apiFetch<DocumentChunksResponse>(
      `/api/documents/${encodeURIComponent(documentId)}/chunks`,
      { signal }
    ),

  upload: (input: {
    businessId: string;
    documentType: string;
    title: string;
    file: File;
    signal?: AbortSignal;
  }) => {
    const body = new FormData();
    body.append('business_id', input.businessId);
    body.append('document_type', input.documentType);
    body.append('title', input.title);
    body.append('file', input.file);
    return apiFetch<DocumentUploadResponse>('/api/documents/upload', {
      method: 'POST',
      body,
      signal: input.signal,
    });
  },

  process: (documentId: string, signal?: AbortSignal) =>
    apiFetch<ProcessingResponse>(
      `/api/documents/${encodeURIComponent(documentId)}/process`,
      { method: 'POST', signal }
    ),
};

export const verificationService = {
  check: (request: VerificationCheckRequest, signal?: AbortSignal) =>
    apiFetch<VerificationCheckResponse>('/api/verifications/check', {
      method: 'POST',
      body: JSON.stringify(request),
      signal,
    }),

  getReviewContext: (verificationId: number, signal?: AbortSignal) =>
    apiFetch<VerificationReview>(
      `/api/verifications/${verificationId}/review`,
      { signal }
    ),

  submitReview: (
    verificationId: number,
    data: { decision: 'approved' | 'rejected'; notes?: string; claim_id?: number },
    signal?: AbortSignal
  ) =>
    apiFetch<HumanReviewResponse>(
      `/api/verifications/${verificationId}/review`,
      {
        method: 'POST',
        body: JSON.stringify(data),
        signal,
      }
    ),

  checkHealth: (signal?: AbortSignal) =>
    apiFetch<{ status: string; environment: string; version: string }>('/health', { signal }),
};
