export const DEFAULT_PROJECT_TYPE_LABELS: Record<string, string> = {
  can_ho: 'Căn hộ chung cư',
  nha_pho: 'Nhà phố / Townhouse',
  dat_nen: 'Đất nền',
  shophouse: 'Shophouse',
  biet_thu: 'Biệt thự',
  mixed: 'Hỗn hợp',
};

export const PROJECT_STATUSES = [
  'planning',
  'presale',
  'selling',
  'handover',
  'completed',
  'paused',
] as const;

export const PROJECT_STATUS_LABELS: Record<string, string> = {
  planning: 'Lập kế hoạch',
  presale: 'Mở bán (Presale)',
  selling: 'Đang bán',
  handover: 'Bàn giao',
  completed: 'Hoàn thành',
  paused: 'Tạm dừng',
};

export const PRODUCT_STATUSES = ['available', 'hold', 'booked', 'sold', 'locked'] as const;

export const PRODUCT_STATUS_LABELS: Record<string, string> = {
  available: 'Còn hàng',
  hold: 'Giữ chỗ',
  booked: 'Đặt cọc',
  sold: 'Đã bán',
  locked: 'Khóa',
};

export const PRODUCT_LINES = [
  'can_ho',
  'thap_tang_thap',
  'studio',
  'duplex',
  'penthouse',
  'shophouse',
  'nha_pho',
  'song_lap',
  'biet_thu',
  'nha_vuon',
  'lien_ke',
  'dat_nen',
  'dat_nen_noi_khu',
  'dat_nen_ngoai_khu',
  'dat_biet_thu',
  'officetel',
  'condotel',
  'can_ho_dich_vu',
  'mat_bang',
  'tien_ich',
  'nha_xuong',
  'khu_cong_nghiep',
  'other',
] as const;

export const PRODUCT_LINE_LABELS: Record<string, string> = {
  can_ho: 'Căn hộ chung cư',
  thap_tang_thap: 'Chung cư thấp tầng',
  studio: 'Studio / Căn hộ mini',
  duplex: 'Duplex / Dual key',
  penthouse: 'Penthouse / Sky villa',
  shophouse: 'Shophouse / Nhà phố TM',
  nha_pho: 'Nhà phố / Townhouse',
  song_lap: 'Nhà song lập / Semi-detached',
  biet_thu: 'Biệt thự',
  nha_vuon: 'Nhà vườn',
  lien_ke: 'Liền kề',
  dat_nen: 'Đất nền',
  dat_nen_noi_khu: 'Đất nền nội khu',
  dat_nen_ngoai_khu: 'Đất nền ngoại khu / ven KĐT',
  dat_biet_thu: 'Đất biệt thự',
  officetel: 'Officetel',
  condotel: 'Condotel / Khách sạn căn',
  can_ho_dich_vu: 'Căn hộ dịch vụ / Serviced apt',
  mat_bang: 'Mặt bằng kinh doanh',
  tien_ich: 'Tiện ích / Công cộng',
  nha_xuong: 'Nhà xưởng / Kho bãi',
  khu_cong_nghiep: 'Khu công nghiệp / CCN',
  other: 'Khác',
};

export const PRODUCT_TYPOLOGIES = [
  'studio',
  '1pn',
  '1pn_plus',
  '2pn',
  '2pn_plus',
  '3pn',
  '3pn_plus',
  '4pn',
  'multi',
  'shophouse',
  'corner',
  'standard',
  'garden',
  'semi_detached',
  'thap_5',
  'thap_8',
  'dat_100',
  'dat_150',
  'dat_200',
  'dat_300',
  'dat_500',
  'other',
] as const;

export const PRODUCT_TYPOLOGY_LABELS: Record<string, string> = {
  studio: 'Studio',
  '1pn': '1 phòng ngủ',
  '1pn_plus': '1PN+',
  '2pn': '2 phòng ngủ',
  '2pn_plus': '2PN+',
  '3pn': '3 phòng ngủ',
  '3pn_plus': '3PN+',
  '4pn': '4+ phòng ngủ',
  multi: 'Đa phòng / Compound',
  shophouse: 'Shophouse',
  corner: 'Căn góc / End unit',
  standard: 'Căn thường',
  garden: 'Nhà vườn / Garden',
  semi_detached: 'Song lập',
  thap_5: 'Thấp tầng ≤ 5 tầng',
  thap_8: 'Thấp tầng ≤ 8 tầng',
  dat_100: 'Đất ~100 m²',
  dat_150: 'Đất ~150 m²',
  dat_200: 'Đất ~200 m²',
  dat_300: 'Đất ~300 m²',
  dat_500: 'Đất ≥ 500 m²',
  other: 'Khác',
};

export const KPI_CATEGORY_LABELS: Record<string, string> = {
  revenue: 'Doanh thu',
  sales: 'Bán hàng',
  marketing: 'Marketing',
  finance: 'Tài chính',
  customer: 'Khách hàng',
  operation: 'Vận hành',
};

export const KPI_TRACK_STATUS_LABELS: Record<string, string> = {
  draft: 'Nháp',
  active: 'Đang theo dõi',
  completed: 'Hoàn thành kỳ',
  cancelled: 'Hủy',
};

export const RISK_CATEGORY_LABELS: Record<string, string> = {
  legal: 'Pháp lý',
  market: 'Thị trường',
  finance: 'Tài chính',
  construction: 'Thi công',
  sales: 'Bán hàng',
  partner: 'Đối tác',
  other: 'Khác',
};

export const RISK_LEVEL_LABELS: Record<string, string> = {
  low: 'Thấp',
  medium: 'Trung bình',
  high: 'Cao',
  critical: 'Nghiêm trọng',
};

export const BUDGET_CATEGORIES = ['revenue', 'cogs', 'marketing', 'sales', 'admin', 'other'] as const;

export const BUDGET_CATEGORY_LABELS: Record<string, string> = {
  revenue: 'Doanh thu',
  cogs: 'Giá vốn / COGS',
  marketing: 'Marketing',
  sales: 'Bán hàng',
  admin: 'Quản lý',
  other: 'Khác',
};

export const RISK_CATEGORIES = [
  'legal',
  'market',
  'finance',
  'construction',
  'sales',
  'partner',
  'other',
] as const;

export const RISK_LEVELS = ['low', 'medium', 'high', 'critical'] as const;

export const PRICE_LIST_STATUS_LABELS: Record<string, string> = {
  draft: 'Nháp',
  active: 'Đang áp dụng',
  archived: 'Lưu trữ',
};

export const PRICE_LIST_STATUSES = ['draft', 'active', 'archived'] as const;

export interface ReProjectTypeRow {
  id: number;
  code: string;
  name: string;
  description: string;
  sort_order: number;
  active: boolean;
  project_count: number;
  created_at: string;
  updated_at: string;
}

export interface ReProjectRow {
  id: number;
  code: string;
  name: string;
  project_type: string;
  project_type_label: string;
  status: string;
  status_label: string;
  location_address: string;
  district: string;
  city: string;
  developer_name: string;
  investor_name: string;
  total_land_area_m2: number | null;
  total_units: number;
  sold_units: number;
  sell_through_pct: number;
  revenue_target_vnd: number;
  start_date: string;
  presale_date: string;
  handover_date: string;
  description: string;
  notes: string;
  business_plan: Record<string, unknown>;
  marketing_plan: Record<string, unknown>;
  sales_plan: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface SaveProjectTypeBody {
  code?: string;
  name?: string;
  description?: string;
  sort_order?: number;
  active?: boolean | number | string;
}

export interface CreateReProjectBody {
  name?: string;
  code?: string;
  project_type?: string;
  status?: string;
  location_address?: string;
  district?: string;
  city?: string;
  developer_name?: string;
  investor_name?: string;
  total_land_area_m2?: number | null;
  total_units?: number;
  sold_units?: number;
  revenue_target_vnd?: number;
  start_date?: string;
  presale_date?: string;
  handover_date?: string;
  description?: string;
  notes?: string;
  business_plan?: Record<string, unknown>;
  marketing_plan?: Record<string, unknown>;
  sales_plan?: Record<string, unknown>;
}

export interface SaveProductBody {
  unit_code?: string;
  tower?: string;
  floor?: string;
  product_line?: string;
  zone?: string;
  typology?: string;
  is_corner?: boolean | number | string;
  sales_staff_id?: number | null;
  product_type?: string;
  area_m2?: number | null;
  bedrooms?: number | null;
  direction?: string;
  view_type?: string;
  list_price_vnd?: number;
  net_price_vnd?: number;
  status?: string;
  notes?: string;
  price_batch?: string;
}

export interface SavePriceListBody {
  version_code?: string;
  code?: string;
  name?: string;
  effective_date?: string;
  status?: string;
  notes?: string;
}

export interface ReProductRow extends Record<string, unknown> {
  id: number;
  project_id: number;
  status_label: string;
  product_line_label: string;
  typology_label: string;
  sales_staff_name: string;
  sales_staff_title: string;
}

export interface RePriceListRow {
  id: number;
  project_id: number;
  version_code: string;
  name: string;
  effective_date: string;
  status: string;
  status_label: string;
  notes: string;
  applied_at: string;
  applied_by: string;
  created_by: string;
  created_at: string;
  updated_at: string;
  item_count: number;
}

export interface InventoryStats {
  total: number;
  available: number;
  sold: number;
  booked: number;
  total_list_value_vnd: number;
  available_list_value_vnd: number;
  by_product_line: Array<Record<string, unknown>>;
  by_zone: Array<Record<string, unknown>>;
  by_typology: Array<Record<string, unknown>>;
  by_status: Record<string, number>;
}

export interface SaveCashFlowBody {
  flow_type?: string;
  category?: string;
  sub_category?: string;
  line_item?: string;
  amount_vnd?: number;
  period_month?: string;
  transaction_date?: string;
  due_date?: string;
  paid_date?: string;
  status?: string;
  source_type?: string;
  source_ref?: string;
  counterparty?: string;
  notes?: string;
}

export interface ImportCashFlowBody {
  csv?: string;
}

export interface AccountingAiAskBody {
  question?: string;
  q?: string;
}

export interface ApplyPredictedRisksBody {
  codes?: string[];
}

export interface SaveKpiBody {
  category?: string;
  metric_name?: string;
  metric_id?: number | string;
  metric_code?: string;
  target_value?: number;
  actual_value?: number;
  unit?: string;
  period_month?: string;
  weight_pct?: number;
  owner_staff_id?: number | string | null;
  owner_name?: string;
  track_status?: string;
  notes?: string;
}

export interface SaveRiskBody {
  category?: string;
  title?: string;
  description?: string;
  probability_pct?: number;
  impact_pct?: number;
  risk_level?: string;
  mitigation?: string;
  owner_name?: string;
  status?: string;
  due_date?: string;
}

export interface SaveBudgetLineBody {
  category?: string;
  line_item?: string;
  period_month?: string;
  planned_vnd?: number;
  actual_vnd?: number;
  notes?: string;
}

export interface RefreshLeadsNewKpiBody {
  period_month?: string;
}

export const PROJECT_STAFF_ROLES = ['sales', 'manager', 'marketing', 'viewer'] as const;

export const PROJECT_STAFF_ROLE_LABELS: Record<string, string> = {
  sales: 'Kinh doanh',
  manager: 'Quản lý dự án',
  marketing: 'Marketing',
  viewer: 'Xem only',
};

export interface ReProjectStaffRow {
  id: number;
  project_id: number;
  staff_id: number;
  staff_name: string;
  staff_code: string;
  role: string;
  role_label: string;
  assign_enabled: boolean;
  sort_order: number;
  joined_at: string;
  left_at: string | null;
  active: boolean;
  scope_product_lines: string[];
  scope_zones: string[];
  scope_product_lines_label: string;
  scope_zones_label: string;
}

export interface AddProjectStaffBody {
  staff_id?: number | string;
  role?: string;
  assign_enabled?: boolean | number | string;
  sort_order?: number | string;
  scope_product_lines?: string[];
  scope_zones?: string[];
}

export interface UpdateProjectStaffBody {
  role?: string;
  assign_enabled?: boolean | number | string;
  sort_order?: number | string;
  scope_product_lines?: string[];
  scope_zones?: string[];
}

export interface SaveProjectLeadConfigBody {
  enabled?: boolean | number | string;
  webhook_enabled?: boolean | number | string;
  auto_assign?: boolean | number | string;
  webhook_slug?: string;
  facebook_page_id?: string;
  zalo_oa_id?: string;
  regenerate_verify_token?: boolean | number | string;
  forms?: Array<Record<string, unknown>>;
  zalo_campaigns?: Array<Record<string, unknown>>;
  website_routes?: Array<Record<string, unknown>>;
}

export interface ReProjectLeadConfigRow {
  project_id: number;
  enabled: boolean;
  webhook_slug: string;
  webhook_verify_token: string;
  webhook_url: string;
  zalo_webhook_url: string;
  facebook_page_id: string;
  zalo_oa_id: string;
  auto_assign: boolean;
  webhook_enabled: boolean;
  forms: Array<Record<string, unknown>>;
  zalo_campaigns: Array<Record<string, unknown>>;
  website_routes: Array<Record<string, unknown>>;
  updated_at: string;
  updated_by: string;
}

export interface ProjectSummaryResponse {
  project: ReProjectRow;
  product_count: number;
  products_available: number;
  products_sold: number;
  product_lines_count: number;
  product_zones_count: number;
  kpi_count: number;
  kpi_with_owner_count: number;
  kpi_avg_achievement_pct: number;
  kpi_weight_total_pct: number;
  inventory: InventoryStats;
  kpi_board: Record<string, unknown>;
  risk_count: number;
  high_risk_count: number;
  budget_revenue_planned_vnd: number;
  budget_revenue_actual_vnd: number;
  budget_cost_planned_vnd: number;
  budget_cost_actual_vnd: number;
  profit_planned_vnd: number;
  profit_actual_vnd: number;
}
