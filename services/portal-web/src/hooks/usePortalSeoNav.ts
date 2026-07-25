'use client';

import { useEffect, useState } from 'react';
import { portalSeoStatus } from '@/lib/api';

export function usePortalSeoNav(token: string | null): boolean {
  const [seoEnabled, setSeoEnabled] = useState(false);

  useEffect(() => {
    if (!token) {
      setSeoEnabled(false);
      return;
    }
    void portalSeoStatus(token)
      .then((status) => setSeoEnabled(Boolean(status.enabled && status.mapped)))
      .catch(() => setSeoEnabled(false));
  }, [token]);

  return seoEnabled;
}
