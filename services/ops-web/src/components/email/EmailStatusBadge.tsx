'use client';

const STATUS_LABELS: Record<string, string> = {
  draft: 'Draft',
  pending_approval: 'Chờ duyệt',
  approved: 'Đã duyệt',
  scheduled: 'Đã lên lịch',
  sending: 'Đang gửi',
  sent: 'Đã gửi',
  paused: 'Tạm dừng',
  cancelled: 'Đã hủy',
  failed: 'Lỗi',
  active: 'Active',
  pending: 'Pending',
};

export function EmailStatusBadge({ status }: { status: string }) {
  const key = (status || 'draft').toLowerCase().replace(/\s+/g, '_');
  const label = STATUS_LABELS[key] ?? status;
  return (
    <span className={`email-status-badge email-status-${key}`} aria-label={`Trạng thái: ${label}`}>
      {label}
    </span>
  );
}
