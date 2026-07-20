import { ReProjectRow } from './re-projects.types';

export const RE_PROJECT_WORKFLOW_STEPS = [
  {
    id: 'overview',
    label: 'Thông tin dự án',
    hint: 'Khởi tạo hồ sơ dự án trên CRM',
    phase: 'initiate',
    phase_label: 'Khởi tạo',
    criteria: 'Mã, tên, vị trí và tổng số căn',
  },
  {
    id: 'business',
    label: 'Kế hoạch kinh doanh',
    hint: 'SWOT, chiến lược, phân tích thị trường',
    phase: 'strategy',
    phase_label: 'Chiến lược',
    criteria: 'Tầm nhìn, SWOT và doanh thu mục tiêu (hoặc duyệt KH)',
  },
  {
    id: 'budget',
    label: 'Ngân sách & P&L',
    hint: 'Khung tài chính trước khi triển khai bán',
    phase: 'finance',
    phase_label: 'Tài chính',
    criteria: 'Có dòng doanh thu và chi phí kế hoạch',
  },
  {
    id: 'products',
    label: 'Tồn kho sản phẩm',
    hint: 'Master data căn hộ trước khi lập giá & bán',
    phase: 'product',
    phase_label: 'Sản phẩm',
    criteria: 'Nhập tồn kho theo phân khu & loại hình sản phẩm',
  },
  {
    id: 'sales',
    label: 'Kế hoạch bán hàng',
    hint: 'Chỉ tiêu, chính sách giá và hoa hồng',
    phase: 'sales',
    phase_label: 'Bán hàng',
    criteria: 'Doanh thu + số căn mục tiêu (hoặc duyệt KH)',
  },
  {
    id: 'marketing',
    label: 'Marketing & GTM',
    hint: 'Go-to-market sau khi có mục tiêu bán',
    phase: 'gtm',
    phase_label: 'Go-to-market',
    criteria: 'Định vị, lead/tháng và ngân sách MKT',
  },
  {
    id: 'kpi',
    label: 'KPI vận hành',
    hint: 'Chỉ tiêu đo lường theo kỳ',
    phase: 'monitor',
    phase_label: 'Đo lường',
    criteria: 'Ít nhất 3 KPI gán nhân viên phụ trách',
  },
  {
    id: 'risks',
    label: 'Quản trị rủi ro',
    hint: 'Risk register — cập nhật xuyên suốt vòng đời dự án',
    phase: 'governance',
    phase_label: 'Quản trị',
    criteria: 'Đăng ký ít nhất 1 rủi ro chính',
    optional: true,
  },
] as const;

export const WORKFLOW_METHODOLOGY =
  'Luồng theo thực hành dự án BĐS: Khởi tạo → Chiến lược → Tài chính → ' +
  'Sản phẩm → Bán hàng → Marketing → KPI → Quản trị rủi ro (song song).';

const STATUS_LABELS: Record<string, string> = {
  done: 'Hoàn thành',
  in_progress: 'Đang làm',
  pending: 'Chưa bắt đầu',
};

function planStatus(
  plan: Record<string, unknown>,
  contentKeys: string[],
  approvedKey = 'approval_status',
): string {
  if (String(plan[approvedKey] ?? '') === 'approved') return 'done';
  for (const k of contentKeys) {
    const v = plan[k];
    if (Array.isArray(v) && v.length) return 'in_progress';
    if (v && typeof v === 'object' && Object.values(v as Record<string, unknown>).some(Boolean)) {
      return 'in_progress';
    }
    if (v != null && v !== '' && v !== 0) return 'in_progress';
  }
  return 'pending';
}

function businessStepStatus(proj: ReProjectRow): string {
  const bp = (proj.business_plan ?? {}) as Record<string, unknown>;
  if (String(bp.approval_status ?? '') === 'approved') return 'done';
  const sw = (bp.swot ?? {}) as Record<string, unknown>;
  const hasSwot = ['strengths', 'weaknesses', 'opportunities', 'threats'].some((k) => sw[k]);
  const hasContent = Boolean(
    bp.vision || bp.mission || hasSwot || Number(bp.revenue_target_vnd ?? 0) > 0,
  );
  return hasContent ? 'in_progress' : 'pending';
}

function marketingStepStatus(proj: ReProjectRow): string {
  const mp = (proj.marketing_plan ?? {}) as Record<string, unknown>;
  if (String(mp.approval_status ?? '') === 'approved') return 'done';
  const hasContent = Boolean(
    mp.positioning ||
      Number(mp.lead_target_monthly ?? 0) > 0 ||
      mp.objectives ||
      mp.channels,
  );
  if (hasContent) return 'in_progress';
  return planStatus(mp, [
    'objectives',
    'target_segments',
    'key_messages',
    'channels',
    'positioning',
  ]);
}

function salesStepStatus(proj: ReProjectRow): string {
  const sp = (proj.sales_plan ?? {}) as Record<string, unknown>;
  if (String(sp.approval_status ?? '') === 'approved') return 'done';
  const hasContent = Boolean(
    Number(sp.revenue_target_vnd ?? 0) > 0 ||
      Number(sp.units_target ?? 0) > 0 ||
      sp.pricing_strategy ||
      sp.commission_policy,
  );
  if (hasContent) return 'in_progress';
  return planStatus(sp, ['pricing_strategy', 'commission_policy', 'revenue_target_vnd', 'units_target']);
}

function overviewStepStatus(proj: ReProjectRow): string {
  const hasName = Boolean(String(proj.name ?? '').trim());
  const hasCode = Boolean(String(proj.code ?? '').trim());
  const hasLocation = Boolean(
    String(proj.district ?? '').trim() ||
      String(proj.city ?? '').trim() ||
      String(proj.location_address ?? '').trim(),
  );
  const hasScale = Number(proj.total_units ?? 0) > 0;
  if (hasName && hasCode && hasLocation && hasScale) return 'done';
  if (hasName && (hasCode || hasLocation)) return 'in_progress';
  return 'pending';
}

function productsStepStatus(proj: ReProjectRow, summary: Record<string, unknown>): string {
  const count = Number(summary.product_count ?? 0);
  const total = Number(proj.total_units ?? 0);
  if (count >= 1 && (total <= 0 || count >= Math.min(3, Math.max(1, Math.floor(total / 10))))) {
    return 'done';
  }
  if (count >= 1 || total > 0) return 'in_progress';
  return 'pending';
}

function kpiStepStatus(summary: Record<string, unknown>): string {
  const n = Number(summary.kpi_count ?? 0);
  const withOwner = Number(summary.kpi_with_owner_count ?? 0);
  if (n >= 3 && withOwner >= 3) return 'done';
  if (n >= 1 || withOwner >= 1) return 'in_progress';
  return 'pending';
}

function budgetStepStatus(summary: Record<string, unknown>): string {
  const rev = Number(summary.budget_revenue_planned_vnd ?? 0);
  const cost = Number(summary.budget_cost_planned_vnd ?? 0);
  if (rev > 0 && cost > 0) return 'done';
  if (rev > 0 || cost > 0) return 'in_progress';
  return 'pending';
}

function risksStepStatus(summary: Record<string, unknown>): string {
  return Number(summary.risk_count ?? 0) >= 1 ? 'done' : 'pending';
}

export function computeProjectWorkflow(
  projectId: number,
  proj: ReProjectRow,
  summary: Record<string, unknown>,
): Record<string, unknown> {
  const statusMap: Record<string, string> = {
    overview: overviewStepStatus(proj),
    business: businessStepStatus(proj),
    budget: budgetStepStatus(summary),
    products: productsStepStatus(proj, summary),
    sales: salesStepStatus(proj),
    marketing: marketingStepStatus(proj),
    kpi: kpiStepStatus(summary),
    risks: risksStepStatus(summary),
  };

  const steps: Array<Record<string, unknown>> = [];
  let doneN = 0;
  let nextStepId = '';

  RE_PROJECT_WORKFLOW_STEPS.forEach((meta, i) => {
    const st = statusMap[meta.id] ?? 'pending';
    const optional = Boolean((meta as { optional?: boolean }).optional);
    const prevId = i > 0 ? RE_PROJECT_WORKFLOW_STEPS[i - 1].id : '';
    const nextId =
      i < RE_PROJECT_WORKFLOW_STEPS.length - 1 ? RE_PROJECT_WORKFLOW_STEPS[i + 1].id : '';
    if (st === 'done') doneN += 1;
    else if (!nextStepId) nextStepId = meta.id;
    let label = STATUS_LABELS[st] ?? st;
    if (optional && st === 'pending') label = 'Khuyến nghị';
    steps.push({
      ...meta,
      status: st,
      status_label: label,
      prev_step_id: prevId,
      next_step_id: nextId,
      order: i + 1,
      blocked_by: '',
      optional,
      accessible: true,
      locked: false,
    });
  });

  if (!nextStepId) {
    for (const s of steps) {
      if (s.status !== 'done') {
        nextStepId = String(s.id);
        break;
      }
    }
    if (!nextStepId && steps.length) nextStepId = String(steps[steps.length - 1].id);
  }

  const nextStep = steps.find((s) => s.id === nextStepId);
  let nextHint = '';
  if (nextStep) {
    const crit = String(nextStep.criteria ?? nextStep.hint ?? '');
    nextHint = `${nextStep.label}: ${crit}`;
  }

  const total = steps.length;
  return {
    project_id: projectId,
    steps,
    done_count: doneN,
    total_steps: total,
    progress_pct: total ? Math.round((doneN / total) * 1000) / 10 : 0,
    next_step_id: nextStepId,
    next_step_hint: nextHint,
    methodology_note: WORKFLOW_METHODOLOGY,
  };
}
