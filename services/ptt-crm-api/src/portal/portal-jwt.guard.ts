import {
  CanActivate,
  createParamDecorator,
  ExecutionContext,
  Injectable,
  UnauthorizedException,
} from '@nestjs/common';
import { Request } from 'express';
import { ClientOffboardService } from '../agency/client-offboard.service';
import { PortalAuthService } from './portal-auth.service';
import { PortalJwtPayload } from './portal-jwt.util';

@Injectable()
export class PortalJwtGuard implements CanActivate {
  constructor(
    private readonly auth: PortalAuthService,
    private readonly tenantLock: ClientOffboardService,
  ) {}

  async canActivate(context: ExecutionContext): Promise<boolean> {
    const req = context.switchToHttp().getRequest<Request & { portalUser?: PortalJwtPayload }>();
    const header = String(req.headers.authorization ?? '').trim();
    const token = header.startsWith('Bearer ') ? header.slice(7).trim() : '';
    if (!token) {
      throw new UnauthorizedException({ error: 'Bearer token required' });
    }
    const user = await this.auth.verifyTokenAsync(token);
    await this.tenantLock.assertPortalTenantActive(user.client_id);
    req.portalUser = user;
    return true;
  }
}

export const PortalUser = createParamDecorator(
  (_data: unknown, ctx: ExecutionContext): PortalJwtPayload => {
    const req = ctx.switchToHttp().getRequest<Request & { portalUser?: PortalJwtPayload }>();
    if (!req.portalUser) {
      throw new UnauthorizedException({ error: 'Unauthorized' });
    }
    return req.portalUser;
  },
);
