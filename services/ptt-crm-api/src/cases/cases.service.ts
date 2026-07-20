import {
  BadRequestException,
  Injectable,
  NotFoundException,
} from '@nestjs/common';
import { CasesSqliteRepository } from './cases-sqlite.repository';
import {
  CreateCareReportBody,
  CreateCaseEventBody,
  PatchCaseBody,
} from './cases.types';

@Injectable()
export class CasesService {
  constructor(private readonly sqlite: CasesSqliteRepository) {}

  list(q?: string, staffId?: number) {
    const qRaw = String(q ?? '').trim().toLowerCase();
    const cases = this.sqlite.listCases(staffId);
    const filtered = qRaw
      ? cases.filter((c) => {
          const hay = [
            c.title,
            c.description,
            c.assigned_to,
            c.customer_name,
            c.customer_phone,
            c.customer_email,
            c.customer_company,
          ]
            .map((v) => String(v ?? '').toLowerCase())
            .join(' ');
          return hay.includes(qRaw);
        })
      : cases;
    return { cases: filtered, staff_id: staffId ?? null };
  }

  detail(id: number) {
    const caseRow = this.sqlite.getCaseById(id);
    if (!caseRow) {
      throw new NotFoundException({ error: 'Case not found' });
    }
    const events = this.sqlite.listEvents(id);
    const careReports = this.sqlite.listCareReports(id);
    return {
      ...caseRow,
      events,
      care_reports: careReports,
      last_care_report: careReports[0] ?? null,
    };
  }

  patch(id: number, body: PatchCaseBody) {
    if ('status' in body && body.status != null) {
      const ns = String(body.status).trim();
      if (!this.sqlite.isValidStatus(ns)) {
        throw new BadRequestException({ error: 'status không hợp lệ' });
      }
    }
    const updated = this.sqlite.patchCase(id, body);
    if (!updated) {
      throw new NotFoundException({ error: 'Case not found' });
    }
    return updated;
  }

  addEvent(id: number, body: CreateCaseEventBody) {
    const text = String(body.body ?? '').trim();
    if (!text) {
      throw new BadRequestException({ error: 'Nội dung ghi chú không được để trống' });
    }
    if (text.length > 8000) {
      throw new BadRequestException({ error: 'Ghi chú quá dài' });
    }
    const existing = this.sqlite.getCaseById(id);
    if (!existing) {
      throw new NotFoundException({ error: 'Case not found' });
    }
    return this.sqlite.createEvent(id, text);
  }

  addCareReport(id: number, body: CreateCareReportBody) {
    const summary = String(body.summary ?? '').trim();
    if (!summary) {
      throw new BadRequestException({ error: 'Nội dung báo cáo không được để trống' });
    }
    if (summary.length > 4000) {
      throw new BadRequestException({ error: 'Báo cáo quá dài' });
    }
    try {
      return this.sqlite.createCareReport(id, body);
    } catch {
      throw new NotFoundException({ error: 'Case not found' });
    }
  }
}
