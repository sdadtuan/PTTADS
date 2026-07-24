'use client';

import { MetaAlertsTable } from '@/components/meta/MetaAlertsTable';
import { MetaAttributionFooter } from '@/components/meta/MetaAttributionFooter';
import { MetaCampaignTable } from '@/components/meta/MetaCampaignTable';
import { MetaClientTable } from '@/components/meta/MetaClientTable';
import { MetaHubAlertsList } from '@/components/meta/MetaHubAlertsList';
import { MetaHubFilters } from '@/components/meta/MetaHubFilters';
import { MetaHubKpiGrid } from '@/components/meta/MetaHubKpiGrid';
import { MetaHubTabs } from '@/components/meta/MetaHubTabs';
import { MetaPageShell } from '@/components/meta/MetaPageShell';
import { MetaSyncStatusChip } from '@/components/meta/MetaSyncStatusChip';
import { useMetaAlerts } from '@/hooks/meta/useMetaAlerts';
import { useMetaHub } from '@/hooks/meta/useMetaHub';
import { useMetaHubCampaigns } from '@/hooks/meta/useMetaHubCampaigns';
import { useMetaHubTab } from '@/hooks/meta/useMetaHubTab';

export function MetaFacebookAdsContent() {
  const {
    user,
    hub,
    migration,
    clientOptions,
    error,
    loading,
    exportBusy,
    days,
    dateTo,
    dateFrom,
    clientId,
    status,
    q,
    exportScope,
    hubQuery,
    trackingByClient,
    setDays,
    setDateTo,
    setDateFrom,
    setClientId,
    setStatus,
    setQ,
    setExportScope,
    handleRefresh,
    handleExport,
    logout,
  } = useMetaHub();

  const { tab, setTab, tabs, alertsEnabled } = useMetaHubTab();

  const {
    data: campaignsData,
    campaigns,
    loading: campaignsLoading,
    error: campaignsError,
    reload: reloadCampaigns,
  } = useMetaHubCampaigns(hubQuery, tab === 'campaigns');

  const {
    alerts: pgAlerts,
    openCount: alertsOpenCount,
    loading: alertsLoading,
    error: alertsError,
    ackBusyId,
    acknowledge,
  } = useMetaAlerts(clientId || undefined, alertsEnabled);

  if (!user) {
    return (
      <main style={{ padding: '2rem' }}>
        <p className="muted">Đang tải…</p>
      </main>
    );
  }

  const summary = hub?.summary ?? {};
  const clientRows = hub?.clients ?? [];
  const attribution = hub?.attribution ?? campaignsData?.attribution ?? null;

  const handleMapSuggestDone = () => {
    handleRefresh();
    if (tab === 'campaigns') void reloadCampaigns();
  };

  return (
    <MetaPageShell
      user={user}
      onLogout={logout}
      migration={migration}
      headerExtra={<MetaSyncStatusChip clientId={clientId || undefined} />}
    >
      <MetaHubFilters
        days={days}
        dateTo={dateTo}
        dateFrom={dateFrom}
        clientId={clientId}
        status={status}
        q={q}
        exportScope={exportScope}
        clientOptions={clientOptions}
        loading={loading}
        exportBusy={exportBusy}
        hubDateFrom={hub?.date_from}
        hubDateTo={hub?.date_to}
        hubWindowDays={hub?.window_days}
        onDaysChange={setDays}
        onDateToChange={setDateTo}
        onDateFromChange={setDateFrom}
        onClientIdChange={setClientId}
        onStatusChange={setStatus}
        onQueryChange={setQ}
        onExportScopeChange={setExportScope}
        onRefresh={handleRefresh}
        onExport={() => void handleExport()}
      />

      {error ? <p className="error">{error}</p> : null}

      <MetaHubKpiGrid summary={summary} clientCount={clientRows.length} attribution={attribution} />
      <MetaAttributionFooter attribution={attribution} />

      <MetaHubAlertsList alerts={hub?.alerts ?? []} />

      <MetaHubTabs
        tab={tab}
        tabs={tabs}
        onTabChange={setTab}
        alertsOpenCount={alertsEnabled ? alertsOpenCount : 0}
      />

      {tab === 'clients' ? (
        <MetaClientTable rows={clientRows} loading={loading} trackingByClient={trackingByClient} />
      ) : null}

      {tab === 'campaigns' ? (
        <>
          {campaignsError ? <p className="error">{campaignsError}</p> : null}
          <MetaCampaignTable
            rows={campaigns}
            loading={campaignsLoading || loading}
            dateFrom={hub?.date_from}
            dateTo={hub?.date_to}
            onMapSuggestDone={handleMapSuggestDone}
          />
        </>
      ) : null}

      {tab === 'alerts' && alertsEnabled ? (
        <>
          {alertsError ? <p className="error">{alertsError}</p> : null}
          <MetaAlertsTable
            alerts={pgAlerts}
            loading={alertsLoading}
            ackBusyId={ackBusyId}
            onAck={(id) => void acknowledge(id)}
          />
        </>
      ) : null}
    </MetaPageShell>
  );
}
