import { Injectable, NestMiddleware } from '@nestjs/common';
import type { NextFunction, Request, Response } from 'express';
import { getRequestCorrelationId } from './correlation.middleware';

function jsonLogsEnabled(): boolean {
  const explicit = (process.env.PTT_JSON_LOGS ?? '').trim().toLowerCase();
  if (['1', 'true', 'yes', 'on'].includes(explicit)) {
    return true;
  }
  if (['0', 'false', 'no', 'off'].includes(explicit)) {
    return false;
  }
  const env = (
    process.env.SENTRY_ENVIRONMENT ??
    process.env.PTT_ENV ??
    process.env.NODE_ENV ??
    ''
  )
    .trim()
    .toLowerCase();
  return ['production', 'staging', 'prod'].includes(env);
}

@Injectable()
export class JsonAccessLogMiddleware implements NestMiddleware {
  use(req: Request, res: Response, next: NextFunction): void {
    if (!jsonLogsEnabled()) {
      next();
      return;
    }
    const started = process.hrtime.bigint();
    res.on('finish', () => {
      const durationMs = Number(process.hrtime.bigint() - started) / 1_000_000;
      const line = JSON.stringify({
        ts: new Date().toISOString(),
        level: 'INFO',
        message: 'http_request',
        component: 'ptt-crm-api',
        correlation_id: getRequestCorrelationId(req),
        http_method: req.method,
        path: req.originalUrl || req.url,
        status: res.statusCode,
        duration_ms: Math.round(durationMs * 100) / 100,
      });
      process.stdout.write(`${line}\n`);
    });
    next();
  }
}
