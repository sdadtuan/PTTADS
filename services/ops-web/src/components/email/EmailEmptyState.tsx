'use client';

import Link from 'next/link';

export function EmailEmptyState({
  message,
  ctaLabel,
  ctaHref,
  onCta,
}: {
  message: string;
  ctaLabel?: string;
  ctaHref?: string;
  onCta?: () => void;
}) {
  return (
    <div className="email-empty">
      <p className="muted">{message}</p>
      {ctaLabel && ctaHref ? (
        <Link href={ctaHref} className="btn btn-sm">
          {ctaLabel}
        </Link>
      ) : null}
      {ctaLabel && onCta ? (
        <button type="button" className="btn btn-sm" onClick={onCta}>
          {ctaLabel}
        </button>
      ) : null}
    </div>
  );
}
