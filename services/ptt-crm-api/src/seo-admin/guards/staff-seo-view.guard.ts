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
import { StaffSectionCap } from '../../staff-auth/staff-auth.types';

const SEO_VIEW_SECTIONS = [
  'crm_seo_aeo',
  'crm_seo_aeo_write',
  'crm_seo_aeo_approve',
  'crm_seo_aeo_technical',
  'crm_seo_aeo_settings',
  'crm_seo_aeo_reports',
] as const;

export function staffHasSeoView(caps: StaffSectionCap[]): boolean {
  if (caps.some((c) => c.section === 'crm_seo' && c.action === 'view')) return true;
  if (caps.some((c) => c.section === 'crm_agency' && c.action === 'view')) return true;
  return SEO_VIEW_SECTIONS.some((section) =>
    caps.some((c) => c.section === section && c.action === 'view'),
  );
}

export function staffHasSeoSettings(caps: StaffSectionCap[]): boolean {
  if (staffHasSeoView(caps) && caps.some((c) => c.section === 'crm_agency' && c.action === 'configure')) {
    return true;
  }
  if (caps.some((c) => c.section === 'crm_seo_aeo_settings' && ['configure', 'edit'].includes(c.action))) {
    return true;
  }
  if (caps.some((c) => c.section === 'crm_seo_aeo' && ['configure', 'edit'].includes(c.action))) {
    return true;
  }
  return false;
}

export function staffHasSeoWrite(caps: StaffSectionCap[]): boolean {
  if (caps.some((c) => c.section === 'crm_seo_aeo_write' && ['edit', 'create'].includes(c.action))) {
    return true;
  }
  if (caps.some((c) => c.section === 'crm_seo_aeo' && ['edit', 'create'].includes(c.action))) {
    return true;
  }
  return staffHasSeoSettings(caps);
}

export function staffHasSeoApprove(caps: StaffSectionCap[]): boolean {
  if (caps.some((c) => c.section === 'crm_seo_aeo_approve' && c.action === 'approve')) {
    return true;
  }
  if (caps.some((c) => c.section === 'crm_seo_aeo' && c.action === 'approve')) {
    return true;
  }
  return caps.some((c) => c.section === 'crm_board' && c.action === 'edit');
}

export function staffHasSeoTechnical(caps: StaffSectionCap[]): boolean {
  if (caps.some((c) => c.section === 'crm_seo_aeo_technical' && ['edit', 'create'].includes(c.action))) {
    return true;
  }
  if (caps.some((c) => c.section === 'crm_seo_aeo' && ['edit', 'create'].includes(c.action))) {
    return true;
  }
  return staffHasSeoWrite(caps);
}

export function staffHasSeoReports(caps: StaffSectionCap[]): boolean {
  if (caps.some((c) => c.section === 'crm_seo_aeo_reports' && c.action === 'view')) return true;
  return staffHasSeoView(caps);
}

@Injectable()
export class StaffSeoViewGuard implements CanActivate {
  constructor(private readonly staffAuth: StaffAuthService) {}

  async canActivate(context: ExecutionContext): Promise<boolean> {
    const req = context.switchToHttp().getRequest<
      Request & { staffUser?: StaffJwtPayload; staffAuthVia?: 'internal' | 'jwt' }
    >();
    if (req.staffAuthVia === 'internal') return true;
    if (!req.staffUser) throw new UnauthorizedException({ error: 'Unauthorized' });
    const me = await this.staffAuth.me(req.staffUser);
    if (!staffHasSeoView(me.caps)) {
      throw new ForbiddenException({ error: 'missing_cap', section: 'crm_seo_aeo' });
    }
    return true;
  }
}

@Injectable()
export class StaffSeoSettingsGuard implements CanActivate {
  constructor(private readonly staffAuth: StaffAuthService) {}

  async canActivate(context: ExecutionContext): Promise<boolean> {
    const req = context.switchToHttp().getRequest<
      Request & { staffUser?: StaffJwtPayload; staffAuthVia?: 'internal' | 'jwt' }
    >();
    if (req.staffAuthVia === 'internal') return true;
    if (!req.staffUser) throw new UnauthorizedException({ error: 'Unauthorized' });
    const me = await this.staffAuth.me(req.staffUser);
    if (!staffHasSeoSettings(me.caps)) {
      throw new ForbiddenException({ error: 'missing_cap', section: 'crm_seo_aeo_settings' });
    }
    return true;
  }
}

@Injectable()
export class StaffSeoWriteGuard implements CanActivate {
  constructor(private readonly staffAuth: StaffAuthService) {}

  async canActivate(context: ExecutionContext): Promise<boolean> {
    const req = context.switchToHttp().getRequest<
      Request & { staffUser?: StaffJwtPayload; staffAuthVia?: 'internal' | 'jwt' }
    >();
    if (req.staffAuthVia === 'internal') return true;
    if (!req.staffUser) throw new UnauthorizedException({ error: 'Unauthorized' });
    const me = await this.staffAuth.me(req.staffUser);
    if (!staffHasSeoWrite(me.caps)) {
      throw new ForbiddenException({ error: 'missing_cap', section: 'crm_seo_aeo_write' });
    }
    return true;
  }
}

@Injectable()
export class StaffSeoApproveGuard implements CanActivate {
  constructor(private readonly staffAuth: StaffAuthService) {}

  async canActivate(context: ExecutionContext): Promise<boolean> {
    const req = context.switchToHttp().getRequest<
      Request & { staffUser?: StaffJwtPayload; staffAuthVia?: 'internal' | 'jwt' }
    >();
    if (req.staffAuthVia === 'internal') return true;
    if (!req.staffUser) throw new UnauthorizedException({ error: 'Unauthorized' });
    const me = await this.staffAuth.me(req.staffUser);
    if (!staffHasSeoApprove(me.caps)) {
      throw new ForbiddenException({ error: 'missing_cap', section: 'crm_seo_aeo_approve' });
    }
    return true;
  }
}

@Injectable()
export class StaffSeoTechnicalGuard implements CanActivate {
  constructor(private readonly staffAuth: StaffAuthService) {}

  async canActivate(context: ExecutionContext): Promise<boolean> {
    const req = context.switchToHttp().getRequest<
      Request & { staffUser?: StaffJwtPayload; staffAuthVia?: 'internal' | 'jwt' }
    >();
    if (req.staffAuthVia === 'internal') return true;
    if (!req.staffUser) throw new UnauthorizedException({ error: 'Unauthorized' });
    const me = await this.staffAuth.me(req.staffUser);
    if (!staffHasSeoTechnical(me.caps)) {
      throw new ForbiddenException({ error: 'missing_cap', section: 'crm_seo_aeo_technical' });
    }
    return true;
  }
}

@Injectable()
export class StaffSeoReportsGuard implements CanActivate {
  constructor(private readonly staffAuth: StaffAuthService) {}

  async canActivate(context: ExecutionContext): Promise<boolean> {
    const req = context.switchToHttp().getRequest<
      Request & { staffUser?: StaffJwtPayload; staffAuthVia?: 'internal' | 'jwt' }
    >();
    if (req.staffAuthVia === 'internal') return true;
    if (!req.staffUser) throw new UnauthorizedException({ error: 'Unauthorized' });
    const me = await this.staffAuth.me(req.staffUser);
    if (!staffHasSeoReports(me.caps)) {
      throw new ForbiddenException({ error: 'missing_cap', section: 'crm_seo_aeo_reports' });
    }
    return true;
  }
}
