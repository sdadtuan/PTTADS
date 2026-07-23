import {
  CarePipelineState,
  PresalesCareGateState,
} from './leads-funnel.types';

export const CONTACT_OK_CARE_STATUS = 'da_lien_he_thanh_cong';

export const CARE_PIPELINE_STAGES = [
  {
    key: 'first_contact',
    label: 'Liên hệ lần đầu',
    hint:
      'Liên hệ trong 48h — xác nhận nhu cầu dịch vụ marketing. Cập nhật trạng thái + báo cáo; 「Liên hệ OK» rồi hoàn thành B2 để mở pre-sales.',
    status_on_complete: 'first_contact',
  },
] as const;

export const CARE_STAGE_KEYS: string[] = CARE_PIPELINE_STAGES.map((s) => s.key);
export const PRESALES_REQUIRED_CARE_STAGES = ['first_contact'] as const;

const LEGACY_PRESALES_CARE_STAGES = ['intake', 'first_contact', 'qualify'] as const;
export const CARE_STAGE_MIN_COMPLETION_NOTE_LEN = 3;

export function parseLeadMeta(raw: string | null | undefined): Record<string, unknown> {
  if (!raw?.trim()) return {};
  try {
    const data = JSON.parse(raw) as unknown;
    return data && typeof data === 'object' && !Array.isArray(data)
      ? (data as Record<string, unknown>)
      : {};
  } catch {
    return {};
  }
}

export function parseStagesDoneJson(raw: string | null | undefined): Record<string, string> {
  if (!raw?.trim()) return {};
  try {
    const data = JSON.parse(raw) as unknown;
    if (!data || typeof data !== 'object' || Array.isArray(data)) return {};
    const out: Record<string, string> = {};
    for (const [k, v] of Object.entries(data as Record<string, unknown>)) {
      if (v) out[String(k)] = String(v);
    }
    return out;
  } catch {
    return {};
  }
}

export function legacyPresalesCareComplete(done: Record<string, string>): boolean {
  return LEGACY_PRESALES_CARE_STAGES.every((k) => Boolean(done[k]));
}

export function careStageForStatus(status: string): string {
  const st = String(status || 'new').trim().toLowerCase();
  if (st === 'lost' || st === 'pending_cleanup') return 'first_contact';
  return 'first_contact';
}

export function normalizeCareStageCurrent(
  careStageCurrent: string | null | undefined,
  careStagesDoneJson: string | null | undefined,
  status: string,
): string {
  const done = parseStagesDoneJson(careStagesDoneJson);
  if (done.first_contact || legacyPresalesCareComplete(done)) return 'first_contact';
  const cur = String(careStageCurrent || '').trim();
  if (CARE_STAGE_KEYS.includes(cur)) return cur;
  return careStageForStatus(status);
}

export function serializeStagesDone(done: Record<string, string>): string {
  const clean: Record<string, string> = {};
  for (const k of CARE_STAGE_KEYS) {
    if (done[k]) clean[k] = done[k];
  }
  return JSON.stringify(clean);
}

export function carePipelineState(
  status: string,
  careStageCurrent: string | null | undefined,
  careStagesDoneJson: string | null | undefined,
): CarePipelineState {
  let done = parseStagesDoneJson(careStagesDoneJson);
  if (legacyPresalesCareComplete(done) && !done.first_contact) {
    done = {
      ...done,
      first_contact: done.qualify || done.first_contact || '',
    };
  }
  const current = normalizeCareStageCurrent(careStageCurrent, careStagesDoneJson, status);
  const curIdx = CARE_STAGE_KEYS.indexOf(current);
  const stages = CARE_PIPELINE_STAGES.map((st, i) => {
    let completedAt = done[st.key] || '';
    if (legacyPresalesCareComplete(done) && st.key === 'first_contact' && !completedAt) {
      completedAt = done.qualify || done.first_contact || '';
    }
    const isDone = Boolean(completedAt);
    return {
      key: st.key,
      label: st.label,
      hint: st.hint,
      index: i,
      done: isDone,
      current: st.key === current && !isDone,
      completed_at: completedAt,
    };
  });
  if (stages[0]?.done) stages[0].current = false;
  const currentMeta = CARE_PIPELINE_STAGES[Math.max(0, curIdx)] ?? CARE_PIPELINE_STAGES[0];
  const b2Done = Boolean(stages[0]?.done);
  return {
    current_stage_key: current,
    current_stage_label: currentMeta.label,
    current_stage_hint: currentMeta.hint,
    current_stage_index: Math.max(0, curIdx),
    stages_done: Object.fromEntries(CARE_STAGE_KEYS.filter((k) => done[k]).map((k) => [k, done[k]])),
    stages,
    all_complete: b2Done,
  };
}

export function presalesCareGateState(
  careStageCurrent: string | null | undefined,
  careStagesDoneJson: string | null | undefined,
): PresalesCareGateState {
  const done = parseStagesDoneJson(careStagesDoneJson);
  const legacyOk = legacyPresalesCareComplete(done);
  const stages = PRESALES_REQUIRED_CARE_STAGES.map((key) => {
    const meta = CARE_PIPELINE_STAGES.find((s) => s.key === key);
    let completedAt = done[key] || '';
    if (key === 'first_contact' && !completedAt && legacyOk) {
      completedAt = done.qualify || done.first_contact || '';
    }
    return {
      key,
      label: meta?.label ?? key,
      index: 2,
      done: Boolean(completedAt),
      completed_at: completedAt,
    };
  });
  const complete = legacyOk || Boolean(stages[0]?.done);
  const missing = stages.filter((s) => !s.done);
  return {
    complete,
    stages,
    missing_keys: missing.map((s) => s.key),
    missing_labels: missing.map((s) => s.label),
    message: complete
      ? 'Đã hoàn thành B2 — có thể bắt đầu pre-sales.'
      : 'Hoàn thành B2 trước pre-sales: báo cáo trạng thái 「Liên hệ OK」 + ghi chú hoàn thành bước.',
    current_stage_key: normalizeCareStageCurrent(careStageCurrent, careStagesDoneJson, ''),
  };
}

export function assertPresalesCareGate(
  careStageCurrent: string | null | undefined,
  careStagesDoneJson: string | null | undefined,
): void {
  const gate = presalesCareGateState(careStageCurrent, careStagesDoneJson);
  if (!gate.complete) {
    throw new Error(gate.message);
  }
}
