'use client';

import { useEffect, useMemo, useState } from 'react';
import type { FacebookAdsMigrationStatus } from '@/lib/api';

type GateState = 'pass' | 'pending' | 'warn';

interface MigrationGateRow {
  id: string;
  label: string;
  state: GateState;
  detail: string;
}

interface UatRow {
  id: string;
  label: string;
  note: string;
}

const RUNBOOK_PATH = 'docs/runbooks/horizon1-meta-ads-migration-checklist.md';

const UAT_ROWS: UatRow[] = [
  {
    id: 'E1',
    label: 'Staff login → hub load CPL + bảng client',
    note: 'manual_uat.ops_web_hub_cpl_summary',
  },
  {
    id: 'E2',
    label: 'Meta test webhook → lead CRM ≤ 5 phút',
    note: 'manual_uat.webhook_test_lead_created',
  },
  {
    id: 'E3',
    label: 'Autosync một process (không duplicate Gunicorn)',
    note: 'manual_uat.autosync_single_process',
  },
  {
    id: 'E4',
    label: 'Portal Meta read-only — số khớp hub',
    note: 'manual_uat.portal_meta_readonly',
  },
  {
    id: 'E5',
    label: 'Campaign write approve smoke (nếu B4)',
    note: 'manual_uat.campaign_write_approve_smoke',
  },
];

function gatePillClass(state: GateState): string {
  if (state === 'pass') return 'meta-migration-pill meta-migration-pill--pass';
  if (state === 'warn') return 'meta-migration-pill meta-migration-pill--warn';
  return 'meta-migration-pill meta-migration-pill--pending';
}

function gateLabel(state: GateState): string {
  if (state === 'pass') return 'PASS';
  if (state === 'warn') return 'WARN';
  return 'PENDING';
}

function buildGateRows(status: FacebookAdsMigrationStatus): MigrationGateRow[] {
  const nestWebhook = status.webhooks_nest_meta === true;
  const flaskFallback = status.webhooks_flask_fallback === true;
  const g04Pass = nestWebhook && !flaskFallback;

  let g06Detail = 'Chưa cấu hình redirect nginx';
  let g06State: GateState = 'pending';
  if (status.gate_m1_g06) {
    g06State = 'pass';
    g06Detail = 'Config + live verify OK';
  } else if (status.gate_m1_g06_config && status.nginx_redirect_live_skipped) {
    g06State = 'warn';
    g06Detail = 'Config OK — chưa verify live (HORIZON1_SKIP_NGINX_REDIRECT_VERIFY=1)';
  } else if (status.gate_m1_g06_config) {
    g06State = 'warn';
    g06Detail = 'Config OK — live redirect chưa PASS';
  } else if (status.nginx_deploy_config_ok) {
    g06Detail = 'Snippet deploy có — chưa đủ điều kiện gate';
  }

  let g11Detail = 'Chưa chạy dry-run B3.5';
  let g11State: GateState = 'pending';
  if (status.gate_m1_g11) {
    g11State = 'pass';
    g11Detail = 'Artifact dry-run OK (M1-G11)';
  } else if (status.retirement_dry_run_artifact_present === false) {
    g11Detail = 'Chạy: ./scripts/wave_b3_5_deploy.sh';
  } else if (typeof status.retirement_env_pending_changes === 'number' && status.retirement_env_pending_changes > 0) {
    g11State = 'warn';
    g11Detail = `${status.retirement_env_pending_changes} env flag chờ APPLY (B3.6)`;
  } else if (status.retirement_env_already_applied) {
    g11State = 'warn';
    g11Detail = 'Env đã apply — chờ verify artifact';
  }

  let g12Detail = 'Chưa APPLY prod B3.6';
  let g12State: GateState = 'pending';
  if (status.gate_m1_g12) {
    g12State = 'pass';
    g12Detail = 'Prod retirement APPLY OK (M1-G12)';
  } else if (status.retirement_apply_artifact_present === false && status.flask_meta_ads_admin_retired) {
    g12Detail = 'Chạy: sudo -E APPLY=1 ./scripts/wave_b3_6_deploy.sh';
  }

  return [
    {
      id: 'M1-G04',
      label: 'Webhook Nest-only (không Flask fallback)',
      state: g04Pass ? 'pass' : nestWebhook ? 'warn' : 'pending',
      detail: g04Pass
        ? 'PTT_WEBHOOKS_NEST_META=1, fallback tắt'
        : flaskFallback
          ? 'PTT_WEBHOOKS_FLASK_FALLBACK vẫn bật'
          : 'PTT_WEBHOOKS_NEST_META chưa bật',
    },
    {
      id: 'M1-G06',
      label: 'nginx redirect /crm/facebook-ads → ops-web',
      state: g06State,
      detail: g06Detail,
    },
    {
      id: 'M1-G09',
      label: 'Flask Meta hub retired (env flag)',
      state: status.gate_m1_g09 ? 'pass' : 'pending',
      detail: status.gate_m1_g09
        ? 'PTT_FLASK_META_ADS_ADMIN_RETIRED=1'
        : 'Staff vẫn có thể dùng Flask hub trên rs.pttads.vn',
    },
    {
      id: 'M1-G11',
      label: 'Retirement dry-run preflight',
      state: g11State,
      detail: g11Detail,
    },
    {
      id: 'M1-G12',
      label: 'Retirement prod APPLY',
      state: g12State,
      detail: g12Detail,
    },
  ];
}

function countPassed(rows: MigrationGateRow[]): number {
  return rows.filter((r) => r.state === 'pass').length;
}

interface MetaMigrationPanelProps {
  status: FacebookAdsMigrationStatus;
}

export function MetaMigrationPanel({ status }: MetaMigrationPanelProps) {
  const gates = useMemo(() => buildGateRows(status), [status]);
  const passed = countPassed(gates);
  const total = gates.length;
  const allPassed = passed === total;
  const progressPct = total ? Math.round((passed / total) * 100) : 0;

  const [collapsed, setCollapsed] = useState(false);
  const [showUat, setShowUat] = useState(false);
  const [showOps, setShowOps] = useState(false);

  useEffect(() => {
    if (window.localStorage.getItem('meta-migration-panel-collapsed') === '1') {
      setCollapsed(true);
    }
  }, []);

  function toggleCollapsed() {
    setCollapsed((prev) => {
      const next = !prev;
      if (typeof window !== 'undefined') {
        window.localStorage.setItem('meta-migration-panel-collapsed', next ? '1' : '0');
      }
      return next;
    });
  }

  const canonical =
    status.canonical_upstream === 'ops-web'
      ? 'ops-web (canonical)'
      : status.flask_meta_ads_admin_retired
        ? 'ops-web'
        : 'Flask rs.pttads.vn (legacy)';

  const applyCmd =
    status.retirement_next_apply_command ?? 'sudo -E APPLY=1 ./scripts/close_flask_retirement_meta_ads.sh';

  return (
    <section
      className={`card meta-migration-panel${allPassed ? ' meta-migration-panel--complete' : ''}`}
      aria-label="Horizon 1 Meta Ads migration"
    >
      <header className="meta-migration-header">
        <div>
          <p className="meta-migration-kicker">Horizon 1</p>
          <h2 className="meta-migration-title">Meta Ads migration</h2>
          <p className="muted meta-migration-subtitle">
            Hub: <strong>{canonical}</strong>
            {status.legacy_rs_path ? (
              <>
                {' '}
                · Legacy{' '}
                <code>{status.legacy_rs_path}</code>
                {status.gate_m1_g06 ? ' → redirect ops-web' : ''}
              </>
            ) : null}
          </p>
        </div>
        <div className="meta-migration-header-actions">
          <span className="meta-migration-progress-label">
            {passed}/{total} gates
          </span>
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            onClick={toggleCollapsed}
            aria-expanded={!collapsed}
          >
            {collapsed ? 'Mở panel' : 'Thu gọn'}
          </button>
        </div>
      </header>

      {!collapsed ? (
        <>
          <div
            className="meta-migration-progress"
            role="progressbar"
            aria-valuenow={progressPct}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-label={`Migration gates ${passed} of ${total} passed`}
          >
            <div className="meta-migration-progress-bar" style={{ width: `${progressPct}%` }} />
          </div>

          {allPassed ? (
            <p className="meta-migration-complete-note">
              Các gate tự động đã PASS. Tiếp theo: soak 7 ngày (M1-G08), UAT §E, pilot metrics và human
              sign-off.
            </p>
          ) : (
            <p className="muted meta-migration-hint">
              Panel này đọc từ <code>GET /api/v1/facebook-ads/migration-status</code> — dùng cho staff/QA
              theo dõi cutover; DevOps chạy wave scripts trên VPS.
            </p>
          )}

          <div className="meta-migration-gates">
            <h3 className="meta-migration-section-title">Gates tự động (DevOps)</h3>
            <ul className="meta-migration-gate-list">
              {gates.map((gate) => (
                <li key={gate.id} className="meta-migration-gate-row">
                  <div className="meta-migration-gate-main">
                    <span className="meta-migration-gate-id">{gate.id}</span>
                    <span>{gate.label}</span>
                  </div>
                  <div className="meta-migration-gate-meta">
                    <span className={gatePillClass(gate.state)}>{gateLabel(gate.state)}</span>
                    <span className="muted meta-migration-gate-detail">{gate.detail}</span>
                  </div>
                </li>
              ))}
            </ul>
          </div>

          <details
            className="meta-migration-details"
            open={showUat}
            onToggle={(e) => setShowUat((e.target as HTMLDetailsElement).open)}
          >
            <summary>UAT thủ công (QA) — tham chiếu §E</summary>
            <p className="muted" style={{ marginTop: '0.5rem', fontSize: '0.85rem' }}>
              Ghi kết quả vào <code>docs/evidence/horizon1-meta-ads-signoff.json</code> — panel không thay
              sign-off chính thức.
            </p>
            <ul className="meta-migration-uat-list">
              {UAT_ROWS.map((row) => (
                <li key={row.id}>
                  <span className="meta-migration-uat-id">{row.id}</span>
                  <span>{row.label}</span>
                  <code className="meta-migration-uat-field">{row.note}</code>
                </li>
              ))}
            </ul>
          </details>

          <details
            className="meta-migration-details"
            open={showOps}
            onToggle={(e) => setShowOps((e.target as HTMLDetailsElement).open)}
          >
            <summary>Lệnh DevOps & runbook</summary>
            <dl className="meta-migration-ops-dl">
              <dt>Checklist</dt>
              <dd>
                <code>{RUNBOOK_PATH}</code>
              </dd>
              <dt>Dry-run B3.5</dt>
              <dd>
                <code>./scripts/wave_b3_5_deploy.sh</code>
              </dd>
              <dt>APPLY B3.6</dt>
              <dd>
                <code>{applyCmd}</code>
              </dd>
              <dt>Verify redirect</dt>
              <dd>
                <code>curl -I https://rs.pttads.vn/crm/facebook-ads</code>
              </dd>
              <dt>Soak daily</dt>
              <dd>
                <code>./scripts/horizon1_meta_ads_soak_record.sh</code>
              </dd>
              <dt>Evaluate</dt>
              <dd>
                <code>./scripts/horizon1_meta_ads_pack.sh evaluate</code>
              </dd>
            </dl>
          </details>

          {status.ops_web_hub_url ? (
            <p className="muted meta-migration-footer">
              Canonical URL:{' '}
              <a href={status.ops_web_hub_url} target="_blank" rel="noreferrer">
                {status.ops_web_hub_url}
              </a>
            </p>
          ) : null}
        </>
      ) : null}
    </section>
  );
}
