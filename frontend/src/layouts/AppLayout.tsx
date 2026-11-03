import React from 'react';
import { Link, NavLink, Outlet } from 'react-router-dom';
import {
  ArrowUpRight,
  FileText,
  Gauge,
  Home,
  MessageSquareText,
  ShieldCheck,
  UsersRound,
  Workflow,
} from 'lucide-react';
import { useWorkspace } from '@/context/WorkspaceContext';

const navigation = [
  { to: '/app', label: 'Overview', icon: Gauge, end: true },
  { to: '/app/workspaces', label: 'Workspaces', icon: Home },
  { to: '/app/documents', label: 'Documents', icon: FileText },
  { to: '/app/verification', label: 'Verification', icon: Workflow },
  { to: '/app/reviews', label: 'Human reviews', icon: UsersRound },
];

export const AppLayout: React.FC = () => {
  const { businessId } = useWorkspace();

  return (
    <div className="application-shell">
      <aside className="app-sidebar">
        <Link to="/" className="app-brand">
          <span className="brand-icon"><ShieldCheck aria-hidden="true" /></span>
          <span className="brand-copy">
            <span className="brand-name">Cluzar-ClaimGuard</span>
            <span className="brand-note">Independent proof of concept</span>
          </span>
        </Link>
        <div className="sidebar-label">WORKSPACE</div>
        <div className="active-workspace">
          <span className="workspace-dot" />
          <span>
            <strong>{businessId || 'No workspace selected'}</strong>
            <small>{businessId ? 'Business context' : 'Select a business ID'}</small>
          </span>
        </div>
        <nav className="app-navigation" aria-label="Workspace navigation">
          {navigation.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) => `app-nav-link${isActive ? ' active' : ''}`}
            >
              <Icon aria-hidden="true" />
              {label}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="sidebar-disclosure">
            This independent proof of concept is not affiliated with or endorsed by Cluzar or Newtonite.
          </div>
          <Link to="/" className="return-home-link">Public homepage <ArrowUpRight aria-hidden="true" /></Link>
          <Link to="/app/verification" className="sidebar-quick-link">
            <MessageSquareText aria-hidden="true" /> Check a draft
          </Link>
        </div>
      </aside>

      <div className="app-main-column">
        <header className="app-topbar">
          <div className="app-topbar-brand">
            <span className="brand-icon"><ShieldCheck aria-hidden="true" /></span>
            <strong>Cluzar-ClaimGuard</strong>
          </div>
          <Link to="/app/workspaces" className="topbar-workspace">
            <span className="workspace-dot" />
            {businessId || 'Choose a business'} <ArrowUpRight aria-hidden="true" />
          </Link>
        </header>
        <main className="app-content">
          <Outlet />
        </main>
        <footer className="app-footer">
          Independent proof of concept · Not affiliated with or endorsed by Cluzar or Newtonite
        </footer>
      </div>
    </div>
  );
};
