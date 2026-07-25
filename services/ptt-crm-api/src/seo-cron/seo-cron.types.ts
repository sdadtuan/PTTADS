export interface SeoCronJobOutcome {
  ok?: boolean;
  skipped?: boolean;
  reason?: string;
  [key: string]: unknown;
}

export interface SeoGateCronResponse {
  ok: boolean;
  jobs: Record<string, SeoCronJobOutcome>;
}
