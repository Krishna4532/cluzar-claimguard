import React, { createContext, useContext, useMemo, useState } from 'react';

const STORAGE_KEY = 'cluzar-claimguard-business-id';

interface WorkspaceContextValue {
  businessId: string;
  setBusinessId: (businessId: string) => void;
}

const WorkspaceContext = createContext<WorkspaceContextValue | null>(null);

function readStoredBusinessId(): string {
  try {
    return window.localStorage.getItem(STORAGE_KEY) ?? '';
  } catch {
    return '';
  }
}

export const WorkspaceProvider: React.FC<React.PropsWithChildren> = ({ children }) => {
  const [businessId, setBusinessIdState] = useState(readStoredBusinessId);

  const setBusinessId = (nextBusinessId: string) => {
    const normalized = nextBusinessId.trim();
    setBusinessIdState(normalized);
    try {
      if (normalized) window.localStorage.setItem(STORAGE_KEY, normalized);
      else window.localStorage.removeItem(STORAGE_KEY);
    } catch {
      // Keep the selection for the current page session when storage is unavailable.
    }
  };

  const value = useMemo(() => ({ businessId, setBusinessId }), [businessId]);
  return <WorkspaceContext.Provider value={value}>{children}</WorkspaceContext.Provider>;
};

export function useWorkspace(): WorkspaceContextValue {
  const context = useContext(WorkspaceContext);
  if (!context) throw new Error('useWorkspace must be used within WorkspaceProvider.');
  return context;
}
