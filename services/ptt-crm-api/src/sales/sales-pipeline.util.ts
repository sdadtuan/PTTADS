import { FunnelStats } from './sales.types';

export const SALES_PIPELINE_STAGES = [
  'moi',
  'dang_lien_he',
  'mql',
  'sql',
  'bao_gia',
  'chot',
  'mat',
] as const;

export const SALES_PIPELINE_LABELS_VI: Record<string, string> = {
  moi: 'Mới',
  dang_lien_he: 'Đang liên hệ',
  mql: 'MQL',
  sql: 'SQL',
  bao_gia: 'Báo giá',
  chot: 'Chốt',
  mat: 'Mất',
};

export const STAGE_SLA_HOURS: Record<string, number> = {
  moi: 4,
  dang_lien_he: 24,
  mql: 72,
  sql: 120,
  bao_gia: 168,
  chot: 0,
  mat: 0,
};

export const STAGE_OWNER_ROLE: Record<string, string> = {
  moi: 'CSKH / ca trực',
  dang_lien_he: 'Sales',
  mql: 'Sales',
  sql: 'Sales',
  bao_gia: 'Sales',
  chot: 'Account / CS',
  mat: 'Sales',
};

export const TERMINAL_STAGES = new Set(['chot', 'mat']);

export function normalizePipelineStage(raw?: string | null): string {
  const s = String(raw ?? 'moi').trim().toLowerCase();
  return (SALES_PIPELINE_STAGES as readonly string[]).includes(s) ? s : 'moi';
}

export function pipelineStageLabel(stage: string): string {
  return SALES_PIPELINE_LABELS_VI[normalizePipelineStage(stage)] ?? stage;
}

function hoursInStage(enteredAt: string, now: Date): number {
  if (!enteredAt) return 0;
  const t = Date.parse(enteredAt.replace(' ', 'T'));
  if (!Number.isFinite(t)) return 0;
  return Math.max(0, (now.getTime() - t) / 3_600_000);
}

function isSlaOverdue(stage: string, enteredAt: string, now: Date): boolean {
  const st = normalizePipelineStage(stage);
  const sla = STAGE_SLA_HOURS[st] ?? 0;
  if (sla <= 0 || TERMINAL_STAGES.has(st)) return false;
  return hoursInStage(enteredAt, now) > sla;
}

export function computeFunnelStats(
  rows: Array<Record<string, unknown>>,
): FunnelStats {
  const now = new Date();
  const stageCounts: Record<string, number> = Object.fromEntries(
    SALES_PIPELINE_STAGES.map((s) => [s, 0]),
  );
  const stageHoursSum: Record<string, number> = Object.fromEntries(
    SALES_PIPELINE_STAGES.map((s) => [s, 0]),
  );
  const stageHoursN: Record<string, number> = Object.fromEntries(
    SALES_PIPELINE_STAGES.map((s) => [s, 0]),
  );
  const byStaff: Record<string, { open: number; won: number; lost: number; overdue: number }> =
    {};
  const byChannel: Record<string, number> = {};
  let unassigned = 0;
  let slaOverdue = 0;
  let openPipeline = 0;
  let totalDeal = 0;

  for (const d of rows) {
    const stage = normalizePipelineStage(
      String(d.pipeline_stage ?? d.status ?? 'moi'),
    );
    stageCounts[stage] = (stageCounts[stage] ?? 0) + 1;
    if (!TERMINAL_STAGES.has(stage)) openPipeline += 1;

    const entered = String(d.stage_entered_at ?? d.created_at ?? '');
    const hrs = hoursInStage(entered, now);
    stageHoursSum[stage] = (stageHoursSum[stage] ?? 0) + hrs;
    stageHoursN[stage] = (stageHoursN[stage] ?? 0) + 1;

    if (isSlaOverdue(stage, entered, now)) slaOverdue += 1;
    if (!d.assigned_staff_id) unassigned += 1;

    const ch = String(d.channel ?? 'khac');
    byChannel[ch] = (byChannel[ch] ?? 0) + 1;

    const staffKey = String(d.staff_name ?? '— Chưa gán');
    if (!byStaff[staffKey]) {
      byStaff[staffKey] = { open: 0, won: 0, lost: 0, overdue: 0 };
    }
    const bucket = byStaff[staffKey];
    if (stage === 'chot') bucket.won += 1;
    else if (stage === 'mat') bucket.lost += 1;
    else if (!TERMINAL_STAGES.has(stage)) bucket.open += 1;
    if (isSlaOverdue(stage, entered, now)) bucket.overdue += 1;

    const deal = Number(d.deal_value_vnd ?? 0);
    if (Number.isFinite(deal)) totalDeal += deal;
  }

  const stagesOut: FunnelStats['stages'] = [];
  let prevCount: number | null = null;
  for (const st of SALES_PIPELINE_STAGES) {
    const cnt = stageCounts[st] ?? 0;
    const avgH =
      (stageHoursN[st] ?? 0) > 0
        ? Math.round((stageHoursSum[st] / stageHoursN[st]) * 10) / 10
        : 0;
    let conv: number | null = null;
    if (prevCount != null && prevCount > 0) {
      conv = Math.round((100 * cnt) / prevCount * 10) / 10;
    }
    stagesOut.push({
      stage: st,
      label: pipelineStageLabel(st),
      count: cnt,
      avg_hours: avgH,
      sla_hours: STAGE_SLA_HOURS[st] ?? 0,
      conversion_from_prev_pct: conv,
      owner_role: STAGE_OWNER_ROLE[st] ?? '',
    });
    if (!TERMINAL_STAGES.has(st)) prevCount = cnt;
  }

  const bottlenecks: FunnelStats['bottlenecks'] = [];
  for (const item of stagesOut) {
    const st = item.stage;
    if (TERMINAL_STAGES.has(st)) continue;
    const score = item.count * (item.avg_hours / Math.max(1, item.sla_hours || 1));
    if (item.count >= 2 && (item.avg_hours > item.sla_hours || score >= 3)) {
      bottlenecks.push({
        stage: st,
        label: item.label,
        count: item.count,
        avg_hours: item.avg_hours,
        sla_hours: item.sla_hours,
        severity: item.avg_hours > item.sla_hours ? 'high' : 'medium',
      });
    }
  }
  bottlenecks.sort((a, b) => b.count - a.count || b.avg_hours - a.avg_hours);

  const total = rows.length;
  const won = stageCounts.chot ?? 0;
  const lost = stageCounts.mat ?? 0;
  const closed = won + lost;
  const winRate = closed > 0 ? Math.round((100 * won) / closed * 10) / 10 : null;

  const pad = (n: number) => String(n).padStart(2, '0');
  const generatedAt = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())} ${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`;

  return {
    generated_at: generatedAt,
    totals: {
      cases: total,
      open_pipeline: openPipeline,
      unassigned,
      sla_overdue: slaOverdue,
      won,
      lost,
      win_rate_pct: winRate,
      pipeline_value_vnd: totalDeal,
    },
    stages: stagesOut,
    by_staff: byStaff,
    by_channel: byChannel,
    bottlenecks: bottlenecks.slice(0, 5),
  };
}
