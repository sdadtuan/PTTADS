'use client';

import { useCallback, useMemo } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { metaAlertsEnabled } from '@/lib/meta/flags';
import type { MetaHubTab } from '@/lib/meta/types';

const VALID_TABS: MetaHubTab[] = ['clients', 'campaigns', 'alerts'];

export function useMetaHubTab() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const alertsEnabled = metaAlertsEnabled();

  const tab = useMemo((): MetaHubTab => {
    const raw = searchParams.get('tab');
    if (raw === 'campaigns') return 'campaigns';
    if (raw === 'alerts' && alertsEnabled) return 'alerts';
    return 'clients';
  }, [alertsEnabled, searchParams]);

  const setTab = useCallback(
    (next: MetaHubTab) => {
      if (next === 'alerts' && !alertsEnabled) return;
      const qs = new URLSearchParams(searchParams.toString());
      if (next === 'clients') {
        qs.delete('tab');
      } else {
        qs.set('tab', next);
      }
      const suffix = qs.toString();
      router.replace(suffix ? `/meta/facebook-ads?${suffix}` : '/meta/facebook-ads', {
        scroll: false,
      });
    },
    [alertsEnabled, router, searchParams],
  );

  const tabs = useMemo(() => {
    const items: Array<{ id: MetaHubTab; label: string }> = [
      { id: 'clients', label: 'Clients' },
      { id: 'campaigns', label: 'Campaigns' },
    ];
    if (alertsEnabled) {
      items.push({ id: 'alerts', label: 'Alerts' });
    }
    return items;
  }, [alertsEnabled]);

  return { tab, setTab, tabs, alertsEnabled };
}

export { VALID_TABS };
