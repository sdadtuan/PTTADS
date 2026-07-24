import { BadRequestException, Injectable, NotFoundException } from '@nestjs/common';
import { MetaCreativeRegistryRepository } from './meta-creative-registry.repository';
import {
  MetaAdCreativeLinkRow,
  MetaCreativeLinkMutationResponse,
  MetaCreativeLinkResolveResponse,
  MetaCreativeLinksListResponse,
} from './meta-creative-registry.types';

const LINK_SOURCES = new Set(['manual', 'campaign_write', 'graph_sync']);

@Injectable()
export class MetaCreativeRegistryService {
  constructor(private readonly repo: MetaCreativeRegistryRepository) {}

  isEnabled(): boolean {
    return ['1', 'true', 'yes', 'on'].includes(
      (process.env.PTT_META_CREATIVE_REGISTRY_ENABLED ?? '0').trim().toLowerCase(),
    );
  }

  private mapRow(row: Record<string, unknown>): MetaAdCreativeLinkRow {
    return {
      id: String(row.id),
      client_id: String(row.client_id),
      creative_submission_id: String(row.creative_submission_id),
      external_ad_id: String(row.external_ad_id),
      external_adset_id: row.external_adset_id != null ? String(row.external_adset_id) : null,
      external_campaign_id:
        row.external_campaign_id != null ? String(row.external_campaign_id) : null,
      external_creative_id:
        row.external_creative_id != null ? String(row.external_creative_id) : null,
      link_source: String(row.link_source ?? 'manual'),
      is_active: Boolean(row.is_active),
      linked_by: row.linked_by != null ? String(row.linked_by) : null,
      note: row.note != null ? String(row.note) : null,
      creative_title: row.title != null ? String(row.title) : null,
      creative_status: row.status != null ? String(row.status) : null,
      creative_asset_url: row.asset_url != null ? String(row.asset_url) : null,
      creative_version: row.version != null ? Number(row.version) : null,
      created_at: new Date(String(row.created_at)).toISOString(),
      updated_at: new Date(String(row.updated_at)).toISOString(),
    };
  }

  private disabledList(): MetaCreativeLinksListResponse {
    return { ok: true, disabled: true, rows: [], count: 0 };
  }

  async listLinks(query: {
    client_id?: string;
    external_ad_id?: string;
    external_campaign_id?: string;
    creative_submission_id?: string;
    active_only?: string;
    limit?: string;
  }): Promise<MetaCreativeLinksListResponse> {
    if (!this.isEnabled()) return this.disabledList();
    if (!(await this.repo.pgReady())) {
      return {
        ok: true,
        disabled: true,
        reason: 'meta_ad_creative_links_not_ready',
        hint: './scripts/apply_pg_ddl_v9_meta_creative_registry.sh',
        rows: [],
        count: 0,
      };
    }

    const limitRaw = query.limit ? Number(query.limit) : 200;
    const rows = await this.repo.listLinks({
      clientId: query.client_id?.trim() || undefined,
      externalAdId: query.external_ad_id?.trim() || undefined,
      externalCampaignId: query.external_campaign_id?.trim() || undefined,
      creativeSubmissionId: query.creative_submission_id?.trim() || undefined,
      activeOnly: (query.active_only ?? '1').trim() !== '0',
      limit: Number.isFinite(limitRaw) ? Math.min(Math.max(limitRaw, 1), 1000) : 200,
    });
    const mapped = rows.map((row) => this.mapRow(row as Record<string, unknown>));
    return { ok: true, rows: mapped, count: mapped.length };
  }

  async resolveLink(query: {
    client_id?: string;
    external_ad_id?: string;
  }): Promise<MetaCreativeLinkResolveResponse> {
    const clientId = query.client_id?.trim() || '';
    const externalAdId = query.external_ad_id?.trim() || '';
    if (!clientId || !externalAdId) {
      throw new BadRequestException({ ok: false, error: 'client_id_and_external_ad_id_required' });
    }
    if (!this.isEnabled()) {
      return { ok: true, disabled: true, found: false, client_id: clientId, external_ad_id: externalAdId, link: null };
    }
    if (!(await this.repo.pgReady())) {
      return {
        ok: true,
        disabled: true,
        reason: 'meta_ad_creative_links_not_ready',
        hint: './scripts/apply_pg_ddl_v9_meta_creative_registry.sh',
        found: false,
        client_id: clientId,
        external_ad_id: externalAdId,
        link: null,
      };
    }

    const row = await this.repo.resolveLink(clientId, externalAdId);
    if (!row) {
      return { ok: true, found: false, client_id: clientId, external_ad_id: externalAdId, link: null };
    }
    return {
      ok: true,
      found: true,
      client_id: clientId,
      external_ad_id: externalAdId,
      link: this.mapRow(row as Record<string, unknown>),
    };
  }

  async createLink(
    body: Record<string, unknown>,
    linkedBy?: string | null,
  ): Promise<MetaCreativeLinkMutationResponse> {
    if (!this.isEnabled()) return { ok: true, disabled: true };
    if (!(await this.repo.pgReady())) {
      return { ok: false, error: 'meta_ad_creative_links_not_ready' };
    }

    const clientId = String(body.client_id ?? '').trim();
    const creativeId = String(body.creative_submission_id ?? body.creative_id ?? '').trim();
    const externalAdId = String(body.external_ad_id ?? '').trim();
    const linkSource = String(body.link_source ?? 'manual').trim().toLowerCase();
    if (!clientId || !creativeId || !externalAdId) {
      throw new BadRequestException({ ok: false, error: 'client_id_creative_and_external_ad_id_required' });
    }
    if (!LINK_SOURCES.has(linkSource)) {
      throw new BadRequestException({ ok: false, error: 'invalid_link_source', link_source: linkSource });
    }
    if (!(await this.repo.clientExists(clientId))) {
      throw new BadRequestException({ ok: false, error: 'client_not_found' });
    }

    const creative = await this.repo.getCreativeSubmission(creativeId);
    if (!creative) {
      throw new BadRequestException({ ok: false, error: 'creative_not_found' });
    }
    if (String(creative.client_id) !== clientId) {
      throw new BadRequestException({ ok: false, error: 'creative_client_mismatch' });
    }
    if (String(creative.status) !== 'approved') {
      throw new BadRequestException({ ok: false, error: 'creative_not_approved', status: creative.status });
    }

    const previousId = await this.repo.findActiveLink(clientId, externalAdId);
    const inserted = await this.repo.insertLink({
      clientId,
      creativeSubmissionId: creativeId,
      externalAdId,
      externalAdsetId: body.external_adset_id != null ? String(body.external_adset_id).trim() : null,
      externalCampaignId:
        String(body.external_campaign_id ?? creative.external_campaign_id ?? '').trim() || null,
      externalCreativeId: body.external_creative_id != null ? String(body.external_creative_id).trim() : null,
      linkSource,
      linkedBy,
      note: body.note != null ? String(body.note).trim() : null,
    });

    const link = this.mapRow({
      ...(inserted as Record<string, unknown>),
      title: creative.title,
      status: creative.status,
      asset_url: creative.asset_url,
      version: creative.version,
    });
    return { ok: true, link, replaced: Boolean(previousId) };
  }

  async deactivateLink(linkId: string): Promise<MetaCreativeLinkMutationResponse> {
    if (!this.isEnabled()) return { ok: true, disabled: true };
    if (!(await this.repo.pgReady())) {
      return { ok: false, error: 'meta_ad_creative_links_not_ready' };
    }
    const ok = await this.repo.deactivateLink(linkId);
    if (!ok) throw new NotFoundException({ ok: false, error: 'not_found' });
    return { ok: true };
  }
}
