import * as Sentry from '@sentry/node';

export function initSentry(component = 'ptt-crm-api'): void {
  const dsn = (process.env.SENTRY_DSN ?? '').trim();
  if (!dsn) {
    return;
  }
  Sentry.init({
    dsn,
    environment: (process.env.SENTRY_ENVIRONMENT ?? 'development').trim(),
    release: (process.env.SENTRY_RELEASE ?? '').trim() || undefined,
    tracesSampleRate: Number(process.env.SENTRY_TRACES_SAMPLE_RATE ?? 0) || 0,
    sendDefaultPii: false,
    beforeSend(event) {
      const cid = event.tags?.correlation_id;
      if (!cid && event.request?.headers) {
        const headers = event.request.headers as Record<string, string | string[] | undefined>;
        const raw = headers['x-correlation-id'] ?? headers['X-Correlation-Id'];
        const value = Array.isArray(raw) ? raw[0] : raw;
        if (value) {
          event.tags = { ...event.tags, correlation_id: value };
        }
      }
      return event;
    },
  });
  Sentry.setTag('component', component);
}

export { Sentry };
