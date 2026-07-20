import { BLOCK_KEYS, RAG_GREEN, RAG_RED, RAG_YELLOW } from './owner-weekly.util';

export interface ExportSheet {
  name: string;
  headers: string[];
  rows: unknown[][];
}

export interface ExportJsonBundle {
  filename: string;
  format: 'json';
  sheets: ExportSheet[];
}

function formatMetricExport(m: Record<string, unknown>): string {
  const fmt = String(m.format ?? '');
  const value = m.value;
  if (fmt === 'vnd') return Number(value ?? 0).toLocaleString('vi-VN').replace(/,/g, '.');
  if (fmt === 'pct') return `${value}%`;
  if (fmt === 'ratio') return `${value}×`;
  if (fmt === 'days') return `${value} ngày`;
  return String(value ?? '');
}

function kvRows(pairs: Array<[string, unknown]>): unknown[][] {
  return pairs.map(([k, v]) => [k, v]);
}

export function buildOwnerWeeklyExportSheets(dashboard: Record<string, unknown>): ExportSheet[] {
  const week = (dashboard.week ?? {}) as Record<string, unknown>;
  const brief = (dashboard.pre_execution ?? {}) as Record<string, unknown>;
  const rag = (dashboard.rag_counts ?? {}) as Record<string, number>;

  const summaryRows = kvRows([
    ['Tuần', week.label ?? ''],
    ['Bắt đầu', week.start ?? ''],
    ['Kết thúc', week.end ?? ''],
    ['Chỉ số xanh', rag[RAG_GREEN] ?? 0],
    ['Chỉ số vàng', rag[RAG_YELLOW] ?? 0],
    ['Chỉ số đỏ', rag[RAG_RED] ?? 0],
    ['Hành động cần xử lý', brief.action_count ?? 0],
  ]);

  const detailHeaders = ['Khối', 'Chỉ số', 'Giá trị', 'Target', 'Trạng thái', 'So tuần trước (%)', 'Ghi chú'];
  const detailRows: unknown[][] = [];
  const blocks = (dashboard.blocks ?? {}) as Record<string, Record<string, unknown>>;
  for (const blockKey of BLOCK_KEYS) {
    const block = blocks[blockKey] ?? {};
    for (const m of (block.metrics as Record<string, unknown>[]) ?? []) {
      const target = m.target;
      const targetStr =
        target != null ? formatMetricExport({ value: target, format: m.format }) : '';
      detailRows.push([
        block.label ?? blockKey,
        m.label ?? m.key,
        formatMetricExport(m),
        targetStr,
        m.status_label ?? m.status,
        m.delta_pct ?? '',
        m.note ?? '',
      ]);
    }
  }

  const actionHeaders = ['Khối', 'Chỉ số', 'Mức', 'Gợi ý', 'Bước điều tra'];
  const actionRows: unknown[][] = [];
  for (const action of (brief.actions as Record<string, unknown>[]) ?? []) {
    const steps = (action.steps as unknown[]) ?? [];
    actionRows.push([
      action.block_label ?? '',
      action.metric_label ?? '',
      action.status_label ?? action.status ?? '',
      action.hint ?? '',
      steps.slice(0, 5).map(String).join(' | '),
    ]);
  }

  return [
    { name: 'Tom tat', headers: ['Chỉ số', 'Giá trị'], rows: summaryRows },
    { name: 'Chi tiet', headers: detailHeaders, rows: detailRows },
    { name: 'Hanh dong', headers: actionHeaders, rows: actionRows },
  ];
}

export function ownerWeeklyExportFilename(dashboard: Record<string, unknown>): string {
  const week = (dashboard.week ?? {}) as Record<string, unknown>;
  const isoYear = Number(week.iso_year ?? new Date().getFullYear());
  const isoWeek = Number(week.iso_week ?? 1);
  const stamp = new Date().toISOString().slice(0, 10);
  return `owner-weekly-${String(isoYear).padStart(4, '0')}-W${String(isoWeek).padStart(2, '0')}-${stamp}.json`;
}
