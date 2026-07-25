import {
  CanActivate,
  ExecutionContext,
  Injectable,
  UnauthorizedException,
} from '@nestjs/common';
import { Request } from 'express';
import { timingSafeEqual } from 'node:crypto';

function cronSecretKeys(): string[] {
  return [
    process.env.PTT_SEO_CRON_SECRET,
    process.env.CRM_FACEBOOK_SYNC_SECRET,
    process.env.CRM_FINANCE_KPI_CRON_SECRET,
  ]
    .map((v) => (v ?? '').trim())
    .filter(Boolean);
}

@Injectable()
export class SeoCronSecretGuard implements CanActivate {
  canActivate(context: ExecutionContext): boolean {
    const req = context.switchToHttp().getRequest<Request>();
    const secrets = cronSecretKeys();
    if (!secrets.length) {
      const remote = String(req.ip ?? req.socket?.remoteAddress ?? '').toLowerCase();
      const host = String(req.hostname ?? '').split(':')[0].toLowerCase();
      const localAllowed = (process.env.PTT_SEO_CRON_ALLOW_LOCAL ?? '1').trim().toLowerCase();
      if (localAllowed !== '0' && localAllowed !== 'false') {
        if (
          remote.includes('127.0.0.1') ||
          remote === '::1' ||
          remote.includes('::ffff:127.0.0.1') ||
          host === 'localhost' ||
          host === '127.0.0.1'
        ) {
          return true;
        }
      }
      throw new UnauthorizedException({ error: 'cron_secret_not_configured' });
    }
    const header = String(req.headers.authorization ?? '').trim();
    if (!header.toLowerCase().startsWith('bearer ')) {
      throw new UnauthorizedException({ error: 'missing_bearer' });
    }
    const got = header.slice(7).trim();
    const buf = Buffer.from(got);
    for (const exp of secrets) {
      const expBuf = Buffer.from(exp);
      if (buf.length === expBuf.length && timingSafeEqual(buf, expBuf)) {
        return true;
      }
    }
    throw new UnauthorizedException({ error: 'invalid_cron_secret' });
  }
}
