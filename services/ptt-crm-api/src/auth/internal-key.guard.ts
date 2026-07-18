import { CanActivate, ExecutionContext, Injectable, UnauthorizedException } from '@nestjs/common';
import { Request } from 'express';
import { AppConfigService } from '../config/app-config.service';

@Injectable()
export class InternalKeyGuard implements CanActivate {
  constructor(private readonly config: AppConfigService) {}

  canActivate(context: ExecutionContext): boolean {
    if (this.config.authDisabled || !this.config.internalKey) {
      return true;
    }
    const req = context.switchToHttp().getRequest<Request>();
    const key = String(req.headers['x-ptt-internal-key'] ?? '').trim();
    if (key !== this.config.internalKey) {
      throw new UnauthorizedException({ error: 'Unauthorized' });
    }
    return true;
  }
}
