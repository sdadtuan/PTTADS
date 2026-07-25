export function stubScanResult(queryText: string): {
  ai_response: string;
  brand_visible: boolean;
  gap_notes: string;
} {
  const output =
    `## Câu trả lời AI điển hình\nStub response for ${queryText}\n\n` +
    `## Phân tích Brand Visibility\nbrand_visible: yes\n\n` +
    `## Content Gap\nStub gap notes.`;
  return {
    ai_response: output,
    brand_visible: true,
    gap_notes: 'Stub gap',
  };
}

export function citationStatus(brandVisible: boolean, gapNotes: string): string {
  const gap = (gapNotes || '').trim();
  if (brandVisible && !gap) return 'cited';
  if (brandVisible) return 'mentioned';
  return 'absent';
}
