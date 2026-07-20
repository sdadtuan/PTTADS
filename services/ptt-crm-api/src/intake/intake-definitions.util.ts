export const COMMON_FORM_SLUG = '_common';

export const BANT_KEYS = [
  'budget',
  'authority',
  'need',
  'timeline',
  'fit',
  'history',
] as const;

export const GO_THRESHOLDS = { go: 24, nurture_min: 18 } as const;

export const SERVICE_SLUGS = [
  'dich-vu-seo-tong-the',
  'dich-vu-aeo',
  'dich-vu-seo-local',
  'dich-vu-seo-audit',
  'dich-vu-quan-tri-website',
  'thiet-ke-website',
  'thiet-ke-website-tron-goi',
  'thiet-ke-landing-page',
  'quang-cao-facebook',
  'quang-cao-google',
  'thue-tai-khoan-quang-cao',
  'tiep-thi-noi-dung',
] as const;

export const BANT_ROWS: Array<{ label: string; hint: string }> = [
  { label: 'Budget', hint: 'Ngân sách thực tế/tháng hoặc dự án? Ai duyệt chi?' },
  { label: 'Authority', hint: 'Ai ký HĐ? Ai quyết định cuối cùng?' },
  { label: 'Need', hint: 'Pain point #1? Hậu quả nếu không giải quyết?' },
  { label: 'Timeline', hint: 'Khi nào cần bắt đầu? Deadline campaign/go-live?' },
  { label: 'Fit', hint: 'Phù hợp ICP PTT? Scope trong năng lực?' },
  { label: 'History', hint: 'Đã thử gì? Agency cũ? Kết quả?' },
];

const COMMON_SLUG_ALIASES = new Set([
  COMMON_FORM_SLUG,
  '00-form-chung',
  'common',
  'form-chung',
]);

const COMMON_FORM = {
  title: 'Form chung — chưa xác định dịch vụ',
  group: 'Mọi dịch vụ PTT',
  overview:
    'Qualify lead trước khi biết chính xác dịch vụ. Sau khi rõ → chuyển form dịch vụ cụ thể.',
  icp: 'Lead inbound/outbound chưa rõ scope; multi-service; cần discovery trước khi gán lifecycle slug.',
  phone_qs: [
    'Anh/chị đang quan tâm dịch vụ gì? (SEO / Ads / Web / Content / chưa rõ?)',
    'Website/domain hiện tại (nếu có)?',
    'Pain point #1 cần giải quyết gấp nhất?',
    'Ngân sách dự kiến (range/tháng hoặc dự án)? Ai duyệt chi?',
    'Timeline bắt đầu mong muốn?',
    'Ai là decision maker / người ký HĐ?',
    'Đã thử agency hoặc tự làm gì trước đây? Kết quả?',
    'KPI đo thành công là gì (traffic, lead, doanh thu…)?',
    'Ngành / quy mô DN / thị trường chính?',
    'Lead đến từ đâu — kỳ vọng cụ thể từ PTT?',
    'Có deadline campaign / mùa vụ / họp board không?',
    'Dịch vụ nào ưu tiên nhất nếu phải chọn một?',
  ],
  inperson_qs: [
    'Mục tiêu kinh doanh 6–12 tháng tới? KPI đo thành công?',
    'Khách hàng lý tưởng (ICP) của anh/chị là ai?',
    'Điểm đau lớn nhất hiện tại? Đã thử giải pháp nào?',
    'Quy trình duyệt chi / ký HĐ nội bộ như thế nào?',
    'Đối thủ chính? Anh/chị muốn khác biệt ở đâu?',
    'Team marketing hiện tại: ai làm gì? Thiếu gì?',
    'Ngân sách đã duyệt hay đang xin duyệt?',
    'Timeline bắt buộc (campaign, mùa vụ, board meeting)?',
    'Rủi ro lớn nhất nếu chọn sai đối tác?',
    'Tiêu chí chọn agency (giá, case, SLA, báo cáo)?',
  ],
  red_flags: [
    'Chưa rõ nhu cầu — chỉ hỏi giá',
    'Không có ngân sách / từ chối nêu range',
    'Không tiếp cận được decision maker',
    'Kỳ vọng không thực tế (kết quả trong 1–2 tuần)',
    'Từ chối chia sẻ thông tin cơ bản',
    'Ghost sau 2 lần follow-up',
    'So sánh giá với freelancer không cùng scope',
    'Đa dịch vụ nhưng không ưu tiên — khó scope',
  ],
  urgency: [
    'Campaign / mùa vụ sắp tới',
    'Traffic / lead tụt gấp',
    'Website lỗi / downtime',
    'Hết hạn agency cũ',
    'Board / sếp yêu cầu báo cáo gấp',
    'Đối thủ vượt mặt trên digital',
  ],
};

export function isCommonSlug(slug: string): boolean {
  return COMMON_SLUG_ALIASES.has(String(slug ?? '').trim().toLowerCase());
}

export function normalizeIntakeSlug(slug: string): string {
  if (isCommonSlug(slug)) return COMMON_FORM_SLUG;
  return String(slug ?? '').trim();
}

export function resolveDefinitionSlug(serviceSlug: string): string {
  if (isCommonSlug(serviceSlug)) return COMMON_FORM_SLUG;
  const s = String(serviceSlug ?? '').trim();
  if ((SERVICE_SLUGS as readonly string[]).includes(s)) return s;
  return COMMON_FORM_SLUG;
}

export function buildBantRowsUi(): Array<{ key: string; label: string; hint: string }> {
  const keyMap: Record<string, string> = {
    Budget: 'budget',
    Authority: 'authority',
    Need: 'need',
    Timeline: 'timeline',
    Fit: 'fit',
    History: 'history',
  };
  return BANT_ROWS.map(({ label, hint }) => ({
    key: keyMap[label] ?? label.toLowerCase(),
    label,
    hint,
  }));
}

export function getCommonFormDefinition(): typeof COMMON_FORM {
  return COMMON_FORM;
}

export function getUiDefinition(slug: string): Record<string, unknown> {
  const defSlug = resolveDefinitionSlug(slug);
  const svc = defSlug === COMMON_FORM_SLUG ? COMMON_FORM : COMMON_FORM;
  return {
    slug: defSlug,
    title: svc.title || defSlug,
    group: svc.group || '',
    overview: svc.overview || '',
    icp: svc.icp || '',
    phone_questions: [...(svc.phone_qs || [])],
    inperson_questions: [...(svc.inperson_qs || [])],
    red_flags: [...(svc.red_flags || [])],
    urgency_triggers: [...(svc.urgency || [])],
    bant_rows: buildBantRowsUi(),
    is_common_form: defSlug === COMMON_FORM_SLUG,
  };
}

export function definitionsPayload(): Record<string, unknown> {
  const common = getCommonFormDefinition();
  return {
    slugs: [...SERVICE_SLUGS],
    common_slug: COMMON_FORM_SLUG,
    common: {
      title: common.title,
      phone_questions_count: common.phone_qs.length,
      inperson_questions_count: common.inperson_qs.length,
    },
    bant_rows: BANT_ROWS,
  };
}
