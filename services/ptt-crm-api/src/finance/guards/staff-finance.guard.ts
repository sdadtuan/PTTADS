import {
  CanActivate,
  ExecutionContext,
  ForbiddenException,
  Injectable,
  UnauthorizedException,
} from '@nestjs/common';
import { Request } from 'express';
import { StaffAuthService } from '../../staff-auth/staff-auth.service';
import { StaffJwtPayload } from '../../staff-auth/staff-jwt.util';

type StaffRequest = Request & {
  staffUser?: StaffJwtPayload;
  staffAuthVia?: 'internal' | 'jwt';
};

@Injectable()
export class StaffFinanceViewGuard implements CanActivate {
  constructor(private readonly staffAuth: StaffAuthService) {}

  async canActivate(context: ExecutionContext): Promise<boolean> {
    const req = context.switchToHttp().getRequest<StaffRequest>();
    if (req.staffAuthVia === 'internal') return true;
    if (!req.staffUser) throw new UnauthorizedException({ error: 'Unauthorized' });
    const me = await this.staffAuth.me(req.staffUser);
    if (!this.staffAuth.hasCap(me.caps, 'crm_business_dashboard', 'view')) {
      throw new ForbiddenException({ error: 'missing_cap', section: 'crm_business_dashboard' });
    }
    return true;
  }
}

@Injectable()
export class StaffFinanceExportGuard implements CanActivate {
  constructor(private readonly staffAuth: StaffAuthService) {}

  async canActivate(context: ExecutionContext): Promise<boolean> {
    const req = context.switchToHttp().getRequest<StaffRequest>();
    if (req.staffAuthVia === 'internal') return true;
    if (!req.staffUser) throw new UnauthorizedException({ error: 'Unauthorized' });
    const me = await this.staffAuth.me(req.staffUser);
    const canExport = this.staffAuth.hasCap(me.caps, 'crm_business_dashboard', 'export');
    const canView = this.staffAuth.hasCap(me.caps, 'crm_business_dashboard', 'view');
    if (!canExport && !canView) {
      throw new ForbiddenException({ error: 'missing_cap', section: 'crm_business_dashboard' });
    }
    return true;
  }
}

@Injectable()
export class StaffFinanceConfigureGuard implements CanActivate {
  constructor(private readonly staffAuth: StaffAuthService) {}

  async canActivate(context: ExecutionContext): Promise<boolean> {
    const req = context.switchToHttp().getRequest<StaffRequest>();
    if (req.staffAuthVia === 'internal') return true;
    if (!req.staffUser) throw new UnauthorizedException({ error: 'Unauthorized' });
    const me = await this.staffAuth.me(req.staffUser);
    if (!this.staffAuth.hasCap(me.caps, 'crm_business_dashboard', 'configure')) {
      throw new ForbiddenException({ error: 'missing_cap', section: 'crm_business_dashboard' });
    }
    return true;
  }
}
