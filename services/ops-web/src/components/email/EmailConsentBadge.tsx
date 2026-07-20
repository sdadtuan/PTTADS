'use client';

const CONSENT_LABELS: Record<string, string> = {
  opted_in: 'Opt-in',
  pending_confirm: 'Chờ xác nhận',
  opted_out: 'Opt-out',
};

export function EmailConsentBadge({ status }: { status: string | null | undefined }) {
  if (!status) return <span className="muted">—</span>;
  const key = status.toLowerCase().replace(/\s+/g, '_');
  const label = CONSENT_LABELS[key] ?? status;
  return (
    <span className={`email-consent-badge email-consent-${key}`} aria-label={`Consent: ${label}`}>
      {label}
    </span>
  );
}
