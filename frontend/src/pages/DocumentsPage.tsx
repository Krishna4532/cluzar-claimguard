import React, { FormEvent, useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { ArrowUpRight, FileText, RefreshCw, UploadCloud } from 'lucide-react';
import { EmptyState, formatDate, LoadingState, Notice, PageHeading } from '@/components/AppUI';
import { useWorkspace } from '@/context/WorkspaceContext';
import { documentService } from '@/services/api';
import type { BusinessDocumentsResponse, DocumentMetadata } from '@/types';

type ChunkState = { count: number; allEmbedded: boolean } | { error: string };

export const DocumentsPage: React.FC = () => {
  const { businessId } = useWorkspace();
  const [documents, setDocuments] = useState<BusinessDocumentsResponse | null>(null);
  const [chunks, setChunks] = useState<Record<string, ChunkState>>({});
  const [loadError, setLoadError] = useState('');
  const [busy, setBusy] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);
  const [title, setTitle] = useState('');
  const [documentType, setDocumentType] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [uploadError, setUploadError] = useState('');
  const [uploadMessage, setUploadMessage] = useState('');
  const [uploading, setUploading] = useState(false);
  const [processingId, setProcessingId] = useState('');
  const [processMessage, setProcessMessage] = useState('');

  useEffect(() => {
    if (!businessId) {
      setDocuments(null);
      setChunks({});
      return;
    }

    const controller = new AbortController();
    setBusy(true);
    setLoadError('');
    documentService.list(businessId, controller.signal)
      .then(async (result) => {
        setDocuments(result);
        const chunkEntries = await Promise.all(result.items.map(async (doc) => {
          try {
            const chunkResult = await documentService.getChunks(doc.document_id, controller.signal);
            return [doc.document_id, {
              count: chunkResult.total_chunks,
              allEmbedded: chunkResult.total_chunks > 0 && chunkResult.items.every((chunk) => chunk.has_embedding),
            }] as const;
          } catch (requestError) {
            if (controller.signal.aborted) return null;
            return [doc.document_id, {
              error: requestError instanceof Error ? requestError.message : 'Could not inspect processing status.',
            }] as const;
          }
        }));
        if (!controller.signal.aborted) {
          setChunks(Object.fromEntries(chunkEntries.filter((entry) => entry !== null)));
        }
      })
      .catch((requestError: unknown) => {
        if (!controller.signal.aborted) {
          setDocuments(null);
          setLoadError(requestError instanceof Error ? requestError.message : 'Could not load documents.');
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setBusy(false);
      });

    return () => controller.abort();
  }, [businessId, refreshKey]);

  const upload = async (event: FormEvent) => {
    event.preventDefault();
    setUploadError('');
    setUploadMessage('');
    if (!businessId) {
      setUploadError('Select a valid business context before uploading.');
      return;
    }
    if (!file) {
      setUploadError('Choose a PDF or TXT file.');
      return;
    }
    const extension = file.name.split('.').pop()?.toLowerCase();
    if (extension !== 'pdf' && extension !== 'txt') {
      setUploadError('Only PDF and TXT files are accepted.');
      return;
    }
    if (file.size > 10 * 1024 * 1024) {
      setUploadError('The selected file exceeds the backend limit of 10 MB.');
      return;
    }
    if (!title.trim() || !documentType.trim()) {
      setUploadError('Enter both a title and document category.');
      return;
    }

    setUploading(true);
    try {
      const result = await documentService.upload({
        businessId,
        documentType: documentType.trim(),
        title: title.trim(),
        file,
      });
      setUploadMessage(
        `Uploaded and ingested “${result.title}” (${result.extracted_character_count.toLocaleString()} extracted characters). Processing is a separate step.`
      );
      setTitle('');
      setDocumentType('');
      setFile(null);
      const fileInput = document.getElementById('document-file') as HTMLInputElement | null;
      if (fileInput) fileInput.value = '';
      setRefreshKey((key) => key + 1);
    } catch (requestError) {
      setUploadError(requestError instanceof Error ? requestError.message : 'Document upload failed.');
    } finally {
      setUploading(false);
    }
  };

  const processDocument = async (doc: DocumentMetadata) => {
    setProcessingId(doc.document_id);
    setProcessMessage('');
    setLoadError('');
    try {
      const result = await documentService.process(doc.document_id);
      setProcessMessage(
        `${doc.title}: ${result.processing_status} · ${result.chunk_count} chunks · ${result.embedding_count} embeddings.`
      );
      setRefreshKey((key) => key + 1);
    } catch (requestError) {
      setLoadError(requestError instanceof Error ? requestError.message : 'Document processing failed.');
    } finally {
      setProcessingId('');
    }
  };

  return (
    <div>
      <PageHeading
        eyebrow="Source library"
        title="Documents behind each claim."
        description="Upload approved business source material, inspect its metadata, and run the backend’s chunking and embedding operation."
        action={<button type="button" className="button button-outline" onClick={() => setRefreshKey((key) => key + 1)} disabled={!businessId || busy}><RefreshCw aria-hidden="true" /> Refresh</button>}
      />

      {!businessId && (
        <Notice>Select and validate a business context before viewing or uploading documents.</Notice>
      )}
      {uploadError && <Notice tone="error">{uploadError}</Notice>}
      {uploadMessage && <Notice tone="success">{uploadMessage}</Notice>}
      {processMessage && <Notice tone="success">{processMessage}</Notice>}

      <section className="app-form-card upload-card">
        <div className="form-card-icon"><UploadCloud aria-hidden="true" /></div>
        <h2>Upload source document</h2>
        <p>Backend accepts PDF and TXT files up to 10 MB. Uploading ingests the file; processing must be triggered separately.</p>
        <form className="app-form" onSubmit={upload}>
          <div className="form-grid">
            <div>
              <label htmlFor="document-title">Document title</label>
              <input id="document-title" value={title} onChange={(event) => setTitle(event.target.value)} placeholder="e.g. Product specifications" required />
            </div>
            <div>
              <label htmlFor="document-type">Document category</label>
              <input id="document-type" value={documentType} onChange={(event) => setDocumentType(event.target.value)} placeholder="e.g. product_catalog, pricing, policy" required />
            </div>
          </div>
          <div>
            <label htmlFor="document-file">PDF or TXT file</label>
            <input id="document-file" type="file" accept=".pdf,.txt,application/pdf,text/plain" onChange={(event) => setFile(event.target.files?.[0] ?? null)} required />
            {file && <small className="field-hint">{file.name} · {(file.size / (1024 * 1024)).toFixed(2)} MB</small>}
          </div>
          <button type="submit" className="button button-dark" disabled={!businessId || uploading}>
            {uploading ? 'Uploading and ingesting…' : 'Upload document'} <ArrowUpRight aria-hidden="true" />
          </button>
        </form>
      </section>

      <section className="documents-section">
        <div className="app-section-title">
          <div><h2>Workspace documents</h2><p>{businessId ? `Source records returned for ${businessId}.` : 'No business selected.'}</p></div>
          {documents && <span className="count-pill">{documents.total} total</span>}
        </div>
        {loadError && <Notice tone="error">{loadError}</Notice>}
        {busy && <LoadingState label="Loading document records…" />}
        {!busy && businessId && documents?.items.length === 0 && (
          <EmptyState title="No documents returned" detail="Upload an approved PDF or TXT source above to get started." />
        )}
        {!busy && documents && documents.items.length > 0 && (
          <div className="document-list">
            {documents.items.map((doc) => (
              <DocumentRow
                key={doc.document_id}
                document={doc}
                chunkState={chunks[doc.document_id]}
                processing={processingId === doc.document_id}
                onProcess={() => processDocument(doc)}
              />
            ))}
          </div>
        )}
      </section>
    </div>
  );
};

const DocumentRow: React.FC<{
  document: DocumentMetadata;
  chunkState?: ChunkState;
  processing: boolean;
  onProcess: () => void;
}> = ({ document: doc, chunkState, processing, onProcess }) => {
  const processed = chunkState && !('error' in chunkState) && chunkState.count > 0 && chunkState.allEmbedded;
  const unprocessed = chunkState && !('error' in chunkState) && chunkState.count === 0;
  return (
    <article className="document-row">
      <span className="document-icon"><FileText aria-hidden="true" /></span>
      <div className="document-main">
        <Link to={`/app/documents/${encodeURIComponent(doc.document_id)}`} className="document-title">{doc.title}<ArrowUpRight aria-hidden="true" /></Link>
        <span className="document-meta">{doc.document_type} · {doc.file_type.toUpperCase()} · v{doc.version} · {formatDate(doc.created_at)}</span>
        <span className="document-meta">{doc.extracted_character_count.toLocaleString()} extracted characters · backend status: {doc.status}</span>
        {chunkState && 'error' in chunkState && <span className="document-status status-unknown">Processing status unavailable</span>}
        {processed && <span className="document-status status-ready">Processed · {chunkState.count} chunks with embeddings</span>}
        {unprocessed && <span className="document-status status-pending">Ingested · processing not run</span>}
        {chunkState && !('error' in chunkState) && chunkState.count > 0 && !chunkState.allEmbedded && (
          <span className="document-status status-unknown">{chunkState.count} chunks · not all have embeddings</span>
        )}
      </div>
      <div className="document-actions">
        {unprocessed && <button className="button button-outline button-small" type="button" onClick={onProcess} disabled={processing}>{processing ? 'Processing…' : 'Process document'}</button>}
        <Link className="document-detail-link" to={`/app/documents/${encodeURIComponent(doc.document_id)}`}>Details <ArrowUpRight aria-hidden="true" /></Link>
      </div>
    </article>
  );
};

export const DocumentDetailPage: React.FC = () => {
  const { documentId = '' } = useParams();
  const [document, setDocument] = useState<DocumentMetadata | null>(null);
  const [chunks, setChunks] = useState<Awaited<ReturnType<typeof documentService.getChunks>> | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError('');
    Promise.all([
      documentService.get(documentId, controller.signal),
      documentService.getChunks(documentId, controller.signal),
    ])
      .then(([metadata, chunkList]) => {
        setDocument(metadata);
        setChunks(chunkList);
      })
      .catch((requestError: unknown) => {
        if (!controller.signal.aborted) setError(requestError instanceof Error ? requestError.message : 'Could not load document details.');
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [documentId]);

  return (
    <div>
      <PageHeading
        eyebrow="Document details"
        title={document?.title ?? 'Document record'}
        description="Metadata and processing information returned by the document endpoints."
      />
      {loading && <LoadingState label="Loading document details…" />}
      {error && <Notice tone="error">{error}</Notice>}
      {document && (
        <section className="app-detail-card">
          <div className="detail-grid">
            <Detail label="Document ID" value={document.document_id} />
            <Detail label="Business ID" value={document.business_id} />
            <Detail label="Category" value={document.document_type} />
            <Detail label="File type" value={document.file_type.toUpperCase()} />
            <Detail label="Backend status" value={document.status} />
            <Detail label="Version" value={String(document.version)} />
            <Detail label="Extracted characters" value={document.extracted_character_count.toLocaleString()} />
            <Detail label="Pages" value={String(document.page_count)} />
            <Detail label="Created" value={formatDate(document.created_at)} />
            <Detail label="SHA-256" value={document.file_hash} />
          </div>
        </section>
      )}
      {chunks && (
        <section className="documents-section">
          <div className="app-section-title">
            <div><h2>Indexed chunks</h2><p>Chunk text is not exposed by this endpoint.</p></div>
            <span className="count-pill">{chunks.total_chunks} chunks</span>
          </div>
          {chunks.items.length === 0 ? (
            <EmptyState title="No chunks reported" detail="This document has not been processed into chunks yet." />
          ) : (
            <div className="chunk-list">
              {chunks.items.map((chunk) => (
                <div className="chunk-row" key={chunk.chunk_id}>
                  <strong>Chunk {chunk.chunk_index + 1}</strong>
                  <span>{chunk.char_count} characters · offsets {chunk.start_char}–{chunk.end_char}</span>
                  <span className={`document-status ${chunk.has_embedding ? 'status-ready' : 'status-pending'}`}>
                    {chunk.has_embedding ? 'Embedding available' : 'No embedding reported'}
                  </span>
                </div>
              ))}
            </div>
          )}
        </section>
      )}
    </div>
  );
};

const Detail: React.FC<{ label: string; value: string }> = ({ label, value }) => (
  <div className="detail-field"><span>{label}</span><strong>{value}</strong></div>
);
