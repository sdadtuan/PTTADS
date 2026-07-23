import {
  BadRequestException,
  Injectable,
  NotFoundException,
} from '@nestjs/common';
import { AppConfigService } from '../config/app-config.service';
import { SopSqliteRepository } from './sop-sqlite.repository';
import { CreateSopRunBody, isValidDateYmd } from './sop.types';

@Injectable()
export class SopService {
  constructor(
    private readonly sqlite: SopSqliteRepository,
    private readonly config: AppConfigService,
  ) {}

  listTemplates(includeInactive?: string) {
    const raw = String(includeInactive ?? '').trim().toLowerCase();
    const incl = ['1', 'true', 'yes', 'all'].includes(raw);
    const templates = this.sqlite.listTemplates(incl);
    return { templates };
  }

  getTemplate(id: number) {
    const template = this.sqlite.getTemplateById(id);
    if (!template) {
      throw new NotFoundException({ error: 'Không tìm thấy template' });
    }
    const steps = this.sqlite.listSteps(id);
    return { template, steps };
  }

  listTemplateSteps(id: number) {
    const template = this.sqlite.getTemplateById(id);
    if (!template) {
      throw new NotFoundException({ error: 'Không tìm thấy template' });
    }
    return { steps: [] };
  }

  listRuns(status?: string) {
    let statusFilter = String(status ?? 'active').trim().toLowerCase();
    if (!this.sqlite.isValidRunStatus(statusFilter) && statusFilter !== 'all') {
      statusFilter = 'active';
    }
    const runs = this.sqlite.listRuns(statusFilter);
    return { runs };
  }

  createRun(body: CreateSopRunBody) {
    const name = String(body.name ?? '').trim();
    if (!name) {
      throw new BadRequestException({ error: 'Thiếu tên SOP Run' });
    }
    const startDate = String(body.start_date ?? '').trim();
    if (startDate && !isValidDateYmd(startDate)) {
      throw new BadRequestException({ error: 'start_date phải YYYY-MM-DD' });
    }

    if (body.campaign_id != null && body.campaign_id !== 0) {
      const cid = Number(body.campaign_id);
      if (Number.isFinite(cid) && cid > 0 && !this.sqlite.campaignExists(cid)) {
        throw new NotFoundException({ error: 'Chiến dịch không tồn tại' });
      }
    }

    if (body.template_id != null && body.template_id !== 0) {
      const templateId = Number(body.template_id);
      if (Number.isFinite(templateId) && templateId > 0) {
        const tpl = this.sqlite.getTemplateById(templateId);
        if (!tpl) {
          throw new NotFoundException({ error: 'Template SOP không tồn tại' });
        }
      }
    }

    const generateTasks = body.generate_tasks !== false;
    return this.sqlite.createRun(body, generateTasks);
  }

  listOverdueTasks(limit?: string) {
    const raw = String(limit ?? '100').trim();
    const n = Number(raw);
    const tasks = this.sqlite.listOverdueTasks(Number.isFinite(n) && n > 0 ? n : 100);
    return {
      overdue_enabled: this.config.sopOverdueEscalate,
      total: tasks.length,
      tasks,
    };
  }
}
