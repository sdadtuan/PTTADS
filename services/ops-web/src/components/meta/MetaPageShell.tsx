'use client';

import type { ReactNode } from 'react';
import { MetaMigrationPanel } from '@/components/MetaMigrationPanel';
import { OpsNav } from '@/components/OpsNav';
import type { FacebookAdsMigrationStatus } from '@/lib/api';
import type { StoredStaffUser } from '@/lib/auth';

interface MetaPageShellProps {
  user: StoredStaffUser;
  onLogout: () => void;
  migration?: FacebookAdsMigrationStatus | null;
  headerExtra?: ReactNode;
  maxWidth?: number;
  children: ReactNode;
}

export function MetaPageShell({
  user,
  onLogout,
  migration,
  headerExtra,
  maxWidth = 1200,
  children,
}: MetaPageShellProps) {
  return (
    <main style={{ maxWidth, margin: '0 auto', padding: '1.5rem' }}>
      <OpsNav user={user} onLogout={onLogout} />
      {migration ? <MetaMigrationPanel status={migration} variant="compact" /> : null}
      {headerExtra ? (
        <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: '0.75rem' }}>
          {headerExtra}
        </div>
      ) : null}
      {children}
    </main>
  );
}
