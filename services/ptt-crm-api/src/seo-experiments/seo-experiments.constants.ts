export const SEO_EXPERIMENTS_SCHEMA = 'seo_aeo';

export const EXPERIMENT_STATUSES = ['draft', 'running', 'paused', 'completed', 'archived'] as const;

export const STATUS_TRANSITIONS: Record<string, string[]> = {
  draft: ['running', 'archived'],
  running: ['paused', 'completed', 'archived'],
  paused: ['running', 'completed', 'archived'],
  completed: ['archived'],
  archived: [],
};

export function experimentsEnabled(): boolean {
  const flag = (process.env.PTT_SEO_EXPERIMENTS_ENABLED ?? '0').trim().toLowerCase();
  return flag !== '0' && flag !== 'false' && flag !== 'off' && flag !== 'no';
}
