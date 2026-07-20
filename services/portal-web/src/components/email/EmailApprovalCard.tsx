'use client';

import { useEffect, useRef, useState } from 'react';
import { trapFocus } from '@/lib/email-a11y';
import { useToast } from '@/lib/toast';
import { portalEmailApprovalPreview, type PortalEmailApprovalPreview, type PortalEmailApprovalRow } from '@/lib/api';
import { getToken } from '@/lib/auth';

export function EmailApprovalCard({
  item,
  canAct,
  onApprove,
  onReject,
}: {
  item: PortalEmailApprovalRow;
  canAct: boolean;
  onApprove: (campaignId: string) => Promise<void>;
  onReject: (campaignId: string, note: string) => Promise<void>;
}) {
  const { push } = useToast();
  const [rejectOpen, setRejectOpen] = useState(false);
  const [previewOpen, setPreviewOpen] = useState(false);
  const [preview, setPreview] = useState<PortalEmailApprovalPreview | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState(false);
  const rejectRef = useRef<HTMLDivElement>(null);
  const previewRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!rejectOpen || !rejectRef.current) return;
    return trapFocus(rejectRef.current);
  }, [rejectOpen]);

  useEffect(() => {
    if (!previewOpen || !previewRef.current) return;
    return trapFocus(previewRef.current);
  }, [previewOpen, preview]);

  useEffect(() => {
    if (!rejectOpen && !previewOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setRejectOpen(false);
        setPreviewOpen(false);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [rejectOpen, previewOpen]);

  async function openPreview() {
    const token = getToken();
    if (!token) return;
    setPreviewLoading(true);
    setPreviewOpen(true);
    try {
      const data = await portalEmailApprovalPreview(token, item.campaign_id);
      setPreview(data);
    } catch (err) {
      setPreviewOpen(false);
      push(err instanceof Error ? err.message : 'Tải preview thất bại', 'error');
    } finally {
      setPreviewLoading(false);
    }
  }

  async function approve() {
    setBusy(true);
    try {
      await onApprove(item.campaign_id);
      push('Đã phê duyệt campaign', 'success');
    } catch (err) {
      push(err instanceof Error ? err.message : 'Phê duyệt thất bại', 'error');
    } finally {
      setBusy(false);
    }
  }

  async function confirmReject() {
    setBusy(true);
    try {
      await onReject(item.campaign_id, note.trim());
      push('Đã từ chối campaign', 'info');
      setRejectOpen(false);
      setNote('');
    } catch (err) {
      push(err instanceof Error ? err.message : 'Từ chối thất bại', 'error');
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <article className="email-approval-card card">
        <header className="email-approval-card-head">
          <strong>{item.name}</strong>
          <span className={`email-status-badge email-status-${(item.status || 'pending_approval').toLowerCase().replace(/\s+/g, '_')}`}>
            {item.status}
          </span>
        </header>
        <p className="muted" style={{ margin: '0.35rem 0' }}>
          Template: {item.template_name}
          {item.audience_count != null ? ` · Audience ${item.audience_count.toLocaleString()}` : ''}
        </p>
        <p className="muted" style={{ margin: '0 0 0.75rem', fontSize: '0.8125rem' }}>
          Requested: {item.requested_at.slice(0, 16).replace('T', ' ')}
        </p>
        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
          <button type="button" className="btn btn-secondary btn-sm" disabled={previewLoading} onClick={() => void openPreview()}>
            Preview email
          </button>
          {canAct ? (
            <>
              <button type="button" className="btn btn-sm" disabled={busy} onClick={() => void approve()}>
                Phê duyệt gửi
              </button>
              <button type="button" className="btn btn-secondary btn-sm" disabled={busy} onClick={() => setRejectOpen(true)}>
                Từ chối
              </button>
            </>
          ) : null}
        </div>
      </article>

      {previewOpen ? (
        <div className="email-modal-backdrop" role="presentation" onClick={() => setPreviewOpen(false)}>
          <div
            ref={previewRef}
            className="email-modal card email-preview-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby={`preview-title-${item.campaign_id}`}
            onClick={(e) => e.stopPropagation()}
          >
            <h2 id={`preview-title-${item.campaign_id}`} style={{ marginTop: 0, fontSize: '1.1rem' }}>
              Preview email
            </h2>
            {previewLoading || !preview ? (
              <p className="muted">Đang tải preview…</p>
            ) : (
              <>
                <p className="muted" style={{ marginTop: 0 }}>
                  <strong>{preview.name}</strong>
                  {preview.scheduled_at ? ` · Scheduled ${preview.scheduled_at.slice(0, 16).replace('T', ' ')}` : ''}
                </p>
                <p className="muted" style={{ margin: '0 0 0.75rem' }}>
                  Subject: {preview.subject_template}
                </p>
                <div className="email-preview-frame">
                  <iframe title="Xem trước email" srcDoc={preview.html_body} sandbox="" />
                </div>
                <p className="muted" style={{ margin: '0.75rem 0 0', fontSize: '0.8125rem' }}>
                  Audience: {preview.audience_count?.toLocaleString() ?? '—'} contacts
                </p>
              </>
            )}
            <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '1rem' }}>
              <button type="button" className="btn btn-secondary btn-sm" onClick={() => setPreviewOpen(false)}>
                Đóng
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {rejectOpen ? (
        <div className="email-modal-backdrop" role="presentation" onClick={() => setRejectOpen(false)}>
          <div
            ref={rejectRef}
            className="email-modal card"
            role="dialog"
            aria-modal="true"
            aria-labelledby={`reject-title-${item.campaign_id}`}
            onClick={(e) => e.stopPropagation()}
          >
            <h2 id={`reject-title-${item.campaign_id}`} style={{ marginTop: 0, fontSize: '1.1rem' }}>
              Từ chối campaign
            </h2>
            <p className="muted" style={{ marginTop: 0 }}>
              {item.name}
            </p>
            <label style={{ display: 'block', marginBottom: '1rem' }}>
              Lý do (optional)
              <textarea
                value={note}
                onChange={(e) => setNote(e.target.value)}
                rows={3}
                style={{ display: 'block', width: '100%', marginTop: '0.35rem' }}
                placeholder="Ví dụ: cần chỉnh subject line…"
              />
            </label>
            <div style={{ display: 'flex', gap: '0.5rem', justifyContent: 'flex-end' }}>
              <button type="button" className="btn btn-secondary btn-sm" disabled={busy} onClick={() => setRejectOpen(false)}>
                Hủy
              </button>
              <button type="button" className="btn btn-sm" disabled={busy} onClick={() => void confirmReject()}>
                Xác nhận từ chối
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </>
  );
}
