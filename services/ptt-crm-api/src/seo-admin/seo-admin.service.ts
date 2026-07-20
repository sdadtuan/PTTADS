import { Injectable } from '@nestjs/common';
import { SeoAdminRepository } from './seo-admin.repository';
import { SeoClientsListResponse, SeoHubResponse } from './seo-admin.types';

@Injectable()
export class SeoAdminService {
  constructor(private readonly repo: SeoAdminRepository) {}

  async hub(params: {
    customerId?: number;
    days?: number;
    market?: string;
  }): Promise<SeoHubResponse> {
    return this.repo.hubSummary({
      customerId: params.customerId,
      days: params.days ?? 90,
      market: params.market?.trim() || undefined,
    });
  }

  async listClients(params: {
    customerId?: number;
    market?: string;
  }): Promise<SeoClientsListResponse> {
    const hub = await this.hub(params);
    return {
      ok: true,
      clients: hub.clients,
      total: hub.clients.length,
    };
  }
}
