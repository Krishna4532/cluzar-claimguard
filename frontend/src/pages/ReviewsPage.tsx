import React, { FormEvent, useState } from 'react';
import { ArrowUpRight, CheckCircle2, UserRoundCheck } from 'lucide-react';
import { EmptyState, formatDate, Notice, PageHeading } from '@/components/AppUI';
import { verificationService } from '@/services/api';
import type { HumanReviewResponse, VerificationReview } from '@/types';

export const ReviewsPage: React.FC = () => {
  const [idInput, setIdInput] = useState('');
  const [verificationId, setVerificationId] = useState<number | null>(null);
  const [context, setContext] = useState<VerificationReview | null>(null);
  const [selectedClaimId, setSelectedClaimId] = useState('');
  const [notes, setNotes] = useState('');
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [savedReview, setSavedReview] = useState<HumanReviewResponse | null>(null);

  const loadContext = async (event: FormEvent) => {
    event.preventDefault();
    setError('');
    setSavedReview(null);
    const parsedId = Number(idInput);
    if (!Number.isInteger(parsedId) || parsedId <= 0) {
      setError('Enter a positive verification ID.');
      return;
    }

    setLoading(true);
    try {
      const result = await verificationService.getReviewContext(parsedId);
      setContext(result);
      setVerificationId(parsedId);
      const eligible = result.claims.find((claim) => claim.eligible_for_review && !claim.human_decision);
      setSelectedClaimId(eligible ? String(eligible.claim_id) : '');
    } catch (requestError) {
      setContext(null);
      setVerificationId(null);
      setError(requestError instanceof Error ? requestError.message : 'Could not load review context.');
    } finally {
      setLoading(false);
    }
  };

  const submitReview = async (decision: 'approved' | 'rejected') => {
    if (verificationId === null || !selectedClaimId) {
      setError('Choose an eligible claim before submitting a review.');
      return;
    }
    setSubmitting(true);
    setError('');
    setSavedReview(null);
    try {
      const result = await verificationService.submitReview(verificationId, {
        decision,
        claim_id: Number(selectedClaimId),
        notes: notes.trim() || undefined,
      });
      setSavedReview(result);
      setNotes('');
      try {
        const refreshed = await verificationService.getReviewContext(verificationId);
        setContext(refreshed);
      } catch (refreshError) {
        setError(
          `Review was saved, but the updated context could not be reloaded: ${
            refreshError instanceof Error ? refreshError.message : 'Unknown refresh error.'
          }`
        );
      }
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Review submission failed.');
    } finally {
      setSubmitting(false);
    }
  };

  const selectedClaim = context?.claims.find((claim) => String(claim.claim_id) === selectedClaimId);

  return (
    <div>
      <PageHeading
        eyebrow="Persistent human review tracking"
        title="Review a flagged claim."
        description="Load an existing verification’s context, inspect the returned evidence, and submit a decision to the backend when the claim is eligible."
      />
      <Notice>
        The API does not expose a review queue or verification-history list. Enter a known verification ID. Review records are persisted separately from automated verdicts; this is not described as an immutable audit ledger.
      </Notice>
      <section className="app-form-card review-lookup">
        <h2>Load verification context</h2>
        <form className="app-form" onSubmit={loadContext}>
          <label htmlFor="verification-id">Verification ID</label>
          <div className="form-inline">
            <input id="verification-id" inputMode="numeric" value={idInput} onChange={(event) => setIdInput(event.target.value)} placeholder="Enter verification ID" required />
            <button className="button button-dark" type="submit" disabled={loading}>{loading ? 'Loading…' : 'Load context'} <ArrowUpRight aria-hidden="true" /></button>
          </div>
        </form>
      </section>

      {error && <Notice tone="error">{error}</Notice>}
      {savedReview && (
        <Notice tone="success">
          <CheckCircle2 aria-hidden="true" /> Review saved by the backend (record {savedReview.review_id}, {savedReview.human_decision}, {formatDate(savedReview.created_at)}).
        </Notice>
      )}

      {context && (
        <div className="review-context">
          <div className="review-context-heading">
            <div>
              <p className="eyebrow"><span /> Draft {context.draft_id} · {context.business_id}</p>
              <h2>Review context</h2>
              <p>{context.pending_review_count} pending eligible claims · draft status: {context.draft_status}</p>
            </div>
            <span className="review-context-icon"><UserRoundCheck aria-hidden="true" /></span>
          </div>
          <section className="app-detail-card submitted-draft">
            <h3>Original draft</h3>
            <p>{context.draft_content}</p>
          </section>

          {context.claims.length === 0 ? (
            <EmptyState title="No claims in this review context" detail="The backend returned no claim records for this verification." />
          ) : (
            <div className="review-claim-list">
              {context.claims.map((claim) => (
                <article className="review-claim-card" key={claim.claim_id}>
                  <div className="review-claim-head">
                    <span className={`verdict-pill verdict-${claim.verdict}`}>{claim.verdict.replace('_', ' ')}</span>
                    <span>Claim {claim.claim_id} · {claim.claim_type}</span>
                    {claim.human_decision && <span className="reviewed-badge">Reviewed: {claim.human_decision}</span>}
                  </div>
                  <blockquote>{claim.claim_text}</blockquote>
                  <p>{claim.rationale}</p>
                  {claim.confidence !== null && <small className="field-hint">Backend confidence: {(claim.confidence * 100).toFixed(0)}%</small>}
                  {claim.evidence.length > 0 && (
                    <div className="review-evidence-list">
                      {claim.evidence.map((evidence) => (
                        <blockquote key={evidence.evidence_id}>
                          {evidence.evidence_text}
                          {evidence.relevance_score !== null && <small>Backend relevance score: {evidence.relevance_score.toFixed(4)}</small>}
                        </blockquote>
                      ))}
                    </div>
                  )}
                  {claim.reviewer_notes && <div className="existing-review-notes"><strong>Latest reviewer notes</strong><p>{claim.reviewer_notes}</p>{claim.reviewed_at && <small>{formatDate(claim.reviewed_at)}</small>}</div>}
                  {claim.eligible_for_review && !claim.human_decision && (
                    <label className="review-select">
                      <input type="radio" name="review-claim" value={claim.claim_id} checked={selectedClaimId === String(claim.claim_id)} onChange={() => setSelectedClaimId(String(claim.claim_id))} />
                      Select this claim for review
                    </label>
                  )}
                </article>
              ))}
            </div>
          )}

          {context.pending_review_count > 0 && (
            <section className="app-form-card review-submit-card">
              <h3>Submit a human decision</h3>
              <p>Decisions apply to one eligible claim. The backend rejects mismatched claim and verification IDs and duplicate submissions.</p>
              <label htmlFor="review-notes">Reviewer notes <span>(optional, up to 2,000 characters)</span></label>
              <textarea id="review-notes" rows={4} maxLength={2000} value={notes} onChange={(event) => setNotes(event.target.value)} placeholder="Add context for this decision." />
              <div className="review-actions">
                <button className="button button-dark" type="button" disabled={submitting || !selectedClaim || !selectedClaim.eligible_for_review || Boolean(selectedClaim.human_decision)} onClick={() => submitReview('approved')}>
                  {submitting ? 'Saving…' : 'Approve claim'}
                </button>
                <button className="button button-outline" type="button" disabled={submitting || !selectedClaim || !selectedClaim.eligible_for_review || Boolean(selectedClaim.human_decision)} onClick={() => submitReview('rejected')}>
                  Reject claim
                </button>
              </div>
              {selectedClaim && <small className="field-hint">Selected claim {selectedClaim.claim_id}; the backend verifies this claim belongs to verification {verificationId}.</small>}
            </section>
          )}
        </div>
      )}
    </div>
  );
};
