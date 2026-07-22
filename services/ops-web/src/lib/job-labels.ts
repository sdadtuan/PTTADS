/** Nhãn tiếng Việt cho job_type / status trong job_queue (ops-web). */

const JOB_TYPE_LABELS: Record<string, string> = {
  meta_insights_sync: 'Đồng bộ insights Meta Ads',
  meta_token_refresh: 'Làm mới token Meta',
  ingest_lead: 'Ingest lead (webhook/form)',
  form_ingest: 'Ingest form lead',
  sync_lead_replica: 'Đồng bộ lead replica',
  sync_lead_shadow: 'Đồng bộ lead shadow',
  capi_dispatch: 'Gửi sự kiện CAPI Meta',
  seo_gsc_sync: 'Đồng bộ Google Search Console',
  seo_ga4_sync: 'Đồng bộ Google Analytics 4',
  seo_aeo_scan: 'Quét AEO / SEO',
  seo_freshness_scan: 'Quét độ mới nội dung SEO',
  seo_report_schedules: 'Lịch báo cáo SEO',
  email_campaign_prepare: 'Chuẩn bị chiến dịch email',
  email_campaign_schedule_due: 'Gửi email theo lịch',
  email_journey_enroll_scan: 'Quét enroll journey email',
  email_journey_tick: 'Tick journey email',
  email_journey_trigger_events: 'Trigger sự kiện journey',
  email_experiment_rollup: 'Tổng hợp A/B test email',
  email_send_batch: 'Gửi batch email',
  email_engagement_ingest: 'Ingest tương tác email',
  email_clickhouse_export: 'Export email → ClickHouse',
  email_attribution_rollup: 'Tổng hợp attribution email',
  email_deliverability_scan: 'Quét deliverability email',
  email_bounce_process: 'Xử lý bounce email',
  email_complaint_process: 'Xử lý complaint email',
  email_dns_verify: 'Xác minh DNS email',
  email_warm_up_tick: 'Warm-up domain email',
  email_report_schedules: 'Lịch báo cáo email',
};

const JOB_STATUS_LABELS: Record<string, string> = {
  pending: 'Chờ xử lý',
  running: 'Đang chạy',
  done: 'Hoàn thành',
  failed: 'Lỗi (sẽ thử lại)',
  dead: 'Chết (DLQ)',
};

export function jobTypeLabel(jobType: string): string {
  const key = jobType?.trim();
  if (!key) return '—';
  return JOB_TYPE_LABELS[key] ?? key.replace(/_/g, ' ');
}

export function jobStatusLabel(status: string): string {
  const key = status?.trim();
  if (!key) return '—';
  return JOB_STATUS_LABELS[key] ?? key;
}

/** Hiển thị UI: nhãn Việt + mã kỹ thuật (tooltip). */
export function formatJobTypeCell(jobType: string): { label: string; code: string } {
  const code = jobType?.trim() || '—';
  return { label: jobTypeLabel(code), code };
}
