import React from 'react';
import { AlertCircle, LoaderCircle } from 'lucide-react';

export const PageHeading: React.FC<{
  eyebrow: string;
  title: string;
  description: string;
  action?: React.ReactNode;
}> = ({ eyebrow, title, description, action }) => (
  <div className="app-page-heading">
    <div>
      <p className="eyebrow"><span /> {eyebrow}</p>
      <h1>{title}</h1>
      <p className="app-page-description">{description}</p>
    </div>
    {action && <div className="app-page-action">{action}</div>}
  </div>
);

export const Notice: React.FC<{
  children: React.ReactNode;
  tone?: 'info' | 'error' | 'success';
}> = ({ children, tone = 'info' }) => (
  <div className={`app-notice app-notice-${tone}`} role={tone === 'error' ? 'alert' : 'status'}>
    {tone === 'error' && <AlertCircle aria-hidden="true" />}
    <div>{children}</div>
  </div>
);

export const LoadingState: React.FC<{ label?: string }> = ({ label = 'Loading data…' }) => (
  <div className="app-loading" role="status">
    <LoaderCircle aria-hidden="true" />
    <span>{label}</span>
  </div>
);

export const EmptyState: React.FC<{
  title: string;
  detail: string;
  action?: React.ReactNode;
}> = ({ title, detail, action }) => (
  <div className="app-empty">
    <h2>{title}</h2>
    <p>{detail}</p>
    {action}
  </div>
);

export function formatDate(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? value
    : new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(date);
}
