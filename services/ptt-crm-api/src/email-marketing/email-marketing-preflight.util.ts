import {
  EmailCampaignRow,
  EmailPreflightItem,
  EmailPreflightResponse,
  EmailSegmentRow,
  EmailTemplateRow,
} from './email-marketing.types';

const HREF_RE = /href\s*=\s*["']([^"']+)["']/gi;

export function extractHtmlLinks(html: string): string[] {
  const links: string[] = [];
  let match: RegExpExecArray | null;
  const re = new RegExp(HREF_RE.source, HREF_RE.flags);
  while ((match = re.exec(html)) !== null) {
    links.push(match[1].trim());
  }
  return links;
}

function isValidHttpLink(href: string): boolean {
  try {
    const url = new URL(href);
    return url.protocol === 'http:' || url.protocol === 'https:';
  } catch {
    return false;
  }
}

export function checkHtmlLinks(links: string[]): { ok: number; bad: string[] } {
  const bad: string[] = [];
  let ok = 0;
  for (const href of links) {
    if (!href || href === '#' || href.startsWith('#')) {
      bad.push(href || '(empty)');
      continue;
    }
    const lower = href.toLowerCase();
    if (lower.startsWith('mailto:') || lower.startsWith('tel:') || href.includes('{{')) {
      ok += 1;
      continue;
    }
    if (lower.startsWith('javascript:')) {
      bad.push(href);
      continue;
    }
    if (isValidHttpLink(href)) {
      ok += 1;
      continue;
    }
    bad.push(href);
  }
  return { ok, bad };
}

export function runTemplatePreflight(params: {
  subject: string;
  htmlBody: string;
  textBody?: string | null;
  fromEmail?: string | null;
  domainAuth?: { spfStatus: string | null; dkimStatus: string | null } | null;
}): EmailPreflightResponse {
  const checks: EmailPreflightItem[] = [];
  const subject = params.subject?.trim() ?? '';
  const html = params.htmlBody ?? '';

  checks.push({
    id: 'subject',
    label: 'Subject line',
    status: subject.length >= 3 ? 'pass' : 'fail',
    message: subject.length >= 3 ? 'OK' : 'Subject quá ngắn hoặc trống',
  });

  checks.push({
    id: 'html_body',
    label: 'HTML body',
    status: html.trim().length > 20 ? 'pass' : 'fail',
    message: html.trim().length > 20 ? 'OK' : 'HTML body trống hoặc quá ngắn',
  });

  const unsubPattern = /unsubscribe|list-unsubscribe|\{\{unsubscribe/i;
  const hasUnsubLink = unsubPattern.test(html);
  checks.push({
    id: 'unsubscribe',
    label: 'Unsubscribe link',
    status: hasUnsubLink ? 'pass' : 'fail',
    message: hasUnsubLink
      ? 'OK'
      : 'Thiếu link hủy đăng ký (unsubscribe URL hoặc {{unsubscribe_url}})',
  });

  checks.push({
    id: 'list_unsubscribe_header',
    label: 'List-Unsubscribe header',
    status: hasUnsubLink ? 'pass' : 'warn',
    message: hasUnsubLink
      ? 'ESP adapter thêm List-Unsubscribe + One-Click-Post khi gửi'
      : 'Cần link unsubscribe trong HTML để gắn header RFC 8058',
  });

  const links = extractHtmlLinks(html);
  if (links.length === 0) {
    checks.push({
      id: 'broken_links',
      label: 'Broken links',
      status: 'warn',
      message: 'Không có href trong HTML — kiểm tra thủ công nếu có CTA',
    });
  } else {
    const linkCheck = checkHtmlLinks(links);
    checks.push({
      id: 'broken_links',
      label: 'Broken links',
      status: linkCheck.bad.length === 0 ? 'pass' : 'fail',
      message:
        linkCheck.bad.length === 0
          ? `${linkCheck.ok}/${links.length} links OK`
          : `${linkCheck.bad.length} link lỗi: ${linkCheck.bad.slice(0, 3).join(', ')}`,
    });
  }

  if (params.fromEmail) {
    checks.push({
      id: 'from_email',
      label: 'From email',
      status: /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(params.fromEmail) ? 'pass' : 'warn',
      message: /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(params.fromEmail)
        ? 'OK'
        : 'From email workspace chưa hợp lệ',
    });
  } else {
    checks.push({
      id: 'from_email',
      label: 'From email',
      status: 'warn',
      message: 'Workspace chưa cấu hình default_from_email',
    });
  }

  if (params.fromEmail && params.domainAuth) {
    const spf = (params.domainAuth.spfStatus ?? '').toLowerCase();
    const dkim = (params.domainAuth.dkimStatus ?? '').toLowerCase();
    const authOk = spf === 'pass' && (dkim === 'pass' || dkim === 'warn');
    checks.push({
      id: 'domain_auth',
      label: 'From domain authenticated (SPF/DKIM)',
      status: authOk ? 'pass' : spf === 'unknown' && dkim === 'unknown' ? 'warn' : 'fail',
      message: authOk
        ? `SPF ${spf}, DKIM ${dkim}`
        : `SPF ${spf || 'unknown'}, DKIM ${dkim || 'unknown'} — verify tại Deliverability (E-11)`,
    });
  } else if (params.fromEmail) {
    checks.push({
      id: 'domain_auth',
      label: 'From domain authenticated (SPF/DKIM)',
      status: 'warn',
      message: 'Domain chưa đăng ký trong Deliverability — chạy verify trước send prod',
    });
  }

  const failed = checks.some((c) => c.status === 'fail');
  return { ok: true, passed: !failed, checks };
}

export function runCampaignPreflight(params: {
  templateChecks: EmailPreflightResponse;
  audienceCount: number | null;
  segmentName: string | null;
}): EmailPreflightResponse {
  const checks = [...params.templateChecks.checks];
  if (params.audienceCount == null || params.audienceCount <= 0) {
    checks.push({
      id: 'audience',
      label: 'Audience size',
      status: 'fail',
      message: params.segmentName
        ? `Segment "${params.segmentName}" chưa compute hoặc rỗng`
        : 'Chưa chọn segment — audience_count = 0',
    });
  } else {
    checks.push({
      id: 'audience',
      label: 'Audience size',
      status: 'pass',
      message: `${params.audienceCount.toLocaleString()} contacts eligible`,
    });
  }
  const failed = checks.some((c) => c.status === 'fail');
  return { ok: true, passed: !failed && params.templateChecks.passed, checks };
}

export type { EmailCampaignRow, EmailSegmentRow, EmailTemplateRow };
