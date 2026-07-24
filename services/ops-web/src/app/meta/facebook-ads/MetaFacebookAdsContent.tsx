'use client';

import { MetaAttributionFooter } from '@/components/meta/MetaAttributionFooter';
import { MetaHubAlertsList } from '@/components/meta/MetaHubAlertsList';
import { MetaHubFilters } from '@/components/meta/MetaHubFilters';
import { MetaHubKpiGrid } from '@/components/meta/MetaHubKpiGrid';
import { MetaHubTabPanels } from '@/components/meta/MetaHubTabPanels';
import { MetaHubTabs } from '@/components/meta/MetaHubTabs';
import { MetaPageShell } from '@/components/meta/MetaPageShell';
import { MetaSyncStatusChip } from '@/components/meta/MetaSyncStatusChip';
import { useMetaAlerts } from '@/hooks/meta/useMetaAlerts';
import { useMetaHub } from '@/hooks/meta/useMetaHub';
import { useMetaHubCampaigns } from '@/hooks/meta/useMetaHubCampaigns';
import { useMetaHubTab } from '@/hooks/meta/useMetaHubTab';

export function MetaFacebookAdsContent() {
  const hub = useMetaHub();
  const { tab, setTab, tabs, alertsEnabled } = useMetaHubTab();
  const campaigns = useMetaHubCampaigns(hub.hubQuery, tab === 'campaigns');
  const alerts = useMetaAlerts(hub.clientId || undefined, alertsEnabled);

  if (!hub.user) {
    return (
      <main style={{ padding: '2rem' }}>
        <p className="muted">Đang tải…</p>
      </main>
    );
  }

  const clientRows = hub.hub?.clients ?? [];
  const summary = hub.hub?.summary ?? {};
  const attribution = hub.hub?.attribution ?? campaigns.data?.attribution ?? null;

  return (
    <MetaPageShell
      user={hub.user}
      onLogout={hub.logout}
      migration={hub.migration}
      headerExtra={<MetaSyncStatusChip clientId={hub.clientId || undefined} />}
    >
      <MetaHubFilters
        days={hub.days}
        dateTo={hub.dateTo}
        dateFrom={hub.dateFrom}
        clientId={hub.clientId}
        status={hub.status}
        q={hub.q}
        exportScope={hub.exportScope}
        clientOptions={hub.clientOptions}
        loading={hub.loading}
        exportBusy={hub.exportBusy}
        hubDateFrom={hub.hub?.date_from}
        hubDateTo={hub.hub?.date_to}
        hubWindowDays={hub.hub?.window_days}
        onDaysChange={hub.setDays}
        onDateToChange={hub.setDateTo}
        onDateFromChange={hub.setDateFrom}
        onClientIdChange={hub.setClientId}
        onStatusChange={hub.setStatus}
        onQueryChange={hub.setQ}
        onExportScopeChange={hub.setExportScope}
        onRefresh={hub.handleRefresh}
        onExport={() => void hub.handleExport()}
      />

      {hub.error ? <p className="error">{hub.error}</p> : null}

      <MetaHubKpiGrid summary={summary} clientCount={clientRows.length} attribution={attribution} />
      <MetaAttributionFooter attribution={attribution} />
      <MetaHubAlertsList alerts={hub.hub?.alerts ?? []} />

      <MetaHubTabs
        tab={tab}
        tabs={tabs}
        onTabChange={setTab}
        alertsOpenCount={alertsEnabled ? alerts.openCount : 0}
      />

      <MetaHubTabPanels
        tab={tab}
        clientRows={clientRows}
        loading={hub.loading}
        trackingByClient={hub.trackingByClient}
        campaigns={campaigns.campaigns}
        campaignsLoading={campaigns.loading}
        campaignsError={campaigns.error}
        hubDateFrom={hub.hub?.date_from}
        hubDateTo={hub.hub?.date_to}
        onMapSuggestDone={() => {
          hub.handleRefresh();
          if (tab === 'campaigns') void campaigns.reload();
        }}
        alertsEnabled={alertsEnabled}
        pgAlerts={alerts.alerts}
        alertsLoading={alerts.loading}
        alertsError={alerts.error}
        ackBusyId={alerts.ackBusyId}
        onAck={(id) => void alerts.acknowledge(id)}
      />
    </MetaPageShell>
  );
}
