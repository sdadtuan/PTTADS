'use client';

import { useCallback, useEffect, useState } from 'react';
import { EmailStatusBadge } from './EmailStatusBadge';
import {
  createEmailExperiment,
  declareEmailExperimentWinner,
  fetchCampaignExperiment,
  rollupEmailExperiment,
  startEmailExperiment,
  type EmailExperimentRow,
} from '@/lib/api';

export function CampaignExperimentPanel({
  token,
  campaignId,
  clientId,
  canWrite,
}: {
  token: string;
  campaignId: string;
  clientId: string;
  canWrite: boolean;
}) {
  const [experiment, setExperiment] = useState<EmailExperimentRow | null>(null);
  const [controlSubject, setControlSubject] = useState('');
  const [variantSubject, setVariantSubject] = useState('');
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    setError('');
    try {
      setExperiment(await fetchCampaignExperiment(token, campaignId));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Tải experiment thất bại');
    }
  }, [token, campaignId]);

  useEffect(() => {
    void load();
  }, [load]);

  async function createExperiment() {
    setBusy('create');
    setError('');
    try {
      const row = await createEmailExperiment(token, {
        client_id: clientId,
        campaign_id: campaignId,
        name: `Subject A/B — ${campaignId.slice(0, 8)}`,
        variants: [
          { variant_key: 'control', label: 'Control', subject: controlSubject, split_pct: 50 },
          { variant_key: 'variant_a', label: 'Variant A', subject: variantSubject, split_pct: 50 },
        ],
      });
      setExperiment(row);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Tạo experiment thất bại');
    } finally {
      setBusy('');
    }
  }

  async function start() {
    if (!experiment) return;
    setBusy('start');
    setError('');
    try {
      setExperiment(await startEmailExperiment(token, experiment.id));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Start experiment thất bại');
    } finally {
      setBusy('');
    }
  }

  async function rollup() {
    if (!experiment) return;
    setBusy('rollup');
    setError('');
    try {
      await rollupEmailExperiment(token, experiment.id);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Rollup thất bại');
    } finally {
      setBusy('');
    }
  }

  async function declareWinner(variantKey: string) {
    if (!experiment) return;
    setBusy(`winner:${variantKey}`);
    setError('');
    try {
      setExperiment(await declareEmailExperimentWinner(token, experiment.id, variantKey));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Declare winner thất bại');
    } finally {
      setBusy('');
    }
  }

  return (
    <div className="card" style={{ marginBottom: '1rem' }}>
      <h2 style={{ marginTop: 0, fontSize: '1.1rem' }}>A/B subject experiment</h2>
      {error ? <p className="error">{error}</p> : null}
      {experiment ? (
        <>
          <p className="muted">
            {experiment.name} · <EmailStatusBadge status={experiment.status} />
          </p>
          <ul style={{ margin: '0.5rem 0', paddingLeft: '1.2rem' }}>
            {(experiment.variants ?? []).map((v) => (
              <li key={v.variant_key}>
                <strong>{v.variant_key}</strong> — {String(v.config_json?.subject ?? '')} ({v.split_pct}%)
              </li>
            ))}
          </ul>
          {canWrite ? (
            <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
              {experiment.status === 'draft' ? (
                <button type="button" className="btn btn-sm" disabled={!!busy} onClick={() => void start()}>
                  {busy === 'start' ? '…' : 'Start experiment'}
                </button>
              ) : null}
              {experiment.status === 'running' ? (
                <>
                  <button type="button" className="btn btn-secondary btn-sm" disabled={!!busy} onClick={() => void rollup()}>
                    {busy === 'rollup' ? '…' : 'Rollup metrics'}
                  </button>
                  {(experiment.variants ?? []).map((v) => (
                    <button
                      key={v.variant_key}
                      type="button"
                      className="btn btn-sm"
                      disabled={!!busy}
                      onClick={() => void declareWinner(v.variant_key)}
                    >
                      Winner: {v.variant_key}
                    </button>
                  ))}
                </>
              ) : null}
            </div>
          ) : null}
          {experiment.winner_variant_key ? (
            <p className="muted">Winner: {experiment.winner_variant_key}</p>
          ) : null}
        </>
      ) : canWrite ? (
        <>
          <label className="muted" style={{ display: 'block' }}>
            Control subject
            <input className="input" value={controlSubject} onChange={(e) => setControlSubject(e.target.value)} style={{ width: '100%' }} />
          </label>
          <label className="muted" style={{ display: 'block', marginTop: '0.5rem' }}>
            Variant A subject
            <input className="input" value={variantSubject} onChange={(e) => setVariantSubject(e.target.value)} style={{ width: '100%' }} />
          </label>
          <button
            type="button"
            className="btn btn-sm"
            style={{ marginTop: '0.75rem' }}
            disabled={!!busy || !controlSubject.trim() || !variantSubject.trim()}
            onClick={() => void createExperiment()}
          >
            {busy === 'create' ? '…' : 'Tạo subject A/B'}
          </button>
        </>
      ) : (
        <p className="muted">Chưa có experiment cho campaign này.</p>
      )}
    </div>
  );
}
