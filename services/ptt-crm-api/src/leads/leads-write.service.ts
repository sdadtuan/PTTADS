import {
  BadRequestException,
  HttpException,
  HttpStatus,
  Injectable,
  ServiceUnavailableException,
} from '@nestjs/common';
import { DomainEventService } from '../events/domain-event.service';
import { MetaConversionSideEffectsService } from '../meta-tracking/meta-conversion-side-effects.service';
import { PgLeadsWriteRepository } from './pg-leads-write.repository';
import { CreateLeadV1Body, LeadV1, PatchLeadV1Body } from './leads.types';

@Injectable()
export class LeadsWriteService {
  constructor(
    private readonly writeRepo: PgLeadsWriteRepository,
    private readonly events: DomainEventService,
    private readonly conversionFx: MetaConversionSideEffectsService,
  ) {}

  async createLead(body: CreateLeadV1Body): Promise<LeadV1> {
    if (!body.full_name?.trim()) {
      throw new BadRequestException({ error: 'full_name is required' });
    }
    try {
      const lead = await this.writeRepo.createLead(body);
      await this.events.emit(
        'LeadCreated',
        'lead',
        String(lead.id),
        {
          lead_id: lead.id,
          channel: body.channel?.trim() || lead.channel || 'staging',
          client_id: body.client_id ?? lead.client_id ?? null,
          external_lead_id: body.external_lead_id ?? lead.external_lead_id ?? null,
        },
      );
      return lead;
    } catch (err) {
      this.rethrowPg(err);
    }
  }

  async patchLead(leadId: number, body: PatchLeadV1Body, actor?: string): Promise<LeadV1> {
    if (
      body.owner_id === undefined &&
      body.status === undefined &&
      body.score === undefined
    ) {
      throw new BadRequestException({ error: 'At least one of owner_id, status, score required' });
    }
    try {
      const result = await this.writeRepo.patchLead(leadId, body);
      if (!result) {
        throw new HttpException({ error: 'Not found' }, HttpStatus.NOT_FOUND);
      }
      if (result.assigned && body.owner_id != null) {
        await this.events.emit('LeadAssigned', 'lead', String(leadId), {
          lead_id: leadId,
          owner_id: body.owner_id,
          assigned_by: body.assigned_by?.trim() || actor || null,
        });
      }
      if (result.status_changed && body.status !== undefined) {
        await this.conversionFx.enqueueConversionEval({
          leadId,
          clientId: result.lead.client_id,
          oldStatus: result.previous_status ?? null,
          newStatus: body.status,
        });
      }
      return result.lead;
    } catch (err) {
      if (err instanceof HttpException) {
        throw err;
      }
      this.rethrowPg(err);
    }
  }

  private rethrowPg(err: unknown): never {
    const message = err instanceof Error ? err.message : String(err);
    if (/connect|ECONNREFUSED|timeout/i.test(message)) {
      throw new ServiceUnavailableException({ error: 'PostgreSQL unavailable', upstream: 'pg' });
    }
    throw err;
  }
}
