'use client';

import { useState } from 'react';
import type { ConversionRuleRow } from '@/lib/meta/types';

interface Props {
  rules: ConversionRuleRow[];
  canConfigure: boolean;
  saving: boolean;
  onToggle: (ruleId: string, enabled: boolean) => void;
  onCreate: (body: {
    lead_status: string;
    event_name: string;
    client_id?: string | null;
    enabled?: boolean;
  }) => void;
}

export function MetaConversionRulesTable({ rules, canConfigure, saving, onToggle, onCreate }: Props) {
  const [leadStatus, setLeadStatus] = useState('qualified');
  const [eventName, setEventName] = useState('CompleteRegistration');

  return (
    <div className="card meta-tracking-section">
      <h2 className="meta-tracking-section-title">Conversion rules</h2>
      {canConfigure ? (
        <form
          className="meta-tracking-rules-form"
          onSubmit={(e) => {
            e.preventDefault();
            onCreate({ lead_status: leadStatus.trim(), event_name: eventName.trim(), enabled: true });
          }}
        >
          <label>
            <span className="muted">Lead status</span>
            <input value={leadStatus} onChange={(e) => setLeadStatus(e.target.value)} />
          </label>
          <label>
            <span className="muted">Event name</span>
            <input value={eventName} onChange={(e) => setEventName(e.target.value)} />
          </label>
          <button type="submit" className="btn btn-sm" disabled={saving}>
            Thêm rule
          </button>
        </form>
      ) : null}
      <div style={{ overflowX: 'auto' }}>
        <table className="perf-table meta-tracking-table">
          <thead>
            <tr>
              <th>Scope</th>
              <th>Status</th>
              <th>Event</th>
              <th>Value VND</th>
              <th>Enabled</th>
            </tr>
          </thead>
          <tbody>
            {rules.map((rule) => (
              <tr key={rule.id}>
                <td>{rule.client_id ? rule.client_id.slice(0, 8) : 'Global'}</td>
                <td>{rule.lead_status}</td>
                <td>{rule.event_name}</td>
                <td>{rule.value_vnd.toLocaleString('vi-VN')}</td>
                <td>
                  {canConfigure ? (
                    <input
                      type="checkbox"
                      checked={rule.enabled}
                      disabled={saving}
                      onChange={(e) => onToggle(rule.id, e.target.checked)}
                    />
                  ) : rule.enabled ? (
                    '✓'
                  ) : (
                    '—'
                  )}
                </td>
              </tr>
            ))}
            {!rules.length ? (
              <tr>
                <td colSpan={5} className="muted">
                  Chưa có conversion rules
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </div>
  );
}
