import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { RootLayout } from '@/layouts/RootLayout';
import { AppLayout } from '@/layouts/AppLayout';
import { HomePage } from '@/pages/HomePage';
import { NotFoundPage } from '@/pages/NotFoundPage';
import { AppOverviewPage } from '@/pages/AppOverviewPage';
import { WorkspacesPage } from '@/pages/WorkspacesPage';
import { DocumentsPage, DocumentDetailPage } from '@/pages/DocumentsPage';
import { VerificationPage, VerificationResultPage } from '@/pages/VerificationPage';
import { ReviewsPage } from '@/pages/ReviewsPage';
import { WorkspaceProvider } from '@/context/WorkspaceContext';

export const App: React.FC = () => {
  return (
    <WorkspaceProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<RootLayout />}>
            <Route index element={<HomePage />} />
            <Route path="*" element={<NotFoundPage />} />
          </Route>
          <Route path="/app" element={<AppLayout />}>
            <Route index element={<AppOverviewPage />} />
            <Route path="workspaces" element={<WorkspacesPage />} />
            <Route path="documents" element={<DocumentsPage />} />
            <Route path="documents/:documentId" element={<DocumentDetailPage />} />
            <Route path="verification" element={<VerificationPage />} />
            <Route path="verification/result" element={<VerificationResultPage />} />
            <Route path="reviews" element={<ReviewsPage />} />
            <Route path="*" element={<NotFoundPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </WorkspaceProvider>
  );
};

export default App;
