export const EMAIL_GATE_A_SCHEMA = 'email_mkt';

export function emailModuleEnabled(): boolean {
  const raw = (process.env.PTT_EMAIL_ENABLED ?? '1').trim().toLowerCase();
  return raw !== '0' && raw !== 'false' && raw !== 'no';
}

export function emailSendEnabled(): boolean {
  const raw = (process.env.PTT_EMAIL_SEND_ENABLED ?? '0').trim().toLowerCase();
  return raw === '1' || raw === 'true' || raw === 'yes';
}

export function emailJourneysEnabled(): boolean {
  const raw = (process.env.PTT_EMAIL_JOURNEYS_ENABLED ?? '0').trim().toLowerCase();
  return raw === '1' || raw === 'true' || raw === 'yes';
}

export function emailPortalEnabled(): boolean {
  const raw = (process.env.PTT_EMAIL_PORTAL_ENABLED ?? '0').trim().toLowerCase();
  return raw === '1' || raw === 'true' || raw === 'yes';
}

export const OPS_WEB_EMAIL_ROUTES = [
  '/email/hub',
  '/email/clients',
  '/email/contacts',
  '/email/consent',
  '/email/suppression',
  '/email/segments',
  '/email/templates',
  '/email/campaigns',
  '/email/journeys',
  '/email/deliverability',
  '/email/reports',
  '/email/governance',
  '/email/gate-a',
] as const;

export const QA_HANDOFF_CHECKLIST: Array<{ id: string; label: string; automated?: boolean }> = [
  { id: 'workspace_hub', label: 'Create workspace → visible on hub client health' },
  { id: 'import_consent', label: 'Import contacts → consent filter works', automated: true },
  { id: 'segment_suppression', label: 'Segment compute → exclusion counts match suppression' },
  { id: 'preflight_unsub', label: 'Template preflight → block send on missing unsub', automated: true },
  { id: 'approval_enqueue', label: 'Full approval → enqueue → webhook open/click' },
  { id: 'bounce_suppression', label: 'Hard bounce → auto suppression → skipped on next send' },
  { id: 'complaint_banner', label: 'Complaint spike → domain pause banner' },
  { id: 'rbac_approve', label: 'RBAC — strategist cannot approve without key', automated: true },
  { id: 'portal_approver', label: 'Portal approver approve/reject flow' },
  { id: 'preference_token', label: 'Preference center token update', automated: true },
  { id: 'one_click_unsub', label: 'One-click unsub → suppression within SLA' },
  { id: 'mobile_smoke', label: 'Mobile smoke: hub + public preference page', automated: true },
  { id: 'executive_drilldown', label: 'Executive drill-down hub → client → contacts (≤3 clicks)', automated: true },
  { id: 'gate_a_page', label: 'Gate A readiness page loads', automated: true },
  { id: 'hub_api_smoke', label: 'Email hub API smoke (Nest)', automated: true },
];
