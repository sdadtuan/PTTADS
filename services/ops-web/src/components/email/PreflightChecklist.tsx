'use client';

export interface PreflightCheck {
  id?: string;
  name?: string;
  label?: string;
  status: 'pass' | 'warn' | 'fail';
  message?: string;
}

function icon(status: PreflightCheck['status']): string {
  if (status === 'pass') return '✓';
  if (status === 'warn') return '⚠';
  return '✗';
}

export function PreflightChecklist({ checks }: { checks: PreflightCheck[] }) {
  if (checks.length === 0) {
    return <p className="muted">Chưa chạy preflight.</p>;
  }
  return (
    <div role="list" aria-label="Preflight checklist">
      {checks.map((check) => (
        <div
          key={check.id ?? check.name ?? check.label}
          className="email-preflight-row"
          role="listitem"
          aria-checked={check.status === 'pass'}
        >
          <span className={`email-preflight-${check.status}`} aria-hidden>
            {icon(check.status)}
          </span>
          <div>
            <strong>{check.label ?? check.name}</strong>
            {check.message ? <p className="muted" style={{ margin: '0.15rem 0 0' }}>{check.message}</p> : null}
          </div>
        </div>
      ))}
    </div>
  );
}
