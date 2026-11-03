import React, { FormEvent, useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { ArrowLeft, ArrowUpRight, FileSearch, ShieldCheck } from 'lucide-react';
import { EmptyState, Notice, PageHeading } from '@/components/AppUI';
import { useWorkspace } from '@/context/WorkspaceContext';
import { verificationService } from '@/services/api';
import type {
  ClaimVerificationResult,
  VerificationCheckResponse,
} from '@/types';

interface VerificationNavigationState {
  draftText: string;
  response: VerificationCheckResponse;
}

export const VerificationPage: React.FC = () => {
  const { businessId } = useWorkspace();
  const navigate = useNavigate();
  const [draftText, setDraftText] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setError('');
    if (!businessId) {
      setError('Select and validate a business context before submitting a draft.');
      return;
    }
    if (!draftText.trim()) {
      setError('Enter marketing copy to check.');
      return;
    }
    setSubmitting(true);
    try {
      const response = await verificationService.check({
        business_id: businessId,
        draft_text: draftText,
      });
      navigate('/app/verification/result', {
        state: { draftText, response } satisfies VerificationNavigationState,
      });
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Verification request failed.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div>
      <PageHeading
        eyebrow="Draft verification"
        title="Check copy against your sources."
        description="Submit marketing copy to the backend and inspect the returned claim verdicts, explanations, and retrieved evidence."
        action={<Link className="button button-outline" to="/app/documents"><FileSearch aria-hidden="true" /> Source documents</Link>}
      />
      {businessId ? (
        <div className="verification-context"><span className="workspace-dot" /> Business context: <strong>{businessId}</strong></div>
      ) : (
        <Notice>Select and validate a business context before verification.</Notice>
      )}
      {error && <Notice tone="error">{error}</Notice>}
      <section className="app-form-card verification-form-card">
        <div className="form-card-icon"><ShieldCheck aria-hidden="true" /></div>
        <h2>Marketing draft</h2>
        <p>Claims are extracted and checked by the real <code>POST /api/verifications/check</code> endpoint.</p>
        <form className="app-form" onSubmit={submit}>
          <label htmlFor="draft-content">Draft content</label>
          <textarea
            id="draft-content"
            value={draftText}
            onChange={(event) => setDraftText(event.target.value)}
            placeholder="Paste marketing copy to verify against the selected business's approved source documents."
            rows={9}
            required
          />
          <div className="form-submit-row">
            <span className="field-hint">No client-side verdicts or sample results are generated.</span>
            <button type="submit" className="button button-dark" disabled={submitting || !businessId}>
              {submitting ? 'Checking claims…' : 'Submit for verification'} <ArrowUpRight aria-hidden="true" />
            </button>
          </div>
        </form>
      </section>
    </div>
  );
};

export const VerificationResultPage: React.FC = () => {
  const location = useLocation();
  const state = location.state as VerificationNavigationState | null;
  if (!state?.response || !state.draftText) {
    return (
      <div>
        <PageHeading
          eyebrow="Verification result"
          title="No result to display."
          description="Results are returned by the verification API and are only held in the current page navigation."
        />
        <EmptyState
          title="Submit a draft first"
          detail="The backend does not provide a verification-history endpoint, so previous results cannot be restored after leaving this page."
          action={<Link className="button button-dark" to="/app/verification">Check a draft <ArrowUpRight aria-hidden="true" /></Link>}
        />
      </div>
    );
  }

  const { response, draftText } = state;
  return (
    <div>
      <PageHeading
        eyebrow={`Draft ${response.draft_id} · ${response.business_id}`}
        title="Verification result."
        description="This view displays the response from the backend. Retrieved passages are evidence surfaced by the system, not independently established facts."
        action={<Link className="button button-outline" to="/app/verification"><ArrowLeft aria-hidden="true" /> New check</Link>}
      />

      <div className={`overall-result overall-${response.overall_status}`}>
        <span className="overall-status">{response.overall_status}</span>
        <span>{response.total_claims} claims extracted</span>
        <div className="result-counts">
          <span>{response.supported_count} supported</span>
          <span>{response.contradicted_count} contradicted</span>
          <span>{response.unsupported_count} unsupported</span>
          <span>{response.needs_human_count} needs human review</span>
        </div>
      </div>

      <section className="app-detail-card submitted-draft">
        <h2>Submitted content</h2>
        <p>{draftText}</p>
      </section>

      <div className="app-section-title">
        <div><h2>Claim-level results</h2><p>{response.claims.length} result records returned for this draft.</p></div>
      </div>
      {response.claims.length === 0 ? (
        <EmptyState title="No claims returned" detail="The backend did not identify claim results in this draft." />
      ) : (
        <div className="claim-list">
          {response.claims.map((claim, index) => <ClaimResult key={`${claim.start_char}-${claim.end_char}-${index}`} claim={claim} index={index} />)}
        </div>
      )}
      <Notice>
        The API response does not include verification record IDs or a history/list endpoint. Human review access therefore requires a verification ID obtained through another backend-supported workflow.
      </Notice>
    </div>
  );
};

const ClaimResult: React.FC<{ claim: ClaimVerificationResult; index: number }> = ({ claim, index }) => (
  <article className="claim-result">
    <header className="claim-result-head">
      <span className="claim-number">CLAIM {String(index + 1).padStart(2, '0')} · {claim.type}</span>
      <span className={`verdict-pill verdict-${claim.verdict}`}>{claim.verdict.replace('_', ' ')}</span>
    </header>
    <blockquote>{claim.text}</blockquote>
    <p className="claim-explanation">{claim.explanation}</p>
    <div className="claim-confidence">Backend confidence: {(claim.confidence * 100).toFixed(0)}%</div>

    <div className="evidence-heading">
      <h3>Retrieved evidence</h3>
      <span>{claim.evidence.length} source passage{claim.evidence.length === 1 ? '' : 's'}</span>
    </div>
    {claim.evidence.length === 0 ? (
      <p className="no-evidence">No evidence references were returned for this claim.</p>
    ) : (
      <div className="evidence-list">
        {claim.evidence.map((evidence, evidenceIndex) => (
          <article className="evidence-item" key={`${evidence.document_id ?? 'source'}-${evidence.chunk_id ?? evidenceIndex}`}>
            <div className="evidence-source">
              <span><FileSearch aria-hidden="true" /> {evidence.document_title || 'Source passage'}</span>
              {evidence.document_id && <Link to={`/app/documents/${encodeURIComponent(evidence.document_id)}`}>Document details <ArrowUpRight aria-hidden="true" /></Link>}
            </div>
            <blockquote>{evidence.source_text}</blockquote>
            <div className="evidence-meta">
              {evidence.chunk_id !== null && <span>Chunk {evidence.chunk_id}</span>}
              {evidence.relevance_score !== null && <span>Backend relevance score: {evidence.relevance_score.toFixed(4)}</span>}
            </div>
          </article>
        ))}
      </div>
    )}
  </article>
);
