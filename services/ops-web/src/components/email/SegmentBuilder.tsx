'use client';

import { useEffect, useState } from 'react';
import type { EmailSegmentComputeResult, EmailSegmentRow } from '@/lib/api';
import { EmailEmptyState } from './EmailEmptyState';

const LIFECYCLE_OPTIONS = [
  { value: '', label: 'Tất cả contacts' },
  { value: 'subscriber', label: 'Subscriber' },
  { value: 'lead', label: 'Lead' },
  { value: 'customer', label: 'Customer' },
  { value: 'lapsed', label: 'Lapsed' },
];

export function SegmentBuilder({
  segments,
  selectedId,
  clientId,
  canWrite,
  onSelect,
  onCreate,
  onSave,
  onCompute,
  onDuplicate,
}: {
  segments: EmailSegmentRow[];
  selectedId: string | null;
  clientId: string;
  canWrite: boolean;
  onSelect: (id: string | null) => void;
  onCreate: (payload: {
    name: string;
    segment_type: string;
    definition_json: Record<string, unknown>;
  }) => Promise<EmailSegmentRow>;
  onSave: (
    segmentId: string,
    payload: { name: string; segment_type: string; definition_json: Record<string, unknown> },
  ) => Promise<void>;
  onCompute: (segmentId: string) => Promise<EmailSegmentComputeResult>;
  onDuplicate: (segment: EmailSegmentRow) => Promise<EmailSegmentRow>;
}) {
  const selected = segments.find((s) => s.id === selectedId) ?? null;

  const [name, setName] = useState('');
  const [segmentType, setSegmentType] = useState('dynamic');
  const [lifecycleStage, setLifecycleStage] = useState('');
  const [saving, setSaving] = useState(false);
  const [computing, setComputing] = useState(false);
  const [preview, setPreview] = useState<EmailSegmentComputeResult | null>(null);
  const [builderTab, setBuilderTab] = useState<'rules' | 'static'>('rules');

  useEffect(() => {
    if (!selected) {
      setName('');
      setSegmentType('dynamic');
      setLifecycleStage('');
      setPreview(null);
      return;
    }
    setName(selected.name);
    setSegmentType(selected.segment_type || 'dynamic');
    const def = selected.definition_json ?? {};
    setLifecycleStage(typeof def.lifecycle_stage === 'string' ? def.lifecycle_stage : '');
    setPreview(null);
  }, [selected]);

  function buildDefinition(): Record<string, unknown> {
    if (segmentType === 'static') {
      return { contact_ids: [] };
    }
    const def: Record<string, unknown> = {};
    if (lifecycleStage) def.lifecycle_stage = lifecycleStage;
    return def;
  }

  async function createSegment() {
    if (!clientId.trim() || !name.trim()) return;
    setSaving(true);
    try {
      const row = await onCreate({
        name: name.trim(),
        segment_type: segmentType,
        definition_json: buildDefinition(),
      });
      onSelect(row.id);
    } finally {
      setSaving(false);
    }
  }

  async function saveDefinition() {
    if (!selected) return;
    setSaving(true);
    try {
      await onSave(selected.id, {
        name: name.trim() || selected.name,
        segment_type: segmentType,
        definition_json: buildDefinition(),
      });
    } finally {
      setSaving(false);
    }
  }

  async function computeNow() {
    if (!selected) return;
    setComputing(true);
    try {
      const out = await onCompute(selected.id);
      setPreview(out);
    } finally {
      setComputing(false);
    }
  }

  async function duplicateSelected() {
    if (!selected) return;
    setSaving(true);
    try {
      const row = await onDuplicate(selected);
      onSelect(row.id);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="email-segment-builder">
      <div className="email-segment-list-pane card">
        <div className="email-segment-list-head">
          <h3 style={{ margin: 0, fontSize: '1rem' }}>Segment list</h3>
          {canWrite ? (
            <button type="button" className="btn btn-sm" disabled={!clientId.trim() || saving} onClick={() => void createSegment()}>
              + Tạo
            </button>
          ) : null}
        </div>
        {segments.length === 0 ? (
          <EmailEmptyState message="Chưa có phân khúc cho client này." />
        ) : (
          <ul className="email-segment-list">
            {segments.map((s) => (
              <li key={s.id}>
                <button
                  type="button"
                  className={selectedId === s.id ? 'active' : undefined}
                  onClick={() => onSelect(s.id)}
                >
                  <span className="email-segment-list-name">{s.name}</span>
                  <span className="email-segment-list-count">{s.member_count.toLocaleString()}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
        {selected && canWrite ? (
          <div className="email-segment-list-actions">
            <button type="button" className="btn btn-sm" disabled={computing} onClick={() => void computeNow()}>
              {computing ? '…' : 'Compute now'}
            </button>
            <button type="button" className="btn btn-secondary btn-sm" disabled={saving} onClick={() => void duplicateSelected()}>
              Duplicate
            </button>
          </div>
        ) : null}
      </div>

      <div className="email-segment-editor-pane card">
        {!selected ? (
          <EmailEmptyState message="Chọn segment bên trái hoặc tạo mới." />
        ) : (
          <>
            <h3 style={{ marginTop: 0, fontSize: '1rem' }}>Builder ({selected.segment_type})</h3>
            <nav className="email-builder-tabs" aria-label="Builder tabs">
              <button type="button" className={builderTab === 'rules' ? 'active' : undefined} onClick={() => setBuilderTab('rules')}>
                Rules
              </button>
              <button type="button" className={builderTab === 'static' ? 'active' : undefined} onClick={() => setBuilderTab('static')}>
                Static upload
              </button>
              <button type="button" disabled title="Phase 3">
                Lifecycle
              </button>
              <button type="button" disabled title="Phase 3">
                RFM
              </button>
            </nav>

            {canWrite ? (
              <label style={{ display: 'block', marginBottom: '0.75rem' }}>
                Tên segment
                <input value={name} onChange={(e) => setName(e.target.value)} style={{ display: 'block', width: '100%', marginTop: '0.25rem' }} />
              </label>
            ) : (
              <p className="muted">{selected.name}</p>
            )}

            <label style={{ display: 'block', marginBottom: '0.75rem' }}>
              Type
              <select
                value={segmentType}
                disabled={!canWrite}
                onChange={(e) => setSegmentType(e.target.value)}
                style={{ display: 'block', width: '100%', marginTop: '0.25rem' }}
              >
                <option value="dynamic">Dynamic</option>
                <option value="static">Static</option>
              </select>
            </label>

            {builderTab === 'rules' && segmentType === 'dynamic' ? (
              <div className="email-segment-rules">
                <p className="muted" style={{ marginTop: 0 }}>Rules</p>
                <label style={{ display: 'block' }}>
                  Lifecycle stage
                  <select
                    value={lifecycleStage}
                    disabled={!canWrite}
                    onChange={(e) => setLifecycleStage(e.target.value)}
                    style={{ display: 'block', width: '100%', marginTop: '0.25rem' }}
                  >
                    {LIFECYCLE_OPTIONS.map((o) => (
                      <option key={o.value || 'all'} value={o.value}>
                        {o.label}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
            ) : null}

            {builderTab === 'static' || segmentType === 'static' ? (
              <p className="muted">
                Static segments dùng danh sách contact_ids trong definition. Import CSV qua Contacts (EM-2).
              </p>
            ) : null}

            {canWrite ? (
              <div style={{ display: 'flex', gap: '0.5rem', marginTop: '1rem', flexWrap: 'wrap' }}>
                <button type="button" className="btn btn-sm" disabled={saving} onClick={() => void saveDefinition()}>
                  {saving ? '…' : 'Lưu rules'}
                </button>
                <button type="button" className="btn btn-secondary btn-sm" disabled={computing} onClick={() => void computeNow()}>
                  Preview / Compute
                </button>
              </div>
            ) : null}

            <div className="email-segment-preview-panel">
              <p style={{ margin: '1rem 0 0.35rem', fontWeight: 600 }}>Preview</p>
              <p className="muted" style={{ margin: 0 }}>
                Contacts:{' '}
                <strong>{(preview?.member_count ?? selected.member_count).toLocaleString()}</strong>
              </p>
              {preview ? (
                <>
                  <p className="muted" style={{ margin: '0.35rem 0 0' }}>
                    Excluded by suppression: <strong>{preview.excluded_suppression}</strong>
                  </p>
                  <p className="muted" style={{ margin: '0.35rem 0 0' }}>
                    Excluded by consent: <strong>{preview.excluded_consent}</strong>
                  </p>
                </>
              ) : selected.last_computed_at ? (
                <p className="muted" style={{ margin: '0.35rem 0 0', fontSize: '0.8125rem' }}>
                  Last computed: {selected.last_computed_at.slice(0, 16).replace('T', ' ')}
                </p>
              ) : (
                <p className="muted" style={{ margin: '0.35rem 0 0', fontSize: '0.8125rem' }}>
                  Chưa compute — bấm Preview / Compute
                </p>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
