import { BadRequestException, Injectable } from '@nestjs/common';
import { CrmLeadsLegacyService } from '../crm-leads-legacy/crm-leads-legacy.service';
import { CrmLeadsSqliteRepository } from '../crm-leads-legacy/crm-leads-sqlite.repository';
import { computeFirstCallSla, slaMatchesFilter } from './cskh-board-sla.util';
import { CskhBoardRepository } from './cskh-board.repository';
import {
  CskhBoardQuery,
  CskhBoardResponse,
  CskhBoardRow,
  CskhBulkAssignBody,
  CskhBulkRescheduleBody,
} from './cskh-board.types';

@Injectable()
export class CskhBoardService {
  constructor(
    private readonly repo: CskhBoardRepository,
    private readonly sqlite: CrmLeadsSqliteRepository,
    private readonly legacy: CrmLeadsLegacyService,
  ) {}

  async getBoard(query: CskhBoardQuery): Promise<CskhBoardResponse> {
    const limit = Math.max(1, Math.min(Number(query.limit ?? 50), 200));
    const offset = Math.max(0, Number(query.offset ?? 0));
    const slaFilter = query.sla_filter ?? 'all';

    const { leads } = await this.repo.listLeadCandidates({ ...query, sla_filter: slaFilter, limit });
    const ids = leads.map((r) => Number(r.sqlite_lead_id));
    const firstCalls = this.sqlite.firstCallAtByLeadIds(ids);
    const followUps = this.sqlite.nextFollowUpByLeadIds(ids);
    const ownerIds = leads.map((r) => Number(r.owner_id ?? 0)).filter((id) => id > 0);
    const ownerNames = this.sqlite.staffNamesByIds(ownerIds);

    const enriched: CskhBoardRow[] = leads.map((row) => {
      const base = CskhBoardRepository.toBoardRowBase(row);
      const firstCallAt = firstCalls.get(base.id) ?? null;
      const sla = computeFirstCallSla({
        status: base.status,
        receivedAt: base.received_at,
        createdAt: base.created_at,
        firstCallAt,
      });
      return {
        ...base,
        owner_name: base.owner_id ? ownerNames.get(base.owner_id) ?? null : null,
        first_call_at: firstCallAt,
        sla_state: sla.sla_state,
        sla_minutes_elapsed: sla.sla_minutes_elapsed,
        sla_deadline_at: sla.sla_deadline_at,
        next_follow_up_at: followUps.get(base.id) ?? null,
      };
    });

    const filtered = enriched.filter((row) =>
      slaMatchesFilter(row.sla_state as 'ok' | 'warning' | 'breach' | 'na', slaFilter),
    );
    const summary = {
      total: filtered.length,
      breach: filtered.filter((r) => r.sla_state === 'breach').length,
      warning: filtered.filter((r) => r.sla_state === 'warning').length,
      ok: filtered.filter((r) => r.sla_state === 'ok').length,
    };
    const page = filtered.slice(offset, offset + limit);

    return {
      ok: true,
      items: page,
      total: filtered.length,
      limit,
      offset,
      summary,
    };
  }

  async exportCsv(query: CskhBoardQuery): Promise<string> {
    const board = await this.getBoard({ ...query, limit: 500, offset: 0 });
    const header = [
      'id',
      'full_name',
      'phone',
      'status',
      'source',
      'channel',
      'owner_id',
      'owner_name',
      'received_at',
      'first_call_at',
      'sla_state',
      'sla_minutes_elapsed',
      'next_follow_up_at',
    ];
    const lines = [header.join(',')];
    for (const row of board.items) {
      lines.push(
        [
          row.id,
          csvCell(row.full_name),
          csvCell(row.phone),
          csvCell(row.status),
          csvCell(row.source),
          csvCell(row.channel),
          row.owner_id ?? '',
          csvCell(row.owner_name ?? ''),
          csvCell(row.received_at),
          csvCell(row.first_call_at ?? ''),
          row.sla_state,
          row.sla_minutes_elapsed ?? '',
          csvCell(row.next_follow_up_at ?? ''),
        ].join(','),
      );
    }
    return lines.join('\n');
  }

  async bulkAssign(body: CskhBulkAssignBody, actor: string) {
    const leadIds = [...new Set((body.lead_ids ?? []).map((id) => Number(id)).filter((id) => id > 0))];
    const toUserId = Number(body.to_user_id);
    const reason = String(body.reason ?? '').trim();
    if (!leadIds.length) {
      throw new BadRequestException({ error: 'lead_ids_required' });
    }
    if (!toUserId) {
      throw new BadRequestException({ error: 'to_user_id_invalid' });
    }
    if (reason.length < 3) {
      throw new BadRequestException({ error: 'reason_required' });
    }

    const results: Array<{ lead_id: number; ok: boolean; error?: string }> = [];
    for (const leadId of leadIds) {
      try {
        await this.legacy.assignLead(leadId, { to_user_id: toUserId, reason }, actor);
        results.push({ lead_id: leadId, ok: true });
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        results.push({ lead_id: leadId, ok: false, error: msg });
      }
    }
    const okCount = results.filter((r) => r.ok).length;
    return { ok: okCount === leadIds.length, assigned: okCount, total: leadIds.length, results };
  }

  async bulkReschedule(body: CskhBulkRescheduleBody, actor: string, userId: number | null) {
    const leadIds = [...new Set((body.lead_ids ?? []).map((id) => Number(id)).filter((id) => id > 0))];
    const followUpAt = String(body.follow_up_at ?? '').trim();
    const note = String(body.note ?? 'Batch reschedule từ CSKH board').trim();
    if (!leadIds.length) {
      throw new BadRequestException({ error: 'lead_ids_required' });
    }
    if (!followUpAt) {
      throw new BadRequestException({ error: 'follow_up_at_required' });
    }

    const results: Array<{ lead_id: number; ok: boolean }> = [];
    for (const leadId of leadIds) {
      await this.legacy.createActivity(
        leadId,
        {
          activity_type: 'note',
          content: note,
          next_action: 'Follow-up',
          next_action_at: followUpAt,
        },
        actor,
        userId,
      );
      results.push({ lead_id: leadId, ok: true });
    }
    return { ok: true, rescheduled: results.length, results };
  }
}

function csvCell(value: string): string {
  const v = String(value ?? '');
  if (/[",\n]/.test(v)) return `"${v.replace(/"/g, '""')}"`;
  return v;
}
