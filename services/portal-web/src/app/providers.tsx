'use client';

import { useEffect } from 'react';
import { ToastProvider } from '@/lib/toast';
import { initPortalSentry } from '@/lib/sentry.client';

export function Providers({ children }: { children: React.ReactNode }) {
  useEffect(() => {
    initPortalSentry();
  }, []);
  return <ToastProvider>{children}</ToastProvider>;
}
