import { Injectable, UnauthorizedException } from '@nestjs/common';
import { Pool } from 'pg';
import { AppConfigService, StaffStubUser } from '../config/app-config.service';
import { verifyPortalPassword } from '../portal/portal-password.util';
import {
  StaffLoginResult,
  StaffMeResponse,
  StaffSectionCap,
  StaffUserProfile,
} from './staff-auth.types';
import { signStaffJwt, StaffJwtPayload, verifyStaffJwt } from './staff-jwt.util';

const DEFAULT_STUB_CAPS: StaffSectionCap[] = [
  { section: 'dashboard', action: 'view' },
  { section: 'crm_leads', action: 'view' },
  { section: 'crm_leads', action: 'edit' },
  { section: 'crm_leads', action: 'assign' },
  { section: 'crm_board_customers', action: 'view' },
  { section: 'crm_board_customers', action: 'edit' },
  { section: 'crm_board_customers', action: 'create' },
  { section: 'crm_board', action: 'view' },
  { section: 'crm_board', action: 'edit' },
  { section: 'crm_sales_overview', action: 'view' },
  { section: 'crm_sales_plans', action: 'view' },
  { section: 'crm_sales_plans', action: 'create' },
  { section: 'crm_sales_funnel', action: 'view' },
  { section: 'crm_sales_training', action: 'view' },
  { section: 'crm_sales_training', action: 'create' },
  { section: 'crm_sales_market', action: 'view' },
  { section: 'crm_sales_market', action: 'create' },
  { section: 'crm_sales_prospects', action: 'view' },
  { section: 'crm_sales_prospects', action: 'create' },
  { section: 'crm_payroll_attendance', action: 'view' },
  { section: 'crm_payroll_salary', action: 'view' },
  { section: 'crm_payroll_salary', action: 'edit' },
  { section: 'crm_payroll_salary', action: 'export' },
  { section: 'crm_business_dashboard', action: 'view' },
  { section: 'crm_business_dashboard', action: 'export' },
  { section: 'crm_business_dashboard', action: 'configure' },
  { section: 'crm_owner_weekly_dashboard', action: 'view' },
  { section: 'crm_owner_weekly_dashboard', action: 'export' },
  { section: 'crm_owner_weekly_dashboard', action: 'configure' },
  { section: 'crm_re_projects', action: 'view' },
  { section: 'crm_re_projects', action: 'create' },
  { section: 'crm_re_projects', action: 'edit' },
  { section: 'crm_re_projects', action: 'delete' },
  { section: 'crm_re_projects', action: 'export' },
  { section: 'crm_re_projects_products', action: 'view' },
  { section: 'crm_re_projects_products', action: 'create' },
  { section: 'crm_re_projects_products', action: 'edit' },
  { section: 'crm_re_projects_products', action: 'delete' },
  { section: 'crm_re_projects_budget', action: 'view' },
  { section: 'crm_re_projects_budget', action: 'create' },
  { section: 'crm_re_projects_budget', action: 'edit' },
  { section: 'crm_re_projects_budget', action: 'delete' },
  { section: 'crm_re_projects_budget', action: 'export' },
  { section: 'crm_re_projects_kpi', action: 'view' },
  { section: 'crm_re_projects_kpi', action: 'create' },
  { section: 'crm_re_projects_kpi', action: 'edit' },
  { section: 'crm_re_projects_kpi', action: 'delete' },
  { section: 'crm_re_projects_risks', action: 'view' },
  { section: 'crm_re_projects_risks', action: 'create' },
  { section: 'crm_re_projects_risks', action: 'edit' },
  { section: 'crm_re_projects_risks', action: 'delete' },
  { section: 'crm_staff_roster', action: 'view' },
  { section: 'crm_staff_roster', action: 'edit' },
  { section: 'crm_kpi_records', action: 'view' },
  { section: 'crm_kpi_records', action: 'edit' },
  { section: 'crm_staff_kpi_am_sp', action: 'view' },
  { section: 'crm_agency', action: 'view' },
  { section: 'crm_agency', action: 'create' },
  { section: 'crm_facebook_ads', action: 'view' },
  { section: 'crm_google_ads', action: 'view' },
  { section: 'crm_google_ads', action: 'export' },
  { section: 'meta_campaign_write', action: 'view' },
  { section: 'meta_campaign_write', action: 'approve' },
  { section: 'crm_seo', action: 'view' },
  { section: 'crm_email_mkt', action: 'view' },
  { section: 'crm_email_mkt', action: 'write' },
  { section: 'crm_email_mkt', action: 'settings' },
  { section: 'crm_email_mkt', action: 'compliance' },
  { section: 'crm_email_mkt', action: 'approve' },
  { section: 'crm_email_mkt', action: 'deliverability' },
  { section: 'crm_email_mkt', action: 'reports' },
];

@Injectable()
export class StaffAuthService {
  private pool: Pool | null = null;

  constructor(private readonly config: AppConfigService) {}

  private get db(): Pool {
    if (!this.pool) {
      this.pool = new Pool({ connectionString: this.config.databaseUrl });
    }
    return this.pool;
  }

  async login(email: string, password: string): Promise<StaffLoginResult> {
    const normalized = email.trim().toLowerCase();
    const user = await this.resolveUser(normalized, password);
    if (!user) {
      throw new UnauthorizedException({ error: 'Invalid credentials' });
    }
    return this.issueTokens(user);
  }

  refresh(refreshToken: string): StaffLoginResult {
    const payload = verifyStaffJwt(refreshToken, this.config.staffJwtSecret);
    if (!payload || payload.token_type !== 'refresh') {
      throw new UnauthorizedException({ error: 'Invalid or expired refresh token' });
    }
    return this.issueTokens({
      id: payload.sub,
      email: payload.email,
      displayName: payload.display_name,
      positionId: payload.position_id,
    });
  }

  verifyAccessToken(token: string): StaffJwtPayload {
    const payload = verifyStaffJwt(token, this.config.staffJwtSecret);
    if (!payload || payload.token_type !== 'access') {
      throw new UnauthorizedException({ error: 'Invalid or expired token' });
    }
    return payload;
  }

  async me(accessPayload: StaffJwtPayload): Promise<StaffMeResponse> {
    const caps = await this.loadCaps(accessPayload.position_id);
    return {
      id: accessPayload.sub,
      email: accessPayload.email,
      display_name: accessPayload.display_name,
      position_id: accessPayload.position_id,
      caps,
    };
  }

  hasCap(caps: StaffSectionCap[], section: string, action: string): boolean {
    return caps.some((c) => c.section === section && c.action === action);
  }

  private issueTokens(user: {
    id: string;
    email: string;
    displayName: string;
    positionId: number;
  }): StaffLoginResult {
    const base = {
      sub: user.id,
      email: user.email,
      display_name: user.displayName,
      position_id: user.positionId,
    };
    const accessToken = signStaffJwt(
      { ...base, token_type: 'access' },
      this.config.staffJwtSecret,
      this.config.staffJwtTtlSec,
    );
    const refreshToken = signStaffJwt(
      { ...base, token_type: 'refresh' },
      this.config.staffJwtSecret,
      this.config.staffRefreshTtlSec,
    );
    return {
      access_token: accessToken,
      refresh_token: refreshToken,
      token_type: 'Bearer',
      expires_in: this.config.staffJwtTtlSec,
      refresh_expires_in: this.config.staffRefreshTtlSec,
      user: {
        id: user.id,
        email: user.email,
        display_name: user.displayName,
        position_id: user.positionId,
      },
    };
  }

  private async resolveUser(
    email: string,
    password: string,
  ): Promise<(StaffUserProfile & { displayName: string; positionId: number }) | null> {
    if (this.config.staffAllowStubUsers) {
      const stub = this.config.staffStubUsers.find(
        (u) => u.email === email && u.password === password,
      );
      if (stub) {
        return {
          id: stub.staffId,
          email: stub.email,
          display_name: stub.displayName,
          displayName: stub.displayName,
          position_id: stub.positionId,
          positionId: stub.positionId,
        };
      }
    }
    try {
      const result = await this.db.query(
        `SELECT id::text, email, password_hash, display_name, position_id
         FROM staff_users
         WHERE LOWER(email) = $1 AND active IS TRUE
         LIMIT 1`,
        [email],
      );
      const row = result.rows[0] as
        | {
            id: string;
            email: string;
            password_hash: string;
            display_name: string;
            position_id: number;
          }
        | undefined;
      if (!row || !verifyPortalPassword(password, row.password_hash)) {
        return null;
      }
      void this.db.query(`UPDATE staff_users SET last_login_at = NOW() WHERE id = $1::uuid`, [
        row.id,
      ]);
      return {
        id: row.id,
        email: row.email,
        display_name: row.display_name || row.email,
        displayName: row.display_name || row.email,
        position_id: row.position_id,
        positionId: row.position_id,
      };
    } catch {
      return null;
    }
  }

  async loadCaps(positionId: number): Promise<StaffSectionCap[]> {
    try {
      const result = await this.db.query(
        `SELECT section_id, action
         FROM staff_section_permissions
         WHERE position_id = $1
         ORDER BY section_id, action`,
        [positionId],
      );
      if (result.rowCount && result.rowCount > 0) {
        return result.rows.map((row) => ({
          section: String(row.section_id),
          action: String(row.action),
        }));
      }
    } catch {
      // table may not exist yet on fresh dev
    }
    return DEFAULT_STUB_CAPS;
  }
}
