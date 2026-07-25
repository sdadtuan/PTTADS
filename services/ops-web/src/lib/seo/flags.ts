export function seoHubEnabled(): boolean {
  const raw = process.env.NEXT_PUBLIC_PTT_SEO_HUB_ENABLED ?? '1';
  return raw.trim().toLowerCase() !== '0';
}

export function seoClientWorkspaceEnabled(): boolean {
  const raw = process.env.NEXT_PUBLIC_PTT_SEO_CLIENT_WORKSPACE_ENABLED ?? '1';
  return raw.trim().toLowerCase() !== '0';
}

export function seoResearchEnabled(): boolean {
  const raw = process.env.NEXT_PUBLIC_PTT_SEO_RESEARCH_ENABLED ?? '1';
  return raw.trim().toLowerCase() !== '0';
}

export function seoContentEnabled(): boolean {
  const raw = process.env.NEXT_PUBLIC_PTT_SEO_CONTENT_ENABLED ?? '1';
  return raw.trim().toLowerCase() !== '0';
}
