import { BadRequestException, Injectable, NotFoundException } from '@nestjs/common';
import { buildExportJsonBundle, ExportReportType } from './re-projects-export.util';
import { ReProjectsSqliteRepository } from './re-projects-sqlite.repository';
import {
  AddProjectStaffBody,
  SaveProjectLeadConfigBody,
  UpdateProjectStaffBody,
} from './re-projects.types';

@Injectable()
export class ReProjectsOpsService {
  constructor(private readonly sqlite: ReProjectsSqliteRepository) {}

  listStaff(projectId: number) {
    try {
      const staff = this.sqlite.listProjectStaff(projectId, true);
      return { project_id: projectId, staff };
    } catch (e) {
      const msg = String((e as Error).message);
      if (msg.includes('Không tìm thấy')) throw new NotFoundException({ error: msg });
      throw new BadRequestException({ error: msg });
    }
  }

  addStaff(projectId: number, body: AddProjectStaffBody) {
    const staffId = Number(body.staff_id ?? 0);
    if (!Number.isFinite(staffId) || staffId <= 0) {
      throw new BadRequestException({ error: 'Thiếu staff_id.' });
    }
    try {
      const staff = this.sqlite.addProjectStaff(projectId, {
        staff_id: staffId,
        role: String(body.role ?? 'sales'),
        assign_enabled: body.assign_enabled ?? true,
        sort_order: Number(body.sort_order ?? 0),
        scope_product_lines: Array.isArray(body.scope_product_lines) ? body.scope_product_lines : undefined,
        scope_zones: Array.isArray(body.scope_zones) ? body.scope_zones : undefined,
      });
      return { staff };
    } catch (e) {
      throw new BadRequestException({ error: String((e as Error).message) });
    }
  }

  updateStaff(projectId: number, staffId: number, body: UpdateProjectStaffBody) {
    try {
      const staff = this.sqlite.updateProjectStaff(projectId, staffId, body);
      return { staff };
    } catch (e) {
      throw new BadRequestException({ error: String((e as Error).message) });
    }
  }

  removeStaff(projectId: number, staffId: number) {
    try {
      this.sqlite.removeProjectStaff(projectId, staffId);
      return { ok: true };
    } catch (e) {
      throw new BadRequestException({ error: String((e as Error).message) });
    }
  }

  getLeadConfig(projectId: number) {
    try {
      const config = this.sqlite.getProjectLeadConfig(projectId);
      return { config };
    } catch (e) {
      const msg = String((e as Error).message);
      if (msg.includes('Không tìm thấy')) throw new NotFoundException({ error: msg });
      throw new BadRequestException({ error: msg });
    }
  }

  saveLeadConfig(projectId: number, body: SaveProjectLeadConfigBody, updatedBy = '') {
    try {
      const config = this.sqlite.saveProjectLeadConfig(projectId, body, updatedBy);
      return { config };
    } catch (e) {
      throw new BadRequestException({ error: String((e as Error).message) });
    }
  }

  webhookTest(projectId: number) {
    const proj = this.sqlite.fetchProject(projectId);
    if (!proj) {
      throw new NotFoundException({ error: 'Không tìm thấy dự án.' });
    }
    return { ok: true, stub: true };
  }

  workflow(projectId: number) {
    try {
      return this.sqlite.computeProjectWorkflow(projectId);
    } catch (e) {
      const msg = String((e as Error).message);
      if (msg.includes('Không tìm thấy')) throw new NotFoundException({ error: msg });
      throw new BadRequestException({ error: msg });
    }
  }

  exportBundle(projectId: number, reportRaw?: string) {
    const report = (String(reportRaw ?? 'full').trim().toLowerCase() || 'full') as ExportReportType;
    const allowed: ExportReportType[] = [
      'full',
      'summary',
      'workflow',
      'kpis',
      'products',
      'risks',
      'budget',
      'plans',
    ];
    const reportType = allowed.includes(report) ? report : 'full';
    try {
      const pack = this.sqlite.fetchProjectExportData(projectId);
      return buildExportJsonBundle(reportType, {
        project: pack.project,
        summary: pack.summary,
        workflow: pack.workflow,
        kpis: pack.kpis,
        products: pack.products,
        risks: pack.risks,
        budget: pack.budget,
      });
    } catch (e) {
      const msg = String((e as Error).message);
      if (msg.includes('Không tìm thấy')) throw new NotFoundException({ error: msg });
      throw new BadRequestException({ error: msg });
    }
  }
}
