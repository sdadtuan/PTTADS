export interface CustomerRow {
  id: number;
  name: string;
  phone: string;
  email: string;
  address: string;
  company: string;
  lead_source: string;
  lead_source_label: string;
  lead_source_note: string;
  date_of_birth: string;
  gender: string;
  gender_label: string;
  id_number: string;
  occupation: string;
  interests: string;
  profile_notes: string;
  created_at: string;
}

export interface CustomerRelationRow {
  id: number;
  customer_id: number;
  relation_type: string;
  relation_type_label: string;
  full_name: string;
  phone: string;
  email: string;
  notes: string;
  created_at: string;
  updated_at: string;
}

export interface CustomerPurchaseRow {
  id: number;
  customer_id: number;
  order_date: string;
  product_name: string;
  amount_vnd: number;
  quantity: number;
  status: string;
  status_label: string;
  reference_code: string;
  notes: string;
  contract_id: number | null;
  created_at: string;
  updated_at: string;
}

export interface CustomerIssueRow {
  id: number;
  customer_id: number;
  case_id: number | null;
  issue_type: string;
  issue_type_label: string;
  priority: string;
  priority_label: string;
  status: string;
  status_label: string;
  title: string;
  description: string;
  resolution: string;
  assigned_staff_id: number | null;
  assigned_staff_name: string;
  created_at: string;
  updated_at: string;
  resolved_at: string;
}

export interface CustomerDetailStats {
  relations_total: number;
  purchases_total: number;
  issues_total: number;
  issues_open: number;
}

export interface CreateCustomerBody {
  name: string;
  phone?: string;
  email?: string;
  address?: string;
  company?: string;
  lead_source?: string;
  lead_source_note?: string;
  date_of_birth?: string;
  gender?: string;
  id_number?: string;
  occupation?: string;
  interests?: string;
  profile_notes?: string;
}

export interface PatchCustomerBody {
  name?: string;
  phone?: string;
  email?: string;
  address?: string;
  company?: string;
  lead_source?: string;
  lead_source_note?: string;
  date_of_birth?: string;
  gender?: string;
  id_number?: string;
  occupation?: string;
  interests?: string;
  profile_notes?: string;
}

export const CUSTOMER_LEAD_SOURCES = [
  'web',
  'facebook',
  'zalo',
  'google',
  'referral',
  'walk_in',
  'phone',
  'email',
  'event',
  'partner',
  'marketing',
  'other',
] as const;

export const CUSTOMER_LEAD_SOURCE_LABELS: Record<string, string> = {
  web: 'Website / Landing',
  facebook: 'Facebook',
  zalo: 'Zalo',
  google: 'Google / Ads',
  referral: 'Giới thiệu (referral)',
  walk_in: 'Walk-in / Trực tiếp',
  phone: 'Gọi điện',
  email: 'Email',
  event: 'Sự kiện',
  partner: 'Đối tác',
  marketing: 'Chiến dịch marketing',
  other: 'Khác',
};

export const CUSTOMER_GENDERS = ['male', 'female', 'other', 'unknown'] as const;

export const CUSTOMER_GENDER_LABELS: Record<string, string> = {
  male: 'Nam',
  female: 'Nữ',
  other: 'Khác',
  unknown: 'Chưa rõ',
};

export const RELATION_TYPE_LABELS: Record<string, string> = {
  spouse: 'Vợ / Chồng',
  parent: 'Cha / Mẹ',
  child: 'Con',
  sibling: 'Anh / Chị / Em',
  colleague: 'Đồng nghiệp',
  guardian: 'Người giám hộ',
  other: 'Khác',
};

export const PURCHASE_STATUS_LABELS: Record<string, string> = {
  completed: 'Hoàn tất',
  pending: 'Đang xử lý',
  cancelled: 'Đã hủy',
  refunded: 'Hoàn tiền',
};

export const ISSUE_TYPE_LABELS: Record<string, string> = {
  phan_nan: 'Phàn nàn',
  phan_anh: 'Phản ánh',
  khieu_nai: 'Khiếu nại',
  ho_tro_ky_thuat: 'Hỗ trợ kỹ thuật',
  yeu_cau_dich_vu: 'Yêu cầu dịch vụ',
  khac: 'Khác',
};

export const ISSUE_STATUS_LABELS: Record<string, string> = {
  moi: 'Mới',
  dang_xu_ly: 'Đang xử lý',
  cho_khach: 'Chờ phản hồi KH',
  da_xu_ly: 'Đã xử lý',
  dong: 'Đóng',
};

export const ISSUE_PRIORITY_LABELS: Record<string, string> = {
  thap: 'Thấp',
  binh_thuong: 'Bình thường',
  cao: 'Cao',
  khan_cap: 'Khẩn cấp',
};

export const PROFILE_PATCH_KEYS = [
  'name',
  'phone',
  'email',
  'address',
  'company',
  'lead_source',
  'lead_source_note',
  'date_of_birth',
  'gender',
  'id_number',
  'occupation',
  'interests',
  'profile_notes',
] as const;

export const RELATION_TYPES = [
  'spouse',
  'parent',
  'child',
  'sibling',
  'colleague',
  'guardian',
  'other',
] as const;

export const PURCHASE_STATUSES = ['completed', 'pending', 'cancelled', 'refunded'] as const;

export const ISSUE_TYPES = [
  'phan_nan',
  'phan_anh',
  'khieu_nai',
  'ho_tro_ky_thuat',
  'yeu_cau_dich_vu',
  'khac',
] as const;

export const ISSUE_STATUSES = ['moi', 'dang_xu_ly', 'cho_khach', 'da_xu_ly', 'dong'] as const;

export const ISSUE_PRIORITIES = ['thap', 'binh_thuong', 'cao', 'khan_cap'] as const;

export interface CustomerBriefRow {
  id: number;
  customer_id: number;
  meeting_purpose: string;
  ai_output: string;
  created_at: string;
}

export interface CreateRelationBody {
  relation_type?: string;
  full_name: string;
  phone?: string;
  email?: string;
  notes?: string;
}

export interface PatchRelationBody {
  relation_type?: string;
  full_name?: string;
  phone?: string;
  email?: string;
  notes?: string;
}

export interface CreatePurchaseBody {
  order_date?: string;
  product_name: string;
  amount_vnd?: number;
  quantity?: number;
  status?: string;
  reference_code?: string;
  notes?: string;
  contract_id?: number | null;
}

export interface PatchPurchaseBody {
  order_date?: string;
  product_name?: string;
  amount_vnd?: number;
  quantity?: number;
  status?: string;
  reference_code?: string;
  notes?: string;
}

export interface CreateIssueBody {
  issue_type?: string;
  priority?: string;
  title: string;
  description?: string;
  assigned_staff_id?: number | null;
  case_id?: number | null;
}

export interface PatchIssueBody {
  issue_type?: string;
  priority?: string;
  status?: string;
  title?: string;
  description?: string;
  resolution?: string;
  assigned_staff_id?: number | null;
}

export interface GenerateBriefBody {
  meeting_purpose?: string;
}

export function normalizeRelationType(raw?: string): string {
  const code = String(raw ?? '').trim().toLowerCase();
  return (RELATION_TYPES as readonly string[]).includes(code) ? code : 'other';
}

export function normalizePurchaseStatus(raw?: string): string {
  const code = String(raw ?? '').trim().toLowerCase();
  return (PURCHASE_STATUSES as readonly string[]).includes(code) ? code : 'completed';
}

export function normalizeIssueType(raw?: string): string {
  const code = String(raw ?? '').trim().toLowerCase();
  return (ISSUE_TYPES as readonly string[]).includes(code) ? code : 'phan_anh';
}

export function normalizeIssueStatus(raw?: string): string {
  const code = String(raw ?? '').trim().toLowerCase();
  return (ISSUE_STATUSES as readonly string[]).includes(code) ? code : 'moi';
}

export function normalizeIssuePriority(raw?: string): string {
  const code = String(raw ?? '').trim().toLowerCase();
  return (ISSUE_PRIORITIES as readonly string[]).includes(code) ? code : 'binh_thuong';
}
