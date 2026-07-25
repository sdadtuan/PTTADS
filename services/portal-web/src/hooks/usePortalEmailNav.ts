'use client';

import { useEffect, useState } from 'react';
import { portalEmailDashboard } from '@/lib/api';

export function usePortalEmailNav(token: string | null): {
  emailEnabled: boolean;
  pendingEmail: number;
} {
  const [emailEnabled, setEmailEnabled] = useState(false);
  const [pendingEmail, setPendingEmail] = useState(0);

  useEffect(() => {
    if (!token) {
      setEmailEnabled(false);
      setPendingEmail(0);
      return;
    }
    void portalEmailDashboard(token)
      .then((dash) => {
        setEmailEnabled(Boolean(dash.email_enabled));
        setPendingEmail(Number(dash.pending_approvals ?? 0));
      })
      .catch(() => {
        setEmailEnabled(false);
        setPendingEmail(0);
      });
  }, [token]);

  return { emailEnabled, pendingEmail };
}
