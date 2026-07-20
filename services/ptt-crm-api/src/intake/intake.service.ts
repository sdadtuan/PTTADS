import {
  BadRequestException,
  Injectable,
  NotFoundException,
} from '@nestjs/common';
import {
  definitionsPayload,
  getUiDefinition,
} from './intake-definitions.util';
import { IntakeSqliteRepository } from './intake-sqlite.repository';
import { CreateIntakeSessionBody, PatchIntakeSessionBody } from './intake.types';

@Injectable()
export class IntakeService {
  constructor(private readonly sqlite: IntakeSqliteRepository) {}

  getDefinitions() {
    return definitionsPayload();
  }

  getDefinition(slug: string) {
    return getUiDefinition(slug);
  }

  getStats(amId?: number, byAm?: boolean) {
    return this.sqlite.getIntakeStats(amId, byAm);
  }

  resolveEntry(leadId?: number, mode?: string, form?: string) {
    if (!leadId || !Number.isFinite(leadId)) {
      throw new BadRequestException({ ok: false, error: 'Cần lead_id' });
    }
    const result = this.sqlite.resolveIntakeEntry(leadId, mode, form);
    if (!result.ok) {
      throw new NotFoundException(result);
    }
    return result;
  }

  listSessions(leadId?: number, lifecycleId?: number) {
    if (!lifecycleId && !leadId) {
      throw new BadRequestException({ error: 'Cần lifecycle_id hoặc lead_id' });
    }
    const sessions = this.sqlite.listSessions({ leadId, lifecycleId });
    return { sessions };
  }

  getSession(id: number) {
    const session = this.sqlite.getSession(id);
    if (!session) {
      throw new NotFoundException({ error: 'Không tìm thấy phiên' });
    }
    return session;
  }

  createSession(body: CreateIntakeSessionBody) {
    try {
      return this.sqlite.createSession(body);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      throw new BadRequestException({ error: msg });
    }
  }

  updateSession(id: number, body: PatchIntakeSessionBody) {
    const updated = this.sqlite.updateSession(id, body);
    if (!updated) {
      throw new NotFoundException({ error: 'Không tìm thấy phiên' });
    }
    return updated;
  }

  completeSession(id: number, actorId: number | null) {
    try {
      const updated = this.sqlite.completeSession(id, actorId);
      if (!updated) {
        throw new NotFoundException({ error: 'Không tìm thấy phiên' });
      }
      return updated;
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      if (msg.includes('quyết định')) {
        throw new BadRequestException({ error: msg });
      }
      throw err;
    }
  }

  reopenSession(id: number) {
    const updated = this.sqlite.reopenSession(id);
    if (!updated) {
      throw new NotFoundException({ error: 'Không tìm thấy phiên' });
    }
    return updated;
  }

  generateAiSummary(id: number) {
    const session = this.sqlite.getSession(id);
    if (!session) {
      throw new NotFoundException({ error: 'Không tìm thấy phiên' });
    }
    const hasKey = Boolean(String(process.env.ANTHROPIC_API_KEY ?? '').trim());
    if (!hasKey) {
      return {
        ...session,
        ai_summary: `[stub] Intake #${id} — configure ANTHROPIC_API_KEY for AI summary`,
        stub: true,
      };
    }
    const updated = this.sqlite.saveAiSummaryStub(id);
    if (!updated) {
      throw new NotFoundException({ error: 'Không tìm thấy phiên' });
    }
    return updated;
  }
}
