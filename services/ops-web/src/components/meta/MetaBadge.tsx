import type { ReactNode } from 'react';
import type { MetaBadgeVariant } from '@/lib/meta/types';

const VARIANT_CLASS: Record<MetaBadgeVariant, string> = {
  ok: 'meta-badge--ok',
  warn: 'meta-badge--warn',
  error: 'meta-badge--error',
  muted: 'meta-badge--muted',
};

interface MetaBadgeProps {
  variant: MetaBadgeVariant;
  children: ReactNode;
  title?: string;
}

export function MetaBadge({ variant, children, title }: MetaBadgeProps) {
  return (
    <span className={`meta-badge ${VARIANT_CLASS[variant]}`} title={title}>
      {children}
    </span>
  );
}
