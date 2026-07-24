import {
  BadRequestException,
  Injectable,
  NotFoundException,
  ServiceUnavailableException,
} from '@nestjs/common';
import { MetaTrackingRepository } from './meta-tracking.repository';
import {
  ConversionRuleMutationResponse,
  ConversionRulesListResponse,
  CreateConversionRuleBody,
  PatchConversionRuleBody,
} from './meta-tracking.types';

@Injectable()
export class MetaConversionRulesService {
  constructor(private readonly repo: MetaTrackingRepository) {}

  isTrackingEnabled(): boolean {
    return ['1', 'true', 'yes', 'on'].includes(
      (process.env.PTT_META_TRACKING_ENABLED ?? '0').trim().toLowerCase(),
    );
  }

  private async ensureRulesReady(): Promise<void> {
    if (!(await this.repo.pgMetaConversionRulesReady())) {
      throw new ServiceUnavailableException({
        ok: false,
        error: 'meta_conversion_rules_not_ready',
      });
    }
  }

  async listRules(query: { client_id?: string }): Promise<ConversionRulesListResponse> {
    if (!this.isTrackingEnabled()) {
      return { ok: true, disabled: true, rules: [], count: 0 };
    }

    await this.ensureRulesReady();
    const clientId = query.client_id?.trim() || undefined;
    const rules = await this.repo.listConversionRules(clientId);
    return { ok: true, rules, count: rules.length };
  }

  async createRule(body: CreateConversionRuleBody): Promise<ConversionRuleMutationResponse> {
    if (!this.isTrackingEnabled()) {
      throw new ServiceUnavailableException({ ok: false, error: 'meta_tracking_disabled' });
    }

    await this.ensureRulesReady();
    if (!body.lead_status?.trim() || !body.event_name?.trim()) {
      throw new BadRequestException({ error: 'lead_status and event_name required' });
    }

    try {
      const rule = await this.repo.createConversionRule(body);
      return { ok: true, rule };
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      if (/duplicate key|idx_meta_conversion_rules_uniq/i.test(message)) {
        throw new BadRequestException({ error: 'rule_already_exists' });
      }
      throw err;
    }
  }

  async patchRule(
    ruleId: string,
    body: PatchConversionRuleBody,
  ): Promise<ConversionRuleMutationResponse> {
    if (!this.isTrackingEnabled()) {
      throw new ServiceUnavailableException({ ok: false, error: 'meta_tracking_disabled' });
    }

    await this.ensureRulesReady();
    if (
      body.enabled === undefined &&
      body.value_vnd === undefined &&
      body.require_meta_attribution === undefined &&
      body.notes === undefined
    ) {
      throw new BadRequestException({
        error: 'At least one of enabled, value_vnd, require_meta_attribution, notes required',
      });
    }

    const rule = await this.repo.patchConversionRule(ruleId.trim(), body);
    if (!rule) {
      throw new NotFoundException({ error: 'Not found' });
    }
    return { ok: true, rule };
  }
}
