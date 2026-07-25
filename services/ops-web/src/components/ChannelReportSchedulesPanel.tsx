'use client';

import { useCallback, useEffect, useState } from 'react';
import {
  createChannelReportSchedule,
  deleteChannelReportSchedule,
  fetchChannelReportSchedules,
  runChannelReportSchedule,
  type ChannelReportScheduleRow,
} from '@/lib/api';

interface ChannelReportSchedulesPanelProps {
  channel: 'meta' | 'zalo';
  token: string;
  clientId: string;
}

export function ChannelReportSchedulesPanel({ channel, token, clientId }: ChannelReportSchedulesPanelProps) {
  const [rows, setRows] = useState<ChannelReportScheduleRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [msg, setMsg] = useState('');
  const [email, setEmail] = useState('');
  const [tableReady, setTableReady] = useState(true);

  const load = useCallback(async () => {
    if (!clientId.trim()) {
      setRows([]);
      return;
    }
    setLoading(true);
    setMsg('');
    try {
      const data = await fetchChannelReportSchedules(token, channel, clientId);
      setRows(data.items ?? []);
      setTableReady(data.table_ready !== false);
    } catch (err) {
      setMsg(err instanceof Error ? err.message : 'Không tải được lịch báo cáo');
    } finally {
      setLoading(false);
    }
  }, [channel, clientId, token]);

  useEffect(() => {
    void load();
  }, [load]);

  async function handleCreate() {
    const recipient = email.trim();
    if (!recipient || !clientId.trim()) return;
    setMsg('');
    try {
      await createChannelReportSchedule(token, channel, {
        client_id: clientId,
        recipient_emails: [recipient],
        cadence: 'weekly',
        export_format: 'pdf',
        window_days: 7,
        portal_link_enabled: true,
      });
      setEmail('');
      await load();
      setMsg('Đã tạo lịch weekly PDF + portal link.');
    } catch (err) {
      setMsg(err instanceof Error ? err.message : 'Tạo lịch thất bại');
    }
  }

  return (
    <section className="card" style={{ marginTop: '1.25rem', padding: '1rem 1.25rem' }}>
      <h2 style={{ margin: '0 0 0.5rem', fontSize: '1.05rem' }}>
        Lịch báo cáo {channel === 'meta' ? 'Meta' : 'Zalo'} (PDF/CSV email)
      </h2>
      <p className="muted" style={{ margin: '0 0 1rem' }}>
        Gửi tự động weekly — pre-send gate: unmapped=0 và sync T-1 xanh.
      </p>
      {!tableReady ? (
        <p className="muted">Bảng schedule chưa migrate — chạy DDL Prod-S2 trên DB.</p>
      ) : null}
      {!clientId.trim() ? (
        <p className="muted">Chọn client ở filter phía trên để cấu hình lịch.</p>
      ) : (
        <>
          <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', marginBottom: '1rem' }}>
            <input
              type="email"
              placeholder="email@client.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              style={{ minWidth: 220 }}
            />
            <button type="button" className="btn" onClick={() => void handleCreate()}>
              Thêm lịch weekly
            </button>
          </div>
          {msg ? <p className="muted">{msg}</p> : null}
          {loading ? (
            <p className="muted">Đang tải…</p>
          ) : rows.length === 0 ? (
            <p className="muted">Chưa có lịch cho client này.</p>
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Format</th>
                  <th>Cadence</th>
                  <th>Recipients</th>
                  <th>Next run</th>
                  <th>Last sent</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.id}>
                    <td>{row.export_format.toUpperCase()}</td>
                    <td>{row.cadence}</td>
                    <td>{row.recipient_emails.join(', ') || '—'}</td>
                    <td>{row.next_run_at ?? '—'}</td>
                    <td>{row.last_sent_at ? new Date(row.last_sent_at).toLocaleString('vi-VN') : '—'}</td>
                    <td style={{ display: 'flex', gap: '0.35rem' }}>
                      <button
                        type="button"
                        className="btn btn-secondary"
                        onClick={() =>
                          void runChannelReportSchedule(token, channel, row.id)
                            .then(() => setMsg(`Đã enqueue run ${row.id.slice(0, 8)}`))
                            .catch((err) => setMsg(err instanceof Error ? err.message : 'Run failed'))
                        }
                      >
                        Run now
                      </button>
                      <button
                        type="button"
                        className="btn btn-secondary"
                        onClick={() =>
                          void deleteChannelReportSchedule(token, channel, row.id)
                            .then(load)
                            .catch((err) => setMsg(err instanceof Error ? err.message : 'Delete failed'))
                        }
                      >
                        Xóa
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </>
      )}
    </section>
  );
}
