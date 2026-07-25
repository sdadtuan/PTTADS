function envEnabled(name: string, defaultOn = true): boolean {
  const raw = (process.env[name] ?? (defaultOn ? '1' : '0')).trim().toLowerCase();
  return raw !== '0' && raw !== 'false' && raw !== 'no';
}

export function cwvCronEnabled(): boolean {
  return envEnabled('PTT_CWV_ENABLED');
}

export function aeoScheduleCronEnabled(): boolean {
  return envEnabled('PTT_AEO_SCHEDULE_ENABLED');
}

export function crawlReminderEnabled(): boolean {
  return envEnabled('PTT_CRAWL_REMINDER_ENABLED');
}

export function crawlConnectorEnabled(): boolean {
  return envEnabled('PTT_CRAWL_CONNECTOR_ENABLED');
}

export function rankLiveEnabled(): boolean {
  return envEnabled('PTT_RANK_LIVE_ENABLED');
}

export function cwvPerClientLimit(): number {
  const n = Number.parseInt(process.env.PTT_CWV_PER_CLIENT ?? '3', 10);
  return Math.max(1, Math.min(Number.isFinite(n) ? n : 3, 10));
}

export function cwvMaxClients(): number | null {
  const raw = (process.env.PTT_CWV_MAX_CLIENTS ?? '').trim();
  if (!raw) return null;
  const n = Number.parseInt(raw, 10);
  return Number.isFinite(n) && n > 0 ? n : null;
}

export function aeoScheduleMaxClients(): number | null {
  const raw = (process.env.PTT_AEO_SCHEDULE_MAX_CLIENTS ?? '').trim();
  if (!raw) return null;
  const n = Number.parseInt(raw, 10);
  return Number.isFinite(n) && n > 0 ? n : null;
}

export function crawlReminderDays(): number {
  const n = Number.parseInt(process.env.PTT_CRAWL_REMINDER_DAYS ?? '30', 10);
  return Math.max(7, Number.isFinite(n) ? n : 30);
}

export function rankLiveMaxClients(): number | null {
  const raw = (process.env.PTT_RANK_LIVE_MAX_CLIENTS ?? '').trim();
  if (!raw) return null;
  const n = Number.parseInt(raw, 10);
  return Number.isFinite(n) && n > 0 ? n : null;
}
