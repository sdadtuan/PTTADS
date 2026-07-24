'use client';

import Link from 'next/link';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import { MetaAdSnapshotPanel } from '@/components/meta/MetaAdSnapshotPanel';
import { MetaCreativePicker } from '@/components/meta/MetaCreativePicker';
import { MetaDeepLinkButton } from '@/components/meta/MetaDeepLinkButton';
import { MetaDiffPanel } from '@/components/meta/MetaDiffPanel';
import { MetaPreflightChecklist } from '@/components/meta/MetaPreflightChecklist';
import {
  EDIT_WIZARD_STEPS,
  LAUNCH_WIZARD_STEPS,
  MetaWizardStepper,
} from '@/components/meta/MetaWizardStepper';
import { fetchCrmCreatives } from '@/lib/api';
import { getAccessToken, getStoredUser } from '@/lib/auth';
import {
  fetchMetaAdsOpsEditSnapshot,
  fetchMetaAdsOpsPreflight,
  fetchMetaAdsOpsTemplates,
  postMetaAdsOpsCreativeUpload,
  postMetaAdsOpsEditSubmit,
  postMetaAdsOpsLaunch,
} from '@/lib/meta/api';
import { canSubmitMetaAdsOps, canViewMetaAdsOps } from '@/lib/meta/caps';
import { metaAdsOpsEnabled } from '@/lib/meta/flags';
import type { MetaAdsOpsEditSnapshot, MetaAdsOpsPreflightItem, MetaAdsOpsTemplate } from '@/lib/meta/types';

type TabMode = 'launch' | 'edit';

export function MetaAdsOpsContent() {
  const searchParams = useSearchParams();
  const user = getStoredUser();
  const canView = canViewMetaAdsOps(user);
  const canSubmit = canSubmitMetaAdsOps(user);
  const enabled = metaAdsOpsEnabled();

  const initialMode = (searchParams.get('mode') === 'edit' ? 'edit' : 'launch') as TabMode;
  const [tab, setTab] = useState<TabMode>(initialMode);
  const [launchStep, setLaunchStep] = useState(0);
  const [editStep, setEditStep] = useState(0);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [loading, setLoading] = useState(false);

  const [clientId, setClientId] = useState(searchParams.get('client_id') ?? '');
  const [externalAccountId, setExternalAccountId] = useState('');
  const [templates, setTemplates] = useState<MetaAdsOpsTemplate[]>([]);
  const [templateId, setTemplateId] = useState('re_lead_default');
  const [campaignName, setCampaignName] = useState('');
  const [adsetName, setAdsetName] = useState('');
  const [adName, setAdName] = useState('');
  const [dailyBudget, setDailyBudget] = useState(500_000);
  const [creativeId, setCreativeId] = useState('');
  const [creatives, setCreatives] = useState<
    Array<{ id: string; title: string; status: string; version?: number; external_campaign_id?: string | null }>
  >([]);
  const [preflightItems, setPreflightItems] = useState<MetaAdsOpsPreflightItem[]>([]);
  const [preflightReady, setPreflightReady] = useState(false);

  const [externalAdId, setExternalAdId] = useState(searchParams.get('ad_id') ?? '');
  const [editAction, setEditAction] = useState<'update_ad_creative' | 'update_ad_copy'>('update_ad_copy');
  const [snapshot, setSnapshot] = useState<MetaAdsOpsEditSnapshot | null>(null);
  const [headline, setHeadline] = useState('');
  const [primaryText, setPrimaryText] = useState('');
  const [disapprovedAck, setDisapprovedAck] = useState(searchParams.get('ack') === '1');

  const selectedTemplate = useMemo(
    () => templates.find((t) => t.id === templateId) ?? templates[0],
    [templates, templateId],
  );

  const reloadCreatives = useCallback(async () => {
    const token = getAccessToken();
    if (!token || !clientId) return;
    const out = await fetchCrmCreatives(token, 'all', 200);
    setCreatives(out.rows.filter((row) => row.client_id === clientId));
  }, [clientId]);

  const reloadPreflight = useCallback(async () => {
    const token = getAccessToken();
    if (!token || !clientId) return;
    const out = await fetchMetaAdsOpsPreflight(token, clientId);
    setPreflightItems(out.items ?? []);
    setPreflightReady(Boolean(out.ready));
  }, [clientId]);

  useEffect(() => {
    const token = getAccessToken();
    if (!token || !enabled) return;
    void fetchMetaAdsOpsTemplates(token)
      .then((out) => {
        setTemplates(out.templates ?? []);
        if (out.templates?.[0]) {
          setTemplateId(out.templates[0].id);
          setDailyBudget(out.templates[0].default_daily_budget_vnd);
        }
      })
      .catch((err) => setError(err instanceof Error ? err.message : 'Load templates failed'));
  }, [enabled]);

  useEffect(() => {
    if (clientId) {
      void reloadCreatives();
      void reloadPreflight();
    }
  }, [clientId, reloadCreatives, reloadPreflight]);

  useEffect(() => {
    const token = getAccessToken();
    if (!token || !clientId || !externalAdId || tab !== 'edit') return;
    setLoading(true);
    void fetchMetaAdsOpsEditSnapshot(token, clientId, externalAdId)
      .then((out) => {
        setSnapshot(out);
        setHeadline(out.headline);
        setPrimaryText(out.primary_text);
      })
      .catch((err) => setError(err instanceof Error ? err.message : 'Snapshot failed'))
      .finally(() => setLoading(false));
  }, [clientId, externalAdId, tab]);

  if (!enabled) {
    return (
      <main style={{ padding: '2rem' }}>
        <h1>Meta Ads Ops</h1>
        <p className="muted">
          Bật <code>NEXT_PUBLIC_PTT_META_ADS_OPS_ENABLED=1</code> và backend{' '}
          <code>PTT_META_ADS_OPS_ENABLED=1</code>
        </p>
      </main>
    );
  }

  if (!canView) {
    return (
      <main style={{ padding: '2rem' }}>
        <h1>Meta Ads Ops</h1>
        <p className="error">Thiếu quyền xem Meta Ads Ops</p>
      </main>
    );
  }

  const submitLaunch = async () => {
    const token = getAccessToken();
    if (!token || !canSubmit) return;
    setError('');
    setSuccess('');
    setLoading(true);
    try {
      if (creativeId) {
        await postMetaAdsOpsCreativeUpload(token, {
          client_id: clientId,
          creative_submission_id: creativeId,
          external_account_id: externalAccountId || undefined,
        });
      }
      const out = await postMetaAdsOpsLaunch(token, {
        client_id: clientId,
        external_account_id: externalAccountId,
        template_id: templateId,
        campaign_name: campaignName,
        adset_name: adsetName,
        ad_name: adName,
        daily_budget_vnd: dailyBudget,
        creative_submission_id: creativeId,
        preflight_ack: !preflightReady,
      });
      setSuccess(`Đã submit launch · request ${out.request_id ?? '—'}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Launch submit failed');
    } finally {
      setLoading(false);
    }
  };

  const submitEdit = async () => {
    const token = getAccessToken();
    if (!token || !canSubmit || !snapshot) return;
    setError('');
    setSuccess('');
    setLoading(true);
    const oldValue =
      editAction === 'update_ad_copy'
        ? { headline: snapshot.headline, primary_text: snapshot.primary_text }
        : { creative_submission_id: snapshot.creative_submission_id };
    const newValue =
      editAction === 'update_ad_copy'
        ? { headline, primary_text: primaryText }
        : { creative_submission_id: creativeId };
    try {
      const out = await postMetaAdsOpsEditSubmit(token, {
        client_id: clientId,
        external_ad_id: externalAdId,
        action: editAction,
        old_value: oldValue,
        new_value: newValue,
        disapproved_ack: disapprovedAck,
      });
      setSuccess(`Đã submit edit · request ${out.request_id ?? '—'}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Edit submit failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <main style={{ padding: '2rem', maxWidth: 1100 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: '1rem', flexWrap: 'wrap' }}>
        <div>
          <h1 style={{ marginBottom: '0.25rem' }}>Meta Ads Ops</h1>
          <p className="muted" style={{ marginTop: 0 }}>
            Launch wizard + Edit creative/copy · governed via campaign-writes approve
          </p>
        </div>
        {clientId ? <MetaDeepLinkButton clientId={clientId} externalAdId={externalAdId || undefined} /> : null}
      </div>

      <div style={{ display: 'flex', gap: '0.5rem', margin: '1rem 0' }}>
        <button type="button" className={`btn ${tab === 'launch' ? 'btn-primary' : 'btn-secondary'}`} onClick={() => setTab('launch')}>
          Launch
        </button>
        <button type="button" className={`btn ${tab === 'edit' ? 'btn-primary' : 'btn-secondary'}`} onClick={() => setTab('edit')}>
          Edit
        </button>
        <Link href="/crm/campaign-writes" className="btn btn-secondary">
          Campaign writes
        </Link>
      </div>

      {error ? <p className="error">{error}</p> : null}
      {success ? <p style={{ color: 'var(--ok, green)' }}>{success}</p> : null}

      {tab === 'launch' ? (
        <>
          <MetaWizardStepper steps={LAUNCH_WIZARD_STEPS} currentStep={launchStep} />
          <div style={{ marginTop: '1rem', display: 'grid', gap: '1rem' }}>
            {launchStep === 0 ? (
              <div className="card">
                <h3 style={{ marginTop: 0 }}>Client & account</h3>
                <label>
                  Client UUID
                  <input className="input" value={clientId} onChange={(e) => setClientId(e.target.value.trim())} />
                </label>
                <label style={{ display: 'block', marginTop: '0.75rem' }}>
                  Meta ad account (act_*)
                  <input
                    className="input"
                    value={externalAccountId}
                    onChange={(e) => setExternalAccountId(e.target.value.trim())}
                    placeholder="act_1234567890"
                  />
                </label>
              </div>
            ) : null}

            {launchStep === 1 ? (
              <div className="card">
                <h3 style={{ marginTop: 0 }}>Objective & budget</h3>
                <label>
                  Template
                  <select className="input" value={templateId} onChange={(e) => setTemplateId(e.target.value)}>
                    {templates.map((t) => (
                      <option key={t.id} value={t.id}>
                        {t.label}
                      </option>
                    ))}
                  </select>
                </label>
                {selectedTemplate ? (
                  <p className="muted">{selectedTemplate.description}</p>
                ) : null}
                <label style={{ display: 'block', marginTop: '0.75rem' }}>
                  Daily budget (VND)
                  <input
                    className="input"
                    type="number"
                    value={dailyBudget}
                    onChange={(e) => setDailyBudget(Number(e.target.value))}
                  />
                </label>
                <label style={{ display: 'block', marginTop: '0.75rem' }}>
                  Campaign name
                  <input className="input" value={campaignName} onChange={(e) => setCampaignName(e.target.value)} />
                </label>
                <label style={{ display: 'block', marginTop: '0.75rem' }}>
                  Ad set name
                  <input className="input" value={adsetName} onChange={(e) => setAdsetName(e.target.value)} />
                </label>
                <label style={{ display: 'block', marginTop: '0.75rem' }}>
                  Ad name
                  <input className="input" value={adName} onChange={(e) => setAdName(e.target.value)} />
                </label>
              </div>
            ) : null}

            {launchStep === 2 ? (
              <MetaCreativePicker creatives={creatives} selectedId={creativeId} onSelect={setCreativeId} />
            ) : null}

            {launchStep === 3 ? (
              <MetaPreflightChecklist items={preflightItems} clientId={clientId} onRefresh={() => void reloadPreflight()} />
            ) : null}

            {launchStep === 4 ? (
              <div className="card">
                <h3 style={{ marginTop: 0 }}>Review</h3>
                <ul>
                  <li>Client: {clientId || '—'}</li>
                  <li>Account: {externalAccountId || '—'}</li>
                  <li>Template: {templateId}</li>
                  <li>Budget: {dailyBudget.toLocaleString('vi-VN')} VND</li>
                  <li>Creative: {creativeId || '—'}</li>
                  <li>Preflight: {preflightReady ? 'Ready' : 'Needs ack / fix'}</li>
                </ul>
                {!canSubmit ? <p className="muted">Thiếu quyền submit Meta Ads Ops</p> : null}
              </div>
            ) : null}
          </div>

          <div style={{ display: 'flex', gap: '0.5rem', marginTop: '1rem' }}>
            <button type="button" className="btn btn-secondary" disabled={launchStep === 0} onClick={() => setLaunchStep((s) => s - 1)}>
              Back
            </button>
            {launchStep < LAUNCH_WIZARD_STEPS.length - 1 ? (
              <button type="button" className="btn btn-primary" onClick={() => setLaunchStep((s) => s + 1)}>
                Next
              </button>
            ) : (
              <button type="button" className="btn btn-primary" disabled={!canSubmit || loading} onClick={() => void submitLaunch()}>
                {loading ? 'Submitting…' : 'Submit for approval'}
              </button>
            )}
          </div>
        </>
      ) : (
        <>
          <MetaWizardStepper steps={EDIT_WIZARD_STEPS} currentStep={editStep} />
          <div style={{ marginTop: '1rem', display: 'grid', gap: '1rem' }}>
            {editStep === 0 ? (
              <div className="card">
                <h3 style={{ marginTop: 0 }}>Chọn ad</h3>
                <label>
                  Client UUID
                  <input className="input" value={clientId} onChange={(e) => setClientId(e.target.value.trim())} />
                </label>
                <label style={{ display: 'block', marginTop: '0.75rem' }}>
                  External ad id
                  <input className="input" value={externalAdId} onChange={(e) => setExternalAdId(e.target.value.trim())} />
                </label>
                <MetaAdSnapshotPanel snapshot={snapshot} loading={loading} />
              </div>
            ) : null}

            {editStep === 1 ? (
              <>
                <div className="card">
                  <h3 style={{ marginTop: 0 }}>Edit mode</h3>
                  <label>
                    Action
                    <select
                      className="input"
                      value={editAction}
                      onChange={(e) => setEditAction(e.target.value as 'update_ad_creative' | 'update_ad_copy')}
                    >
                      <option value="update_ad_copy">Update copy</option>
                      <option value="update_ad_creative">Swap creative</option>
                    </select>
                  </label>
                  {editAction === 'update_ad_copy' ? (
                    <>
                      <label style={{ display: 'block', marginTop: '0.75rem' }}>
                        Headline
                        <input className="input" value={headline} onChange={(e) => setHeadline(e.target.value)} />
                      </label>
                      <label style={{ display: 'block', marginTop: '0.75rem' }}>
                        Primary text
                        <textarea className="input" rows={4} value={primaryText} onChange={(e) => setPrimaryText(e.target.value)} />
                      </label>
                    </>
                  ) : (
                    <MetaCreativePicker creatives={creatives} selectedId={creativeId} onSelect={setCreativeId} />
                  )}
                  {snapshot?.effective_status === 'DISAPPROVED' ? (
                    <label style={{ display: 'flex', gap: '0.5rem', marginTop: '0.75rem' }}>
                      <input type="checkbox" checked={disapprovedAck} onChange={(e) => setDisapprovedAck(e.target.checked)} />
                      Ack ad disapproved — sẽ trigger re-review
                    </label>
                  ) : null}
                </div>
              </>
            ) : null}

            {editStep === 2 && snapshot ? (
              <MetaDiffPanel
                oldValue={
                  editAction === 'update_ad_copy'
                    ? { headline: snapshot.headline, primary_text: snapshot.primary_text }
                    : { creative_submission_id: snapshot.creative_submission_id }
                }
                newValue={
                  editAction === 'update_ad_copy'
                    ? { headline, primary_text: primaryText }
                    : { creative_submission_id: creativeId }
                }
              />
            ) : null}

            {editStep === 3 ? (
              <div className="card">
                <h3 style={{ marginTop: 0 }}>Submit edit</h3>
                <p className="muted">Request sẽ vào campaign-writes để approve trước khi Graph execute.</p>
              </div>
            ) : null}
          </div>

          <div style={{ display: 'flex', gap: '0.5rem', marginTop: '1rem' }}>
            <button type="button" className="btn btn-secondary" disabled={editStep === 0} onClick={() => setEditStep((s) => s - 1)}>
              Back
            </button>
            {editStep < EDIT_WIZARD_STEPS.length - 1 ? (
              <button type="button" className="btn btn-primary" onClick={() => setEditStep((s) => s + 1)}>
                Next
              </button>
            ) : (
              <button type="button" className="btn btn-primary" disabled={!canSubmit || loading} onClick={() => void submitEdit()}>
                {loading ? 'Submitting…' : 'Submit edit for approval'}
              </button>
            )}
          </div>
        </>
      )}
    </main>
  );
}
