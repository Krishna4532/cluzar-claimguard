import React from 'react';
import { Outlet, Link } from 'react-router-dom';
import {
  ArrowUpRight,
  CheckCircle2,
  ExternalLink,
  FileText,
  Layers,
  ShieldCheck,
  Sliders,
} from 'lucide-react';

export const RootLayout: React.FC = () => {
  return (
    <div className="site-shell">
      <header className="site-header">
        <div className="site-nav-wrap">
          <Link to="/" className="site-brand" aria-label="Cluzar-ClaimGuard home">
            <span className="brand-icon" aria-hidden="true">
              <ShieldCheck />
            </span>
            <span className="brand-copy">
              <span className="brand-name">Cluzar-ClaimGuard</span>
              <span className="brand-note">Independent proof of concept</span>
            </span>
          </Link>

          <nav className="site-nav" aria-label="Main navigation">
            <a href="#workflow">Workflow</a>
            <a href="#features">Evidence engine</a>
            <a href="#human-review">Human review</a>
          </nav>

          <Link className="nav-cta" to="/app">
            Cluzar-ClaimGuard workspace <ArrowUpRight aria-hidden="true" />
          </Link>
        </div>
      </header>

      <main className="site-main">
        <Outlet />
      </main>

      <footer className="site-footer">
        <div className="footer-main">
          <div className="footer-branding">
            <Link to="/" className="site-brand" aria-label="Cluzar-ClaimGuard home">
              <span className="brand-icon" aria-hidden="true">
                <ShieldCheck />
              </span>
              <span className="brand-copy">
                <span className="brand-name">Cluzar-ClaimGuard</span>
                <span className="brand-note">Claim verification workspace</span>
              </span>
            </Link>
            <p>
              Ground marketing draft claims in approved business documentation, with
              traceable evidence and a human review path.
            </p>
            <div className="footer-tags" aria-label="Core technologies">
              <span>pgvector</span>
              <span>BM25</span>
              <span>RRF</span>
            </div>
          </div>

          <div className="footer-column">
            <h2>Verification workflow</h2>
            <ul>
              <li><FileText aria-hidden="true" /> Document ingestion</li>
              <li><Layers aria-hidden="true" /> Hybrid retrieval</li>
              <li><Sliders aria-hidden="true" /> Deterministic checks</li>
              <li><CheckCircle2 aria-hidden="true" /> Human review</li>
            </ul>
          </div>

          <div className="footer-column">
            <h2>Developer resources</h2>
            <a href="http://localhost:8000/health" target="_blank" rel="noreferrer">
              Health check <ExternalLink aria-hidden="true" />
            </a>
          </div>
        </div>

        <div className="footer-disclosure">
          <strong>Independent project disclosure</strong>
          <p>
            Cluzar-ClaimGuard is an independent proof of concept, independently
            inspired by Cluzar’s public-facing visual design and not its
            architecture or proprietary systems. It is not affiliated with,
            sponsored by, or endorsed by Cluzar or Newtonite.
          </p>
        </div>

        <div className="footer-bottom">
          <span>© {new Date().getFullYear()} Cluzar-ClaimGuard</span>
          <span>Evidence-grounded marketing claim verification</span>
        </div>
      </footer>
    </div>
  );
};
