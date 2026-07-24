'use client';

import { useCallback, useEffect, useState } from 'react';
import {
  createMetaCreativeLink,
  deactivateMetaCreativeLink,
  fetchMetaCreativeLinks,
} from '@/lib/meta/api';
import { MetaEditAdLink } from '@/components/meta/MetaEditAdLink';
import { metaCreativeRegistryEnabled } from '@/lib/meta/flags';
import type { MetaAdCreativeLinkRow } from '@/lib/meta/types';

interface MetaCreativeLinkPanelProps {
  token: string | null;
  clientId: string;
  creativeSubmissionId: string;
  creativeTitle: string;
  externalCampaignId?: string | null;
  canEdit: boolean;
  onLinked?: () => void;
}

export function MetaCreativeLinkPanel({
  token,
  clientId,
  creativeSubmissionId,
  creativeTitle,
  externalCampaignId,
  canEdit,
  onLinked,
}: MetaCreativeLinkPanelProps) {
  const enabled = metaCreativeRegistryEnabled() && Boolean(token);
  const [open, setOpen] = useState(false);
  const [links, setLinks] = useState<MetaAdCreativeLinkRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [externalAdId, setExternalAdId] = useState('');
  const [note, setNote] = useState('');

  const loadLinks = useCallback(async () => {
    if (!enabled || !token) return;
    setLoading(true);
    setError('');
    try {
      const res = await fetchMetaCreativeLinks(token, {
        client_id: clientId,
        creative_submission_id: creativeSubmissionId,
        active_only: true,
        limit: 20,
      });
      setLinks(res.rows ?? []);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không tải được registry link');
    } finally {
      setLoading(false);
    }
  }, [clientId, creativeSubmissionId, enabled, token]);

  useEffect(() => {
    if (open) void loadLinks();
  }, [loadLinks, open]);

  if (!enabled) return null;

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!token || !canEdit) return;
    setSaving(true);
    setError('');
    try {
      await createMetaCreativeLink(token, {
        client_id: clientId,
        creative_submission_id: creativeSubmissionId,
        external_ad_id: externalAdId.trim(),
        external_campaign_id: externalCampaignId ?? undefined,
        note: note.trim() || undefined,
      });
      setExternalAdId('');
      setNote('');
      await loadLinks();
      onLinked?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không tạo được link');
    } finally {
      setSaving(false);
    }
  }

  async function onDeactivate(linkId: string) {
    if (!token || !canEdit) return;
    setSaving(true);
    setError('');
    try {
      await deactivateMetaCreativeLink(token, linkId);
      await loadLinks();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không gỡ được link');
    } finally {
      setSaving(false);
    }
  }

  return (
    <div style={{ marginTop: '0.25rem' }}>
      <button type="button" className="btn btn-sm btn-ghost" onClick={() => setOpen((v) => !v)}>
        {open ? 'Đóng Meta ad link' : 'Meta ad link'}
      </button>
      {open ? (
        <div
          className="card"
          style={{ marginTop: '0.5rem', padding: '0.65rem', display: 'grid', gap: '0.45rem' }}
        >
          <strong style={{ fontSize: '0.85rem' }}>{creativeTitle}</strong>
          <p className="muted" style={{ margin: 0, fontSize: '0.8rem' }}>
            Registry B12: gắn <code>external_ad_id</code> ↔ creative đã duyệt.
          </p>
          {loading ? <p className="muted" style={{ margin: 0 }}>Đang tải link…</p> : null}
          {error ? <p className="error" style={{ margin: 0 }}>{error}</p> : null}
          {links.length > 0 ? (
            <ul style={{ margin: 0, paddingLeft: '1.1rem', fontSize: '0.82rem' }}>
              {links.map((link) => (
                <li key={link.id}>
                  Ad <code>{link.external_ad_id}</code>
                  {link.external_campaign_id ? ` · campaign ${link.external_campaign_id}` : ''}
                  {' · '}
                  <MetaEditAdLink
                    clientId={clientId}
                    externalAdId={link.external_ad_id}
                    className="nav-link"
                  />
                  {canEdit ? (
                    <>
                      {' · '}
                      <button
                        type="button"
                        className="btn btn-sm btn-ghost"
                        disabled={saving}
                        onClick={() => void onDeactivate(link.id)}
                      >
                        Gỡ
                      </button>
                    </>
                  ) : null}
                </li>
              ))}
            </ul>
          ) : (
            <p className="muted" style={{ margin: 0, fontSize: '0.82rem' }}>Chưa có ad link.</p>
          )}
          {canEdit ? (
            <form onSubmit={(e) => void onSubmit(e)} style={{ display: 'grid', gap: '0.35rem' }}>
              <input
                placeholder="Meta external_ad_id"
                value={externalAdId}
                onChange={(e) => setExternalAdId(e.target.value)}
                required
                style={{
                  background: 'var(--bg)',
                  border: '1px solid var(--border)',
                  borderRadius: 8,
                  padding: '0.4rem 0.55rem',
                }}
              />
              <input
                placeholder="Ghi chú (tuỳ chọn)"
                value={note}
                onChange={(e) => setNote(e.target.value)}
                style={{
                  background: 'var(--bg)',
                  border: '1px solid var(--border)',
                  borderRadius: 8,
                  padding: '0.4rem 0.55rem',
                }}
              />
              <button type="submit" className="btn btn-sm" disabled={saving}>
                Gắn ad_id
              </button>
            </form>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
