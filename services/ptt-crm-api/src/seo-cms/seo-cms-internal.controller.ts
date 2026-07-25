import {
  Body,
  CanActivate,
  Controller,
  ExecutionContext,
  Injectable,
  Post,
  UnauthorizedException,
  UseGuards,
} from '@nestjs/common';
import { Request } from 'express';
import { timingSafeEqual } from 'node:crypto';
import { cmsPilotSecret } from './seo-cms.constants';
import { SeoCmsService } from './seo-cms.service';

@Injectable()
export class SeoCmsPilotSecretGuard implements CanActivate {
  canActivate(context: ExecutionContext): boolean {
    const req = context.switchToHttp().getRequest<Request>();
    const secret = cmsPilotSecret();
    if (!secret) return true;
    const got = String(req.headers['x-ptt-cms-secret'] ?? '').trim();
    if (!got) throw new UnauthorizedException({ error: 'missing_cms_secret' });
    const a = Buffer.from(got);
    const b = Buffer.from(secret);
    if (a.length !== b.length || !timingSafeEqual(a, b)) {
      throw new UnauthorizedException({ error: 'invalid_cms_secret' });
    }
    return true;
  }
}

@Controller('api/v1/seo/internal/cms-webhook')
export class SeoCmsInternalController {
  constructor(private readonly cms: SeoCmsService) {}

  @Post('receive')
  @UseGuards(SeoCmsPilotSecretGuard)
  receive(@Body() body: Record<string, unknown>) {
    return this.cms.receivePilotWebhook(body);
  }
}
