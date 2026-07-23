'use client';

import Link from 'next/link';
import { useCallback, useEffect, useState } from 'react';
import { fetchServiceLifecycleSop, type SopRunRow } from '@/lib/api';

type SopPayload = {
  lifecycle_id: number;
  sop_run_id: number | null;
  auto_start_enabled: boolean;
  template_code: string;
  run: SopRunRow | null;
  tasks: Array<{
    id: number;
    position: number;
    title: string;
    role: string;
    due_date: string;
    status: string;
  }>;
  message?: string | null;
};

interface Props {
  token: string;
  lifecycleId: number;
}

const STATUS_LABEL: Record<string, string> = {
  todo: 'Chưa làm',
  in_progress: 'Đang làm',
  done: 'Xong',
  skipped: 'Bỏ qua',
};

export function LifecycleSopPanel({ token, lifecycleId }: Props) {
  const [data, setData] = useState<SopPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const reload = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const out = await fetchServiceLifecycleSop(token, lifecycleId);
      setData(out);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Tải SOP thất bại');
    } finally {
      setLoading(false);
    }
  }, [token, lifecycleId]);

  useEffect(() => {
    void reload();
  }, [reload]);

  if (loading) return <p className="muted">Đang tải SOP Launch…</p>;
  if (error) return <p className="error">{error}</p>;
  if (!data) return null;

  const run = data.run;
  const stats = run?.stats;

  return (
    <div className="card" style={{ padding: '1rem', display: 'grid', gap: '0.85rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: '0.75rem', flexWrap: 'wrap' }}>
        <div>
          <h3 style={{ margin: 0, fontSize: '1rem' }}>SOP Launch</h3>
          <p className="muted" style={{ margin: '0.35rem 0 0', fontSize: '0.85rem' }}>
            Template: {data.template_code}
            {data.auto_start_enabled ? ' · Auto-start bật' : ' · Auto-start tắt'}
          </p>
        </div>
        <Link href="/crm/sop" className="nav-link" style={{ fontSize: '0.9rem' }}>
          Mở hub SOP →
        </Link>
      </div>

      {!run ? (
        <p className="muted" style={{ margin: 0 }}>
          {data.message ?? 'Chưa có SOP run cho lifecycle này.'}
        </p>
      ) : (
        <>
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))',
              gap: '0.5rem',
            }}
          >
            <div>
              <div className="muted" style={{ fontSize: '0.75rem' }}>
                Run
              </div>
              <div style={{ fontWeight: 600 }}>
                #{run.id} · {run.status}
              </div>
            </div>
            <div>
              <div className="muted" style={{ fontSize: '0.75rem' }}>
                Tiến độ
              </div>
              <div style={{ fontWeight: 600 }}>
                {stats?.done ?? 0}/{stats?.total ?? 0} xong
              </div>
            </div>
            <div>
              <div className="muted" style={{ fontSize: '0.75rem' }}>
                Quá hạn
              </div>
              <div style={{ fontWeight: 600, color: (stats?.overdue ?? 0) > 0 ? 'var(--danger)' : undefined }}>
                {stats?.overdue ?? 0}
              </div>
            </div>
            <div>
              <div className="muted" style={{ fontSize: '0.75rem' }}>
                Bắt đầu
              </div>
              <div>{run.start_date || '—'}</div>
            </div>
          </div>

          <p style={{ margin: 0, fontSize: '0.9rem' }}>
            <strong>{run.name}</strong>
            {run.template_name ? (
              <span className="muted"> · {run.template_name}</span>
            ) : null}
            {run.campaign_name ? (
              <span className="muted"> · CD: {run.campaign_name}</span>
            ) : null}
          </p>

          {data.tasks.length > 0 ? (
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
                <thead>
                  <tr className="muted">
                    <th style={{ textAlign: 'left', padding: '0.35rem' }}>#</th>
                    <th style={{ textAlign: 'left', padding: '0.35rem' }}>Task</th>
                    <th style={{ textAlign: 'left', padding: '0.35rem' }}>Role</th>
                    <th style={{ textAlign: 'left', padding: '0.35rem' }}>Hạn</th>
                    <th style={{ textAlign: 'left', padding: '0.35rem' }}>Trạng thái</th>
                  </tr>
                </thead>
                <tbody>
                  {data.tasks.map((task) => (
                    <tr key={task.id} style={{ borderTop: '1px solid var(--border)' }}>
                      <td style={{ padding: '0.35rem' }}>{task.position + 1}</td>
                      <td style={{ padding: '0.35rem' }}>{task.title}</td>
                      <td style={{ padding: '0.35rem' }}>{task.role || '—'}</td>
                      <td style={{ padding: '0.35rem' }}>{task.due_date || '—'}</td>
                      <td style={{ padding: '0.35rem' }}>{STATUS_LABEL[task.status] ?? task.status}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="muted" style={{ margin: 0 }}>
              Run chưa có task — kiểm tra template {data.template_code}.
            </p>
          )}
        </>
      )}
    </div>
  );
}
