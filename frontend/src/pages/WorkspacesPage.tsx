import React, { FormEvent, useState } from 'react';
import { ArrowUpRight, BriefcaseBusiness, CheckCircle2 } from 'lucide-react';
import { Notice, PageHeading } from '@/components/AppUI';
import { useWorkspace } from '@/context/WorkspaceContext';
import { workspaceService } from '@/services/api';
import type { BusinessDocumentsResponse } from '@/types';

export const WorkspacesPage: React.FC = () => {
  const { businessId, setBusinessId } = useWorkspace();
  const [input, setInput] = useState(businessId);
  const [documents, setDocuments] = useState<BusinessDocumentsResponse | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [success, setSuccess] = useState('');

  const selectBusiness = async (event: FormEvent) => {
    event.preventDefault();
    const candidate = input.trim();
    if (!candidate) {
      setError('Enter a business ID to validate it against the backend.');
      return;
    }

    setBusy(true);
    setError('');
    setSuccess('');
    try {
      const result = await workspaceService.validateBusiness(candidate);
      setBusinessId(candidate);
      setDocuments(result);
      setSuccess(`Business context selected. The API returned ${result.total} document${result.total === 1 ? '' : 's'}.`);
    } catch (requestError) {
      setDocuments(null);
      setError(requestError instanceof Error ? requestError.message : 'Could not validate this business ID.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <PageHeading
        eyebrow="Workspace management"
        title="Choose a business context."
        description="The backend accepts business IDs for document and verification requests. This selection only chooses that existing context; it does not create a workspace."
      />

      <section className="app-form-card">
        <div className="form-card-icon"><BriefcaseBusiness aria-hidden="true" /></div>
        <h2>Select an existing business</h2>
        <p>Enter the business ID configured on your backend. The documents endpoint validates that it exists.</p>
        <form className="app-form" onSubmit={selectBusiness}>
          <label htmlFor="business-id">Business ID</label>
          <div className="form-inline">
            <input
              id="business-id"
              name="business-id"
              value={input}
              onChange={(event) => setInput(event.target.value)}
              placeholder="Business ID"
              autoComplete="off"
              required
            />
            <button type="submit" className="button button-dark" disabled={busy}>
              {busy ? 'Validating…' : 'Select business'} <ArrowUpRight aria-hidden="true" />
            </button>
          </div>
        </form>
        {error && <Notice tone="error">{error}</Notice>}
        {success && <Notice tone="success"><CheckCircle2 aria-hidden="true" /> {success}</Notice>}
        {businessId && (
          <div className="selected-business">
            <span className="workspace-dot" />
            <span><small>ACTIVE BUSINESS CONTEXT</small><strong>{businessId}</strong></span>
            {documents && <span className="selected-document-count">{documents.total} documents</span>}
          </div>
        )}
      </section>

      <div className="app-limitations">
        <strong>Workspace creation and directory are not available</strong>
        <p>
          The backend has no business list, create, edit, or delete endpoints. The frontend
          therefore validates an entered business ID using the real documents endpoint and
          does not simulate workspace management.
        </p>
      </div>
    </div>
  );
};
