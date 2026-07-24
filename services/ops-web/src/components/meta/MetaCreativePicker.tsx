'use client';

interface CreativePickRow {
  id: string;
  title: string;
  status: string;
  version?: number;
  external_campaign_id?: string | null;
  asset_url?: string | null;
}

interface MetaCreativePickerProps {
  creatives: CreativePickRow[];
  selectedId: string;
  onSelect: (creativeSubmissionId: string) => void;
  loading?: boolean;
}

export function MetaCreativePicker({ creatives, selectedId, onSelect, loading }: MetaCreativePickerProps) {
  const approved = creatives.filter((c) => c.status === 'approved');

  return (
    <div className="card">
      <h3 style={{ marginTop: 0 }}>Chọn creative đã approved</h3>
      <p className="muted" style={{ marginTop: 0 }}>
        Chỉ creative <code>approved</code> từ CRM inbox mới được launch/edit.
      </p>
      {loading ? <p className="muted">Đang tải creatives…</p> : null}
      {!loading && approved.length === 0 ? (
        <p className="muted">Không có creative approved · duyệt tại /crm/creatives</p>
      ) : null}
      <div style={{ display: 'grid', gap: '0.75rem' }}>
        {approved.map((creative) => (
          <label
            key={creative.id}
            style={{
              display: 'flex',
              gap: '0.75rem',
              alignItems: 'flex-start',
              padding: '0.75rem',
              border: `1px solid ${selectedId === creative.id ? 'var(--accent, #2563eb)' : 'var(--border, #ddd)'}`,
              borderRadius: '8px',
              cursor: 'pointer',
            }}
          >
            <input
              type="radio"
              name="creative_pick"
              checked={selectedId === creative.id}
              onChange={() => onSelect(creative.id)}
            />
            <div>
              <strong>{creative.title || creative.id.slice(0, 8)}</strong>
              <div className="muted" style={{ fontSize: '0.9rem' }}>
                v{creative.version ?? 1} · {creative.external_campaign_id ?? '—'}
              </div>
              {creative.asset_url ? (
                <div className="muted" style={{ fontSize: '0.85rem', wordBreak: 'break-all' }}>
                  {creative.asset_url}
                </div>
              ) : null}
            </div>
          </label>
        ))}
      </div>
    </div>
  );
}
