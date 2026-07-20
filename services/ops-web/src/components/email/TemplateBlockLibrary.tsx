'use client';

export interface TemplateBlock {
  id: string;
  label: string;
  html: string;
}

export const TEMPLATE_BLOCKS: TemplateBlock[] = [
  {
    id: 'header',
    label: 'Header',
    html: `<table width="100%" cellpadding="0" cellspacing="0" role="presentation">
  <tr><td style="padding:24px;font-family:sans-serif;font-size:14px;color:#374151;">
    <strong>{{company_name}}</strong>
  </td></tr>
</table>`,
  },
  {
    id: 'hero',
    label: 'Hero',
    html: `<table width="100%" cellpadding="0" cellspacing="0" role="presentation">
  <tr><td style="padding:32px 24px;text-align:center;font-family:sans-serif;">
    <h1 style="margin:0 0 12px;font-size:28px;color:#111827;">{{headline}}</h1>
    <p style="margin:0;color:#6b7280;">Xin chào {{first_name}},</p>
  </td></tr>
</table>`,
  },
  {
    id: 'product-grid',
    label: 'Product grid',
    html: `<table width="100%" cellpadding="0" cellspacing="0" role="presentation">
  <tr>
    <td width="50%" style="padding:12px;font-family:sans-serif;">
      <div style="border:1px solid #e5e7eb;border-radius:8px;padding:16px;">
        <strong>Sản phẩm A</strong>
        <p style="margin:8px 0 0;color:#6b7280;font-size:14px;">Mô tả ngắn</p>
      </div>
    </td>
    <td width="50%" style="padding:12px;font-family:sans-serif;">
      <div style="border:1px solid #e5e7eb;border-radius:8px;padding:16px;">
        <strong>Sản phẩm B</strong>
        <p style="margin:8px 0 0;color:#6b7280;font-size:14px;">Mô tả ngắn</p>
      </div>
    </td>
  </tr>
</table>`,
  },
  {
    id: 'cta',
    label: 'CTA',
    html: `<table width="100%" cellpadding="0" cellspacing="0" role="presentation">
  <tr><td style="padding:24px;text-align:center;">
    <a href="{{cta_url}}" style="display:inline-block;padding:12px 28px;background:#2563eb;color:#fff;text-decoration:none;border-radius:6px;font-family:sans-serif;font-weight:600;">
      {{cta_label}}
    </a>
  </td></tr>
</table>`,
  },
  {
    id: 'footer-unsub',
    label: 'Footer + unsub',
    html: `<table width="100%" cellpadding="0" cellspacing="0" role="presentation">
  <tr><td style="padding:24px;text-align:center;font-family:sans-serif;font-size:12px;color:#9ca3af;">
    <p style="margin:0 0 8px;">© {{company_name}}</p>
    <p style="margin:0;"><a href="{{unsubscribe_url}}" style="color:#6b7280;">Hủy đăng ký</a></p>
  </td></tr>
</table>`,
  },
];

export function TemplateBlockLibrary({ onInsert, disabled }: { onInsert: (html: string) => void; disabled?: boolean }) {
  return (
    <div className="email-block-library">
      <p className="muted" style={{ marginTop: 0, fontSize: '0.8125rem' }}>Block library</p>
      <ul className="email-block-list">
        {TEMPLATE_BLOCKS.map((block) => (
          <li key={block.id}>
            <button type="button" className="btn btn-secondary btn-sm" disabled={disabled} onClick={() => onInsert(block.html)}>
              + {block.label}
            </button>
          </li>
        ))}
      </ul>
      <p className="muted" style={{ fontSize: '0.75rem', marginBottom: 0 }}>
        Personalization: {'{{first_name}}'}, {'{{company_name}}'}, {'{{unsubscribe_url}}'}
      </p>
    </div>
  );
}
