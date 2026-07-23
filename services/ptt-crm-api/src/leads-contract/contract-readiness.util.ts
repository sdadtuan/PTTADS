import { validatePreliminaryPlan } from '../leads-funnel/presales-marketing-plan.util';
import { presalesCareGateState } from '../leads-funnel/care-pipeline.util';
import { PRESALES_STAGES } from '../leads-funnel/leads-funnel.types';
import type { ContractApprovalRow, ContractRow, ReadinessCheck } from './contract.types';

export function buildReadinessChecks(input: {
  careStageCurrent: string;
  careStagesDoneJson: string;
  presales: {
    stage: string;
    status: string;
    tasksProgress: Record<string, { total: number; done: number }>;
  } | null;
  marketingPlan: Record<string, unknown> | null;
  contract: ContractRow | null;
  pendingApproval: ContractApprovalRow | null;
}): ReadinessCheck[] {
  const checks: ReadinessCheck[] = [];

  const careGate = presalesCareGateState(input.careStageCurrent, input.careStagesDoneJson);
  checks.push({
    key: 'b2_complete',
    ok: careGate.complete,
    label: 'B2 — Liên hệ OK',
    message: careGate.complete ? undefined : 'Hoàn thành B2 trước khi ký HĐ.',
  });

  if (!input.presales || input.presales.status !== 'active') {
    checks.push({
      key: 'presales_active',
      ok: false,
      label: 'Pre-sales active',
      message: 'Chưa có pre-sales hoặc đã converted.',
    });
  } else {
    for (const stage of PRESALES_STAGES) {
      const prog = input.presales.tasksProgress[stage] ?? { total: 0, done: 0 };
      const ok = prog.total > 0 && prog.done >= prog.total;
      checks.push({
        key: `presales_${stage}`,
        ok,
        label: `Pre-sales ${stage} ✓`,
        message: ok ? undefined : `Hoàn thành task giai đoạn ${stage}.`,
      });
    }
  }

  const planValidation = validatePreliminaryPlan(input.marketingPlan);
  checks.push({
    key: 'marketing_plan',
    ok: planValidation.ok,
    label: 'KH MKT sơ bộ @ Proposal',
    message: planValidation.ok ? undefined : (planValidation.messages[0] ?? 'Thiếu KH MKT sơ bộ'),
  });

  checks.push({
    key: 'contract_draft',
    ok: Boolean(input.contract && input.contract.status === 'draft'),
    label: 'HĐ draft',
    message: input.contract ? undefined : 'Tạo HĐ draft trước khi submit.',
  });

  checks.push({
    key: 'no_pending_approval',
    ok: !input.pendingApproval || input.pendingApproval.status !== 'pending',
    label: 'Không có approval đang chờ',
    message:
      input.pendingApproval?.status === 'pending'
        ? 'Đã submit — chờ GDKD duyệt.'
        : undefined,
  });

  return checks;
}
