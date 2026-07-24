'use client';

import Link from 'next/link';
import { buildMetaAdsOpsEditUrl } from '@/lib/meta/ads-ops-url';
import { metaAdsOpsEnabled } from '@/lib/meta/flags';

interface MetaEditAdLinkProps {
  clientId: string;
  externalAdId: string;
  disapproved?: boolean;
  className?: string;
}

export function MetaEditAdLink({
  clientId,
  externalAdId,
  disapproved,
  className = 'btn btn-sm btn-secondary',
}: MetaEditAdLinkProps) {
  if (!metaAdsOpsEnabled() || !clientId.trim() || !externalAdId.trim()) return null;

  return (
    <Link
      href={buildMetaAdsOpsEditUrl({
        clientId: clientId.trim(),
        externalAdId: externalAdId.trim(),
        disapproved,
      })}
      className={className}
    >
      Edit ad
    </Link>
  );
}
