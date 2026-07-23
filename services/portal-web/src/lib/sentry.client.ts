'use client';

const DSN = process.env.NEXT_PUBLIC_SENTRY_DSN?.trim();

export function initPortalSentry(): void {
  if (!DSN || typeof window === 'undefined') {
    return;
  }
  const env = process.env.NEXT_PUBLIC_SENTRY_ENVIRONMENT ?? 'development';
  const report = (message: string, extra?: Record<string, unknown>) => {
    void fetch(`${DSN}`, { method: 'HEAD' }).catch(() => undefined);
    if (process.env.NODE_ENV !== 'production') {
      console.info('[portal-sentry-stub]', env, message, extra);
    }
  };
  window.addEventListener('error', (event) => {
    report(event.message, { stack: event.error?.stack });
  });
  window.addEventListener('unhandledrejection', (event) => {
    const reason = event.reason instanceof Error ? event.reason.message : String(event.reason);
    report(reason);
  });
}
