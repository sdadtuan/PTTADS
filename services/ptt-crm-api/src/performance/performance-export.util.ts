import { PerformanceRow } from './performance.types';

function csvEscape(value: string | number | null | undefined): string {
  if (value == null) {
    return '';
  }
  const raw = String(value);
  if (/[",\n\r]/.test(raw)) {
    return `"${raw.replace(/"/g, '""')}"`;
  }
  return raw;
}

export function performanceExportFilename(clientId: string, from: string, to: string): string {
  const short = clientId.slice(0, 8);
  return `portal-performance-${short}-${from}-${to}.csv`;
}

export function performanceRowsToCsv(rows: PerformanceRow[], groupBy: 'day' | 'campaign'): string {
  const headers =
    groupBy === 'day'
      ? [
          'date',
          'channel',
          'campaign_id',
          'campaign_name',
          'spend',
          'leads_crm',
          'cpl',
          'target_cpl_vnd',
          'cpl_delta_pct',
          'roas',
        ]
      : [
          'channel',
          'campaign_id',
          'campaign_name',
          'spend',
          'leads_crm',
          'cpl',
          'target_cpl_vnd',
          'cpl_delta_pct',
          'roas',
        ];
  const lines = [headers.join(',')];
  for (const row of rows) {
    const base = [
      row.channel ?? 'meta',
      row.external_campaign_id ?? '',
      row.external_campaign_name ?? '',
      row.spend,
      row.leads_crm,
      row.cpl ?? '',
      row.target_cpl_vnd ?? '',
      row.cpl_delta_pct ?? '',
      row.roas ?? '',
    ];
    if (groupBy === 'day') {
      lines.push([row.performance_date ?? '', ...base].map(csvEscape).join(','));
    } else {
      lines.push(base.map(csvEscape).join(','));
    }
  }
  return `${lines.join('\n')}\n`;
}

export function performancePdfStub(clientId: string, from: string, to: string): string {
  return `%PDF-1.1
1 0 obj<<>>endobj
2 0 obj<</Length 44>>stream
BT /F1 12 Tf 72 720 Td (PTT Portal PDF stub ${clientId.slice(0, 8)} ${from}-${to}) Tj ET
endstream
endobj
3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Contents 2 0 R>>endobj
4 0 obj<</Type/Catalog/Pages<</Kids[3 0 R]/Count 1>>>>endobj
xref
0 5
0000000000 65535 f 
0000000010 00000 n 
0000000053 00000 n 
0000000145 00000 n 
0000000225 00000 n 
trailer<</Size 5/Root 4 0 R>>
startxref
304
%%EOF
`;
}
