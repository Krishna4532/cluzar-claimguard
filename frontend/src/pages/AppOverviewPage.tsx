import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowUpRight, FileText, ShieldCheck, Workflow } from 'lucide-react';
import { PageHeading } from '@/components/AppUI';
import { useWorkspace } from '@/context/WorkspaceContext';
import { verificationService } from '@/services/api';

const modules = [
  {
    to: '/app/workspaces',
    icon: ShieldCheck,
    title: 'Choose a business context',
    detail: 'Select a business ID already configured in the backend.',
  },
  {
    to: '/app/documents',
    icon: FileText,
    title: 'Manage source documents',
    detail: 'Upload PDF or TXT documents and trigger the supported processing endpoint.',
  },
  {
    to: '/app/verification',
    icon: Workflow,
    title: 'Verify a marketing draft',
    detail: 'Submit copy and inspect claim-level verdicts with returned evidence.',
  },
];

export const AppOverviewPage: React.FC = () => {
  const { businessId } = useWorkspace();
  const [apiStatus, setApiStatus] = useState<{ status: string; version: string } | null>(null);
  const [apiError, setApiError] = useState('');
  const [checkingApi, setCheckingApi] = useState(true);

  useEffect(() => {
    const controller = new AbortController();
    const timeout = window.setTimeout(() => {
      setApiError('Health check timed out.');
      setCheckingApi(false);
      controller.abort();
    }, 4000);
    verificationService.checkHealth(controller.signal)
      .then((health) => setApiStatus({ status: health.status, version: health.version }))
      .catch((requestError: unknown) => {
        if (!controller.signal.aborted) {
          setApiError(requestError instanceof Error ? requestError.message : 'Health check failed.');
        }
      })
      .finally(() => {
        window.clearTimeout(timeout);
        if (!controller.signal.aborted) setCheckingApi(false);
      });

    return () => {
      window.clearTimeout(timeout);
      controller.abort();
    };
  }, []);

  return (
    <div>
      <PageHeading
        eyebrow="Workspace overview"
        title="A clear path from copy to evidence."
        description="Use the actual ClaimGuard APIs to work with source documents, submitted drafts, and claim evidence."
        action={<Link className="button button-dark" to="/app/verification">Check a draft <ArrowUpRight /></Link>}
      />

      <section className="overview-context">
        <span className="workspace-dot" />
        <div>
          <span className="overview-label">CURRENT BUSINESS CONTEXT</span>
          <strong>{businessId || 'No business selected'}</strong>
        </div>
        <Link to="/app/workspaces">{businessId ? 'Change context' : 'Select context'} <ArrowUpRight /></Link>
      </section>

      <section className={`api-health ${apiStatus ? 'api-health-online' : ''}`} aria-live="polite">
        <span className="workspace-dot" />
        <div>
          <strong>Backend API</strong>
          <span>
            {checkingApi ? 'Checking health endpoint…' : apiStatus
              ? `${apiStatus.status} · version ${apiStatus.version}`
              : apiError || 'Health check unavailable'}
          </span>
        </div>
        <small>GET /health</small>
      </section>

      <div className="app-section-title">
        <h2>Continue with</h2>
        <p>Each area reflects operations currently exposed by the backend.</p>
      </div>
      <div className="module-grid">
        {modules.map(({ to, icon: Icon, title, detail }) => (
          <Link className="module-card" to={to} key={to}>
            <span className="module-icon"><Icon aria-hidden="true" /></span>
            <h3>{title}</h3>
            <p>{detail}</p>
            <span className="module-link">Open area <ArrowUpRight aria-hidden="true" /></span>
          </Link>
        ))}
      </div>

      <div className="app-limitations">
        <strong>Backend capabilities vary by area</strong>
        <p>
          The current API does not expose workspace creation/listing, verification history,
          or a human-review queue. Those operations are intentionally not represented as
          available actions here.
        </p>
      </div>
    </div>
  );
};
