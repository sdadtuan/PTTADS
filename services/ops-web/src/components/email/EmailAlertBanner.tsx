'use client';

import Link from 'next/link';

export function EmailAlertBanner({
  severity = 'info',
  message,
  link,
  linkLabel,
}: {
  severity?: 'info' | 'warn' | 'danger';
  message: string;
  link?: string;
  linkLabel?: string;
}) {
  return (
    <div className={`email-alert-banner email-alert-banner--${severity}`} role="status">
      <span>{message}</span>
      {link && linkLabel ? (
        <>
          {' '}
          <Link href={link} className="nav-link">
            {linkLabel}
          </Link>
        </>
      ) : null}
    </div>
  );
}
