'use client';

import Link from 'next/link';
import { useEffect, useMemo, useState } from 'react';
import type {
  FacebookAdsMigrationStatus,
  MetaMigrationManualUat,
  MetaMigrationManualUatField,
} from '@/lib/api';

type GateState = 'pass' | 'pending' | 'warn';

interface MigrationGateRow {
  id: string;
  label: string;
  state: GateState;
  detail: string;
}

interface UatRow {
  id: string;
  field: MetaMigrationManualUatField;
  label: string;
}

const RUNBOOK_PATH = 'docs/runbooks/horizon1-meta-ads-migration-checklist.md';

const UAT_ROWS: UatRow[] = [
  { id: 'E1', field: 'ops_web_hub_cpl_summary', label: 'Staff login → hub load CPL + bảng client' },
  { id: 'E2', field: 'webhook_test_lead_created', label: 'Meta test webhook → lead CRM ≤ 5 phút' },
  { id: 'E3', field: 'autosync_single_process', label: 'Autosync một process (không duplicate Gunicorn)' },
  { id: 'E4', field: 'portal_meta_readonly', label: 'Portal Meta read-only — số khớp hub' },
  { id: 'E5', field: 'campaign_write_approve_smoke', label: 'Campaign write approve smoke (nếu B4)' },
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

export function buildMigrationGateRows(status: FacebookAdsMigrationStatus): MigrationGateRow[] {
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

  let g07Detail = 'Autosync chưa standalone';
  let g07State: GateState = 'pending';
  if (status.gate_m1_g07) {
    g07State = 'pass';
    g07Detail = 'Unit systemd + daemon, Gunicorn background tắt';
  } else {
    const parts: string[] = [];
    if (!status.autosync_gunicorn_background_off) parts.push('CRM_FACEBOOK_BACKGROUND_IN_GUNICORN=1');
    if (status.autosync_unit_no_ptt_dependency === false) parts.push('unit vẫn phụ thuộc ptt.service');
    if (!status.autosync_unit_present) parts.push('thiếu deploy/ptt-fb-autosync.service');
    if (parts.length) g07Detail = parts.join(' · ');
  }

  let g08Detail = 'Chưa có soak evidence';
  let g08State: GateState = 'pending';
  if (status.gate_m1_g08) {
    g08State = 'pass';
    g08Detail = `Soak OK · ${status.soak_sample_count ?? 0} mẫu · span ${status.soak_span_days ?? '—'} ngày`;
  } else if (typeof status.soak_sample_count === 'number' && status.soak_sample_count > 0) {
    g08State = 'warn';
    g08Detail = `${status.soak_sample_count}/${status.soak_min_samples ?? 7} mẫu · span ${status.soak_span_days ?? '—'}/${status.soak_required_days ?? 7} ngày`;
    if (status.soak_error) g08Detail += ` (${status.soak_error})`;
  } else if (status.soak_error) {
    g08Detail = status.soak_error;
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
      id: 'M1-G07',
      label: 'Autosync standalone (không trong Gunicorn)',
      state: g07State,
      detail: g07Detail,
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
    {
      id: 'M1-G08',
      label: 'Soak ≥7 ngày (prod cron)',
      state: g08State,
      detail: g08Detail,
    },
  ];
}

function countPassed(rows: MigrationGateRow[]): number {
  return rows.filter((r) => r.state === 'pass').length;
}

function countUatPassed(manualUat: MetaMigrationManualUat | undefined): number {
  if (!manualUat) return 0;
  return UAT_ROWS.filter((row) => manualUat[row.field]).length;
}

interface MetaMigrationPanelProps {
  status: FacebookAdsMigrationStatus;
  variant?: 'compact' | 'full';
  manualUat?: MetaMigrationManualUat;
  uatReadOnly?: boolean;
  uatSavingField?: MetaMigrationManualUatField | null;
  uatError?: string;
  onToggleUat?: (field: MetaMigrationManualUatField, value: boolean) => void;
}

export function MetaMigrationPanel({
  status,
  variant = 'full',
  manualUat,
  uatReadOnly = false,
  uatSavingField = null,
  uatError = '',
  onToggleUat,
}: MetaMigrationPanelProps) {
  const gates = useMemo(() => buildMigrationGateRows(status), [status]);
  const passed = countPassed(gates);
  const total = gates.length;
  const allPassed = passed === total;
  const progressPct = total ? Math.round((passed / total) * 100) : 0;
  const uatPassed = countUatPassed(manualUat ?? status.manual_uat);
  const uatTotal = UAT_ROWS.length;

  const [collapsed, setCollapsed] = useState(variant === 'compact');
  const [showOps, setShowOps] = useState(false);

  useEffect(() => {
    if (variant !== 'compact') {
      if (window.localStorage.getItem('meta-migration-panel-collapsed') === '1') {
        setCollapsed(true);
      }
    }
  }, [variant]);

  function toggleCollapsed() {
    setCollapsed((prev) => {
      const next = !prev;
      if (variant === 'full' && typeof window !== 'undefined') {
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

  const migrationUrl = status.ops_web_migration_url ?? '/meta/migration';
  const signoffPath = status.signoff_path ?? 'docs/evidence/horizon1-meta-ads-signoff.json';
  const uatState = manualUat ?? status.manual_uat;

  if (variant === 'compact') {
    return (
      <section
        className={`card meta-migration-panel meta-migration-panel--compact${allPassed ? ' meta-migration-panel--complete' : ''}`}
        aria-label="Horizon 1 Meta Ads migration summary"
      >
        <div className="meta-migration-compact-row">
          <div>
            <p className="meta-migration-kicker">Horizon 1</p>
            <p style={{ margin: 0, fontSize: '0.92rem' }}>
              Migration gates: <strong>{passed}/{total}</strong>
              {uatState ? (
                <>
                  {' '}
                  · UAT: <strong>{uatPassed}/{uatTotal}</strong>
                </>
              ) : null}
            </p>
          </div>
          <Link href={migrationUrl} className="btn btn-sm btn-secondary">
            Migration dashboard →
          </Link>
        </div>
        <div className="meta-migration-progress" aria-hidden={collapsed}>
          <div className="meta-migration-progress-bar" style={{ width: `${progressPct}%` }} />
        </div>
      </section>
    );
  }

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
                · Legacy <code>{status.legacy_rs_path}</code>
                {status.gate_m1_g06 ? ' → redirect ops-web' : ''}
              </>
            ) : null}
          </p>
        </div>
        <div className="meta-migration-header-actions">
          <span className="meta-migration-progress-label">
            {passed}/{total} gates
            {uatState ? ` · UAT ${uatPassed}/${uatTotal}` : ''}
          </span>
          <Link href="/meta/facebook-ads" className="btn btn-sm btn-secondary">
            Meta hub
          </Link>
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
              Các gate tự động đã PASS. Tiếp theo: UAT §E, pilot metrics và human sign-off Gate M1.
            </p>
          ) : (
            <p className="muted meta-migration-hint">
              Dữ liệu từ <code>GET /api/v1/facebook-ads/migration-status</code>. UAT checkbox sync vào{' '}
              <code>{signoffPath}</code>.
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

          <div className="meta-migration-details meta-migration-uat-section">
            <h3 className="meta-migration-section-title">UAT thủ công (QA) — §E</h3>
            {uatError ? <p className="error">{uatError}</p> : null}
            <ul className="meta-migration-uat-checklist">
              {UAT_ROWS.map((row) => {
                const checked = uatState?.[row.field] === true;
                const saving = uatSavingField === row.field;
                return (
                  <li key={row.id}>
                    <label className="meta-migration-uat-check">
                      <input
                        type="checkbox"
                        checked={checked}
                        disabled={uatReadOnly || saving || !onToggleUat}
                        onChange={(e) => onToggleUat?.(row.field, e.target.checked)}
                      />
                      <span className="meta-migration-uat-id">{row.id}</span>
                      <span>{row.label}</span>
                      {saving ? <span className="muted">Đang lưu…</span> : null}
                    </label>
                  </li>
                );
              })}
            </ul>
            {status.manual_uat_updated_at ? (
              <p className="muted meta-migration-uat-meta">
                Cập nhật lần cuối: {new Date(status.manual_uat_updated_at).toLocaleString('vi-VN')}
              </p>
            ) : null}
          </div>

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
              <dt>Signoff JSON</dt>
              <dd>
                <code>{signoffPath}</code>
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
              Canonical hub:{' '}
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
