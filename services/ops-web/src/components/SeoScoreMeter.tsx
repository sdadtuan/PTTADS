'use client';

export function SeoScoreMeter({
  value,
  max = 100,
  label,
  unit = '',
}: {
  value: number | string | null | undefined;
  max?: number;
  label: string;
  unit?: string;
}) {
  const num = typeof value === 'number' ? value : Number.parseFloat(String(value ?? ''));
  const safe = Number.isFinite(num) ? Math.max(0, Math.min(num, max)) : 0;
  const pct = max ? Math.round((safe / max) * 100) : 0;

  return (
    <div
      role="meter"
      aria-valuenow={safe}
      aria-valuemin={0}
      aria-valuemax={max}
      aria-label={label}
      style={{ minWidth: 88 }}
    >
      <div
        style={{
          height: 8,
          background: 'var(--border, #eee)',
          borderRadius: 4,
          overflow: 'hidden',
          marginBottom: '0.25rem',
        }}
      >
        <div
          style={{
            width: `${pct}%`,
            height: '100%',
            background: 'currentColor',
            opacity: 0.65,
          }}
        />
      </div>
      <span style={{ fontSize: '0.85rem' }}>
        {Number.isFinite(num) ? `${safe}${unit}` : '—'}
      </span>
    </div>
  );
}
