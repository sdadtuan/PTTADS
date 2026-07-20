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

@Injectable()
export class StaffSalesViewGuard implements CanActivate {
  constructor(private readonly staffAuth: StaffAuthService) {}

  async canActivate(context: ExecutionContext): Promise<boolean> {
    const req = context.switchToHttp().getRequest<
      Request & { staffUser?: StaffJwtPayload; staffAuthVia?: 'internal' | 'jwt' }
    >();
    if (req.staffAuthVia === 'internal') return true;
    if (!req.staffUser) throw new UnauthorizedException({ error: 'Unauthorized' });
    const me = await this.staffAuth.me(req.staffUser);
    const overview = this.staffAuth.hasCap(me.caps, 'crm_sales_overview', 'view');
    const plans = this.staffAuth.hasCap(me.caps, 'crm_sales_plans', 'view');
    if (!overview && !plans) {
      throw new ForbiddenException({ error: 'missing_cap', section: 'crm_sales_overview' });
    }
    return true;
  }
}

@Injectable()
export class StaffSalesFunnelViewGuard implements CanActivate {
  constructor(private readonly staffAuth: StaffAuthService) {}

  async canActivate(context: ExecutionContext): Promise<boolean> {
    const req = context.switchToHttp().getRequest<
      Request & { staffUser?: StaffJwtPayload; staffAuthVia?: 'internal' | 'jwt' }
    >();
    if (req.staffAuthVia === 'internal') return true;
    if (!req.staffUser) throw new UnauthorizedException({ error: 'Unauthorized' });
    const me = await this.staffAuth.me(req.staffUser);
    if (!this.staffAuth.hasCap(me.caps, 'crm_sales_funnel', 'view')) {
      throw new ForbiddenException({ error: 'missing_cap', section: 'crm_sales_funnel' });
    }
    return true;
  }
}

@Injectable()
export class StaffSalesWriteGuard implements CanActivate {
  constructor(private readonly staffAuth: StaffAuthService) {}

  async canActivate(context: ExecutionContext): Promise<boolean> {
    const req = context.switchToHttp().getRequest<
      Request & { staffUser?: StaffJwtPayload; staffAuthVia?: 'internal' | 'jwt' }
    >();
    if (req.staffAuthVia === 'internal') return true;
    if (!req.staffUser) throw new UnauthorizedException({ error: 'Unauthorized' });
    const me = await this.staffAuth.me(req.staffUser);
    const canCreate = this.staffAuth.hasCap(me.caps, 'crm_sales_plans', 'create');
    const canEdit = this.staffAuth.hasCap(me.caps, 'crm_sales_plans', 'edit');
    if (!canCreate && !canEdit) {
      throw new ForbiddenException({ error: 'missing_cap', section: 'crm_sales_plans' });
    }
    return true;
  }
}

@Injectable()
export class StaffSalesPartnerWriteGuard implements CanActivate {
  constructor(private readonly staffAuth: StaffAuthService) {}

  async canActivate(context: ExecutionContext): Promise<boolean> {
    const req = context.switchToHttp().getRequest<
      Request & { staffUser?: StaffJwtPayload; staffAuthVia?: 'internal' | 'jwt' }
    >();
    if (req.staffAuthVia === 'internal') return true;
    if (!req.staffUser) throw new UnauthorizedException({ error: 'Unauthorized' });
    const me = await this.staffAuth.me(req.staffUser);
    const caps = [
      this.staffAuth.hasCap(me.caps, 'crm_sales_plans', 'create'),
      this.staffAuth.hasCap(me.caps, 'crm_sales_plans', 'edit'),
      this.staffAuth.hasCap(me.caps, 'crm_sales_prospects', 'create'),
    ];
    if (!caps.some(Boolean)) {
      throw new ForbiddenException({ error: 'missing_cap', section: 'crm_sales_prospects' });
    }
    return true;
  }
}

@Injectable()
export class StaffSalesTrainingWriteGuard implements CanActivate {
  constructor(private readonly staffAuth: StaffAuthService) {}

  async canActivate(context: ExecutionContext): Promise<boolean> {
    const req = context.switchToHttp().getRequest<
      Request & { staffUser?: StaffJwtPayload; staffAuthVia?: 'internal' | 'jwt' }
    >();
    if (req.staffAuthVia === 'internal') return true;
    if (!req.staffUser) throw new UnauthorizedException({ error: 'Unauthorized' });
    const me = await this.staffAuth.me(req.staffUser);
    const caps = [
      this.staffAuth.hasCap(me.caps, 'crm_sales_plans', 'create'),
      this.staffAuth.hasCap(me.caps, 'crm_sales_plans', 'edit'),
      this.staffAuth.hasCap(me.caps, 'crm_sales_training', 'create'),
    ];
    if (!caps.some(Boolean)) {
      throw new ForbiddenException({ error: 'missing_cap', section: 'crm_sales_training' });
    }
    return true;
  }
}

@Injectable()
export class StaffSalesMarketWriteGuard implements CanActivate {
  constructor(private readonly staffAuth: StaffAuthService) {}

  async canActivate(context: ExecutionContext): Promise<boolean> {
    const req = context.switchToHttp().getRequest<
      Request & { staffUser?: StaffJwtPayload; staffAuthVia?: 'internal' | 'jwt' }
    >();
    if (req.staffAuthVia === 'internal') return true;
    if (!req.staffUser) throw new UnauthorizedException({ error: 'Unauthorized' });
    const me = await this.staffAuth.me(req.staffUser);
    const caps = [
      this.staffAuth.hasCap(me.caps, 'crm_sales_plans', 'create'),
      this.staffAuth.hasCap(me.caps, 'crm_sales_plans', 'edit'),
      this.staffAuth.hasCap(me.caps, 'crm_sales_market', 'create'),
    ];
    if (!caps.some(Boolean)) {
      throw new ForbiddenException({ error: 'missing_cap', section: 'crm_sales_market' });
    }
    return true;
  }
}
