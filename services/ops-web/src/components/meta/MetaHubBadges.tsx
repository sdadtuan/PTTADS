import { MetaBadge } from '@/components/meta/MetaBadge';

interface MetaHubBadgesProps {
  hubMapped: boolean;
  overTarget?: boolean;
  tokenStatus?: string | null;
}

export function MetaHubBadges({ hubMapped, overTarget, tokenStatus }: MetaHubBadgesProps) {
  const items = [];
  if (!hubMapped) {
    items.push(
      <MetaBadge key="unmapped" variant="warn" title="Campaign chưa map Hub">
        Chưa map
      </MetaBadge>,
    );
  }
  if (overTarget) {
    items.push(
      <MetaBadge key="over" variant="error" title="CPL vượt target">
        Vượt CPL
      </MetaBadge>,
    );
  }
  if (tokenStatus === 'expired' || tokenStatus === 'revoked' || tokenStatus === 'error') {
    items.push(
      <MetaBadge key="token" variant="error" title={`Token: ${tokenStatus}`}>
        Token lỗi
      </MetaBadge>,
    );
  }
  if (!items.length) {
    return <MetaBadge variant="ok">OK</MetaBadge>;
  }
  return <span style={{ display: 'inline-flex', gap: '0.35rem', flexWrap: 'wrap' }}>{items}</span>;
}
