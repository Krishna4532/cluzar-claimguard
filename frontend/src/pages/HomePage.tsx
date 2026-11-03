import React, { useEffect, useRef, useState } from 'react';
import {
  ArrowDown,
  ArrowRight,
  ArrowUpRight,
  CheckCircle2,
  FileCheck2,
  FileText,
  Languages,
  Layers,
  LockKeyhole,
  Search,
  ShieldCheck,
  SlidersHorizontal,
  UploadCloud,
  UserRoundCheck,
} from 'lucide-react';

export const HomePage: React.FC = () => {
  const [docsOpen, setDocsOpen] = useState(false);
  const docsDialogRef = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const dialog = docsDialogRef.current;
    if (!dialog) return;

    if (docsOpen && !dialog.open) dialog.showModal();
    else if (!docsOpen && dialog.open) dialog.close();
  }, [docsOpen]);

  return (
    <div className="home-page">
      <section className="hero-section" aria-labelledby="hero-title">
        <div className="hero-copy">
          <p className="eyebrow"><span /> Claim verification · Made for careful review</p>
          <h1 id="hero-title">
            Keep every claim
            <br />
            close to its <em>evidence.</em>
          </h1>
          <p className="hero-lede">
            Review marketing drafts against your approved product documentation.
            Cluzar-ClaimGuard connects each claim to evidence and routes uncertain
            cases for human review.
          </p>
          <div className="hero-actions">
            <a className="button button-dark" href="#workflow">
              Explore the workflow <ArrowUpRight aria-hidden="true" />
            </a>
            <button className="text-link" type="button" onClick={() => setDocsOpen(true)}>
              Open Docs <ArrowRight aria-hidden="true" />
            </button>
          </div>
          <div className="hero-capabilities" aria-label="Supported capabilities">
            <span><Languages aria-hidden="true" /> English · Hindi · Hinglish</span>
            <span><Search aria-hidden="true" /> Dense + BM25 retrieval</span>
            <span><UserRoundCheck aria-hidden="true" /> Human review</span>
          </div>
        </div>

        <div className="hero-art" aria-label="Claim verification workflow illustration">
          <div className="art-orbit art-orbit-one" />
          <div className="art-orbit art-orbit-two" />
          <div className="flow-panel">
            <div className="flow-panel-head">
              <span className="panel-mark"><ShieldCheck aria-hidden="true" /></span>
              <div>
                <span className="panel-kicker">CLUZAR-CLAIMGUARD</span>
                <strong>Evidence workflow</strong>
              </div>
              <span className="panel-menu" aria-hidden="true">···</span>
            </div>
            <div className="flow-step">
              <span className="flow-step-icon"><UploadCloud aria-hidden="true" /></span>
              <span className="flow-step-copy">
                <strong>Approved source documents</strong>
                <small>Product facts · pricing · policies</small>
              </span>
            </div>
            <div className="flow-connector" />
            <div className="flow-step">
              <span className="flow-step-icon step-mint"><FileText aria-hidden="true" /></span>
              <span className="flow-step-copy">
                <strong>Marketing draft</strong>
                <small>Claims identified for review</small>
              </span>
              <ArrowDown aria-hidden="true" className="flow-arrow" />
            </div>
            <div className="flow-connector" />
            <div className="flow-step">
              <span className="flow-step-icon step-saffron"><Search aria-hidden="true" /></span>
              <span className="flow-step-copy">
                <strong>Evidence-led review</strong>
                <small>Sources surfaced for each claim</small>
              </span>
              <ArrowRight aria-hidden="true" className="flow-arrow" />
            </div>
            <div className="flow-panel-foot">
              <span><LockKeyhole aria-hidden="true" /> Workspace-filtered sources</span>
              <span className="flow-language">EN · हिं · HINGLISH</span>
            </div>
          </div>
          <div className="art-note">
            <span className="note-spark">✳</span>
            <span><strong>Evidence first</strong><small>Clear sources. Careful decisions.</small></span>
          </div>
        </div>
      </section>

      <div className="capability-ribbon" aria-label="Product capabilities">
        <span>DOCUMENT INGESTION</span><i />
        <span>HYBRID RETRIEVAL</span><i />
        <span>DETERMINISTIC CHECKS</span><i />
        <span>HUMAN REVIEW</span>
      </div>

      <section id="workspace-overview" className="workflow-section section-wrap">
        <div className="section-heading">
          <div>
            <p className="eyebrow"><span /> How the workspace works</p>
            <h2>From draft to source,<br />with <em>care at every step.</em></h2>
          </div>
          <p>
            A reviewable path from your approved business facts to the claims in
            a marketing draft—without hiding where evidence comes from.
          </p>
        </div>

        <div id="workflow" className="workflow-grid">
          <article className="workflow-card">
            <span className="card-index">01 <UploadCloud aria-hidden="true" /></span>
            <h3>Bring in trusted documents.</h3>
            <p>
              Upload approved product specifications, FAQs, and price lists in
              PDF or TXT format. Text is normalized, chunked, and indexed for
              retrieval.
            </p>
            <span className="card-detail">PDF / TXT · 500-character chunks · 75 overlap</span>
          </article>
          <article className="workflow-card">
            <span className="card-index">02 <Search aria-hidden="true" /></span>
            <h3>Find relevant evidence.</h3>
            <p>
              Claims are extracted from submitted drafts, then matched with
              workspace-filtered source passages using dense and lexical search.
            </p>
            <span className="card-detail">pgvector cosine search + BM25</span>
          </article>
          <article className="workflow-card">
            <span className="card-index">03 <FileCheck2 aria-hidden="true" /></span>
            <h3>Review with context.</h3>
            <p>
              Deterministic rules check exact details; semantic verification
              handles meaning. Unclear cases can be sent to a human reviewer.
            </p>
            <span className="card-detail">Evidence stays tied to each claim</span>
          </article>
        </div>

        <div className="api-card">
          <div className="api-copy">
            <p className="eyebrow eyebrow-light"><span /> Connect to your workflow</p>
            <h3>Use the verification API.</h3>
            <p>Explore the documented endpoints for uploads, checks, and reviews.</p>
          </div>
          <button className="button button-light" type="button" onClick={() => setDocsOpen(true)}>
            Open Docs <ArrowUpRight aria-hidden="true" />
          </button>
        </div>
      </section>

      <section id="features" className="engine-section">
        <div className="section-wrap engine-inner">
          <div className="section-heading">
            <div>
              <p className="eyebrow"><span /> Inside the evidence engine</p>
              <h2>Grounded checks.<br /><em>Not guesswork.</em></h2>
            </div>
            <p>
              Retrieval and verification work together to distinguish exact
              factual checks from claims that need more context.
            </p>
          </div>
          <div className="engine-grid">
            <article className="engine-card">
              <div className="engine-icon"><SlidersHorizontal aria-hidden="true" /></div>
              <h3>Hybrid retrieval</h3>
              <p>
                Dense vector search and BM25 keyword matching are combined with
                reciprocal-rank fusion to find relevant source passages.
              </p>
              <div className="engine-tags"><span>Dense</span><span>BM25</span><span>RRF · k=60</span></div>
            </article>
            <article className="engine-card">
              <div className="engine-icon icon-mint"><CheckCircle2 aria-hidden="true" /></div>
              <h3>Deterministic checks</h3>
              <p>
                Code-based rules compare exact values such as prices,
                percentages, and dates against retrieved evidence.
              </p>
              <div className="engine-tags"><span>Prices</span><span>Percentages</span><span>Dates</span></div>
            </article>
            <article className="engine-card">
              <div className="engine-icon icon-saffron"><ShieldCheck aria-hidden="true" /></div>
              <h3>Fail-closed safety</h3>
              <p>
                Missing evidence is not treated as support. Ambiguous or
                invalid cases can be routed for human review.
              </p>
              <div className="engine-tags"><span>Evidence-aware</span><span>Reviewable</span></div>
            </article>
          </div>
        </div>
      </section>

      <section id="human-review" className="review-section section-wrap">
        <div className="review-copy">
          <p className="eyebrow"><span /> A person stays in the loop</p>
          <h2>Keep human judgment<br />part of the <em>process.</em></h2>
          <p>
            Claims that need attention can be resolved by an operator. Reviewer
            decisions are stored separately, leaving the original automated
            verdict and rationale available for reference.
          </p>
          <ul className="review-points">
            <li><CheckCircle2 aria-hidden="true" /> Eligible claims can receive reviewer decisions.</li>
            <li><CheckCircle2 aria-hidden="true" /> Automated verdicts remain distinct from review actions.</li>
            <li><CheckCircle2 aria-hidden="true" /> Reviewer notes preserve decision context.</li>
          </ul>
        </div>
        <div className="review-visual">
          <div className="review-card">
            <div className="review-card-top"><span>REVIEW RECORDS</span><UserRoundCheck aria-hidden="true" /></div>
            <div className="record-row">
              <span className="record-icon"><Layers aria-hidden="true" /></span>
              <span><strong>Automated verification</strong><small>Original verdict and rationale</small></span>
              <ArrowRight aria-hidden="true" />
            </div>
            <div className="record-divider" />
            <div className="record-row">
              <span className="record-icon record-icon-mint"><CheckCircle2 aria-hidden="true" /></span>
              <span><strong>Human review</strong><small>Separate reviewer decision and notes</small></span>
              <ArrowRight aria-hidden="true" />
            </div>
            <div className="review-card-foot"><LockKeyhole aria-hidden="true" /> Decisions remain separately recorded</div>
          </div>
          <div className="review-stamp"><span>REVIEW</span><strong>with context</strong></div>
        </div>
      </section>

      <section className="closing-section section-wrap">
        <div className="closing-card">
          <div>
            <p className="eyebrow eyebrow-light"><span /> Cluzar-ClaimGuard</p>
            <h2>Give every claim<br />a clearer <em>source.</em></h2>
            <p>Explore the API docs to start connecting approved documentation to draft checks.</p>
          </div>
          <div className="closing-actions">
            <button className="button button-light" type="button" onClick={() => setDocsOpen(true)}>
              Open Docs <ArrowUpRight aria-hidden="true" />
            </button>
            <button className="closing-link" type="button" onClick={() => setDocsOpen(true)}>
              Documentation details <ArrowRight aria-hidden="true" />
            </button>
          </div>
        </div>
      </section>

      <dialog
        ref={docsDialogRef}
        className="docs-dialog"
        aria-labelledby="docs-dialog-title"
        onClose={() => setDocsOpen(false)}
        onCancel={(event) => {
          event.preventDefault();
          setDocsOpen(false);
        }}
        onKeyDown={(event) => {
          if (event.key === 'Escape') {
            event.preventDefault();
            setDocsOpen(false);
          }
        }}
        onClick={(event) => {
          if (event.target === docsDialogRef.current) setDocsOpen(false);
        }}
      >
        <div className="docs-dialog-content">
          <span className="docs-dialog-icon"><FileText aria-hidden="true" /></span>
          <p className="eyebrow"><span /> Cluzar-ClaimGuard</p>
          <h2 id="docs-dialog-title">Documentation Coming Soon</h2>
          <p>
            We're working on comprehensive ClaimGuard documentation to help you understand the platform, its features, and verification workflows. Stay tuned!
          </p>
          <button
            className="button button-dark"
            type="button"
            autoFocus
            onClick={() => setDocsOpen(false)}
          >
            Got it
          </button>
        </div>
      </dialog>
    </div>
  );
};
