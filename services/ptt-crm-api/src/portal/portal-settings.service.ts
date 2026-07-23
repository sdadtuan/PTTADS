import { ForbiddenException, Injectable, ServiceUnavailableException } from '@nestjs/common';
import { PortalJwtPayload } from './portal-jwt.util';
import { PortalSettingsRepository } from './portal-settings.repository';

export interface PortalSettingsResponse {
  ok: boolean;
  client_id: string;
  client_name: string | null;
  display_name: string | null;
  logo_url: string | null;
  am_contact_name: string | null;
  am_contact_email: string | null;
  accent_color: string | null;
  updated_at: string | null;
  table_ready: boolean;
}

@Injectable()
export class PortalSettingsService {
  constructor(private readonly repo: PortalSettingsRepository) {}

  async getForUser(user: PortalJwtPayload): Promise<PortalSettingsResponse> {
    const tableReady = await this.repo.tableReady();
    const clientName = await this.repo.getClientName(user.client_id);
    const row = tableReady ? await this.repo.findByClientId(user.client_id) : null;
    return {
      ok: true,
      client_id: user.client_id,
      client_name: clientName,
      display_name: row?.display_name ?? clientName,
      logo_url: row?.logo_url ?? null,
      am_contact_name: row?.am_contact_name ?? null,
      am_contact_email: row?.am_contact_email ?? null,
      accent_color: row?.accent_color ?? null,
      updated_at: row?.updated_at ?? null,
      table_ready: tableReady,
    };
  }

  async patchForUser(
    user: PortalJwtPayload,
    body: {
      display_name?: string;
      logo_url?: string;
      am_contact_name?: string;
      am_contact_email?: string;
      accent_color?: string;
    },
  ): Promise<PortalSettingsResponse> {
    if (user.role !== 'approver') {
      throw new ForbiddenException({ error: 'approver_role_required' });
    }
    if (!(await this.repo.tableReady())) {
      throw new ServiceUnavailableException({ ok: false, error: 'portal_settings_table_not_ready' });
    }
    await this.repo.upsert(user.client_id, {
      display_name: body.display_name?.trim() || null,
      logo_url: body.logo_url?.trim() || null,
      am_contact_name: body.am_contact_name?.trim() || null,
      am_contact_email: body.am_contact_email?.trim() || null,
      accent_color: body.accent_color?.trim() || null,
      updated_by: user.email,
    });
    return this.getForUser(user);
  }
}
