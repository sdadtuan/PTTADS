export function seoHubEnabled(): boolean {
  const raw = process.env.NEXT_PUBLIC_PTT_SEO_HUB_ENABLED ?? '1';
  return raw.trim().toLowerCase() !== '0';
}

export function seoClientWorkspaceEnabled(): boolean {
  const raw = process.env.NEXT_PUBLIC_PTT_SEO_CLIENT_WORKSPACE_ENABLED ?? '1';
  return raw.trim().toLowerCase() !== '0';
}
