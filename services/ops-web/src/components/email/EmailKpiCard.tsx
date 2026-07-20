'use client';

export function EmailKpiCard({
  label,
  value,
  hint,
}: {
  label: string;
  value: string | number;
  hint?: string;
}) {
  return (
    <div className="email-kpi-card">
      <p className="muted" style={{ margin: 0 }}>
        {label}
      </p>
      <strong>{value}</strong>
      {hint ? (
        <span className="muted" style={{ fontSize: '0.75rem' }}>
          {hint}
        </span>
      ) : null}
    </div>
  );
}
