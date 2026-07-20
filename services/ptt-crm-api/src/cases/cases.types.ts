export interface CaseRow {
  id: number;
  customer_id: number;
  title: string;
  description: string;
  channel: string;
  channel_label: string;
  priority: string;
  priority_label: string;
  status: string;
  status_label: string;
  pipeline_stage: string;
  assigned_to: string;
  assigned_staff_id: number | null;
  assigned_at: string;
  campaign_id: number | null;
  created_at: string;
  updated_at: string;
  customer_name: string;
  customer_phone: string;
  customer_email: string;
  customer_address: string;
  customer_company: string;
  staff_display_name: string;
}

export interface CaseEventRow {
  id: number;
  case_id: number;
  kind: string;
  body: string;
  created_at: string;
}

export interface CareReportRow {
  id: number;
  case_id: number;
  staff_id: number | null;
  staff_name: string;
  contact_type: string;
  contact_type_label: string;
  care_status: string;
  care_status_label: string;
  summary: string;
  next_action: string;
  created_at: string;
}

export interface PatchCaseBody {
  title?: string;
  description?: string;
  status?: string;
  priority?: string;
  pipeline_stage?: string;
  assigned_staff_id?: number | null;
  assigned_to?: string;
  channel?: string;
}

export interface CreateCaseEventBody {
  body: string;
}

export interface CreateCareReportBody {
  summary: string;
  contact_type?: string;
  care_status?: string;
  next_action?: string;
  staff_id?: number | null;
}

export const CRM_STATUSES = [
  'tiep_nhan',
  'dang_xu_ly',
  'cho_khach',
  'da_giai_quyet',
  'dong',
] as const;

export const CRM_STATUS_LABELS: Record<string, string> = {
  tiep_nhan: 'Tiếp nhận',
  dang_xu_ly: 'Đang xử lý',
  cho_khach: 'Chờ KH phản hồi',
  da_giai_quyet: 'Đã giải quyết',
  dong: 'Đã đóng',
};

export const CRM_PRIORITIES = ['thap', 'binh_thuong', 'cao'] as const;

export const CRM_PRIORITY_LABELS: Record<string, string> = {
  thap: 'Thấp',
  binh_thuong: 'Bình thường',
  cao: 'Cao',
};

export const CRM_CHANNELS = ['dien_thoai', 'email', 'zalo', 'truc_tiep', 'khac'] as const;

export const CRM_CHANNEL_LABELS: Record<string, string> = {
  dien_thoai: 'Điện thoại',
  email: 'Email',
  zalo: 'Zalo',
  truc_tiep: 'Trực tiếp',
  khac: 'Khác',
};

export const CRM_CARE_CONTACT_TYPES = [
  'goi_dien',
  'zalo',
  'email',
  'gap_mat',
  'sms',
  'khac',
] as const;

export const CRM_CARE_CONTACT_LABELS: Record<string, string> = {
  goi_dien: 'Gọi điện',
  zalo: 'Zalo / chat',
  email: 'Email',
  gap_mat: 'Gặp trực tiếp',
  sms: 'SMS',
  khac: 'Khác',
};

export const CRM_CARE_STATUS_TYPES = [
  'da_phan_loai',
  'da_lien_he_thanh_cong',
  'khong_goi_duoc',
  'khong_nghe_may',
  'khach_khong_tra_loi',
  'cho_phan_hoi_khach',
  'khach_hen_goi_lai',
  'khong_lien_lac_duoc',
  'so_sai',
  'da_tu_van_xong',
  'chuyen_cap_truong',
  'hoan_tat',
] as const;

export const CRM_CARE_STATUS_LABELS: Record<string, string> = {
  da_phan_loai: 'Đã phân loại xong',
  da_lien_he_thanh_cong: 'Đã liên hệ thành công',
  khong_goi_duoc: 'Không gọi được',
  khong_nghe_may: 'Không nghe máy',
  khach_khong_tra_loi: 'Khách không trả lời',
  cho_phan_hoi_khach: 'Chờ phản hồi khách',
  khach_hen_goi_lai: 'Khách hẹn gọi lại',
  khong_lien_lac_duoc: 'Không liên lạc được',
  so_sai: 'Số sai / không tồn tại',
  da_tu_van_xong: 'Đã tư vấn xong',
  chuyen_cap_truong: 'Chuyển cấp / escalation',
  hoan_tat: 'Hoàn tất chăm sóc',
};

export function normalizeCareContact(raw?: string): string {
  const code = String(raw ?? '').trim().toLowerCase();
  return (CRM_CARE_CONTACT_TYPES as readonly string[]).includes(code) ? code : 'goi_dien';
}

export function normalizeCareStatus(raw?: string): string {
  const code = String(raw ?? '').trim().toLowerCase();
  return (CRM_CARE_STATUS_TYPES as readonly string[]).includes(code)
    ? code
    : 'da_lien_he_thanh_cong';
}

export function normalizeCaseChannel(raw?: string): string {
  const code = String(raw ?? '').trim().toLowerCase();
  return (CRM_CHANNELS as readonly string[]).includes(code) ? code : 'khac';
}

export function normalizeCasePriority(raw?: string): string {
  const code = String(raw ?? '').trim().toLowerCase();
  return (CRM_PRIORITIES as readonly string[]).includes(code) ? code : 'binh_thuong';
}

export function normalizeCaseStatus(raw?: string): string {
  const code = String(raw ?? '').trim().toLowerCase();
  return (CRM_STATUSES as readonly string[]).includes(code) ? code : 'tiep_nhan';
}
