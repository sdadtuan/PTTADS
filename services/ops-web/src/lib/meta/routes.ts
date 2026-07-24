/** Map legacy CRM paths to ops-web routes. */
export function opsWebLink(path: string): string {
  if (path.startsWith('/crm/hub')) return '/crm/hub';
  if (path.startsWith('/crm/agency')) return path.replace('/crm/agency', '/agency');
  return path;
}
