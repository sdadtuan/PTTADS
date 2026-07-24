import { MetaAlertsTable } from '@/components/meta/MetaAlertsTable';
import { MetaCampaignTable } from '@/components/meta/MetaCampaignTable';
import { MetaClientTable } from '@/components/meta/MetaClientTable';
import type {
  MetaAlertRow,
  MetaHubTab,
  FacebookHubCampaignRow,
  FacebookHubClient,
  TrackingHealthAccountRow,
} from '@/lib/meta/types';

interface MetaHubTabPanelsProps {
  tab: MetaHubTab;
  clientRows: FacebookHubClient[];
  loading: boolean;
  trackingByClient: Map<string, TrackingHealthAccountRow>;
  campaigns: FacebookHubCampaignRow[];
  campaignsLoading: boolean;
  campaignsError: string;
  hubDateFrom?: string;
  hubDateTo?: string;
  onMapSuggestDone: () => void;
  alertsEnabled: boolean;
  pgAlerts: MetaAlertRow[];
  alertsLoading: boolean;
  alertsError: string;
  ackBusyId: string | null;
  onAck: (id: string) => void;
}

export function MetaHubTabPanels({
  tab,
  clientRows,
  loading,
  trackingByClient,
  campaigns,
  campaignsLoading,
  campaignsError,
  hubDateFrom,
  hubDateTo,
  onMapSuggestDone,
  alertsEnabled,
  pgAlerts,
  alertsLoading,
  alertsError,
  ackBusyId,
  onAck,
}: MetaHubTabPanelsProps) {
  if (tab === 'clients') {
    return (
      <MetaClientTable rows={clientRows} loading={loading} trackingByClient={trackingByClient} />
    );
  }

  if (tab === 'campaigns') {
    return (
      <>
        {campaignsError ? <p className="error">{campaignsError}</p> : null}
        <MetaCampaignTable
          rows={campaigns}
          loading={campaignsLoading || loading}
          dateFrom={hubDateFrom}
          dateTo={hubDateTo}
          onMapSuggestDone={onMapSuggestDone}
        />
      </>
    );
  }

  if (tab === 'alerts' && alertsEnabled) {
    return (
      <>
        {alertsError ? <p className="error">{alertsError}</p> : null}
        <MetaAlertsTable
          alerts={pgAlerts}
          loading={alertsLoading}
          ackBusyId={ackBusyId}
          onAck={(id) => void onAck(id)}
        />
      </>
    );
  }

  return null;
}
