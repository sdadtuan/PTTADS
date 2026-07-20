'use client';

export function EmailDnsStatus({ status, label }: { status: string; label?: string }) {
  const key = status.toLowerCase();
  const icon = key === 'pass' || key === 'ok' ? '✓' : key === 'warn' ? '⚠' : key === 'fail' ? '✗' : '—';
  const cls =
    key === 'pass' || key === 'ok'
      ? 'email-dns-pass'
      : key === 'warn'
        ? 'email-dns-warn'
        : key === 'fail'
          ? 'email-dns-fail'
          : 'muted';
  return (
    <span className={`email-dns-status ${cls}`} aria-label={`${label ?? 'DNS'}: ${status}`}>
      {icon} {label ?? status}
    </span>
  );
}

export function EmailWarmupMeter({ stage, max = 5 }: { stage: number; max?: number }) {
  return (
    <span className="email-warmup-meter" aria-label={`Warm-up stage ${stage} / ${max}`}>
      {Array.from({ length: max }, (_, i) => (
        <span key={i} className={i < stage ? 'active' : undefined} />
      ))}
    </span>
  );
}
