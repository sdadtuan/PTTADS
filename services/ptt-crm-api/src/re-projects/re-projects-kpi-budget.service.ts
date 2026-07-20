import { BadRequestException, Injectable, NotFoundException } from '@nestjs/common';
import { catalogTs } from '../catalog/catalog-slug.util';
import { computeKpiBoardStats } from './re-projects-inventory.util';
import { ReProjectsSqliteRepository } from './re-projects-sqlite.repository';
import {
  RefreshLeadsNewKpiBody,
  SaveBudgetLineBody,
  SaveKpiBody,
  SaveRiskBody,
} from './re-projects.types';

@Injectable()
export class ReProjectsKpiBudgetService {
  constructor(private readonly sqlite: ReProjectsSqliteRepository) {}

  private assertProject(id: number): void {
    if (!this.sqlite.fetchProject(id)) {
      throw new NotFoundException({ error: 'Không tìm thấy dự án.' });
    }
  }

  listKpiMetrics(reOnly = true) {
    return { metrics: this.sqlite.listCrmKpiMetrics(reOnly) };
  }

  listKpis(projectId: number) {
    const kpis = this.sqlite.listKpis(projectId);
    return { kpis, board: computeKpiBoardStats(kpis) };
  }

  createKpi(projectId: number, body: SaveKpiBody) {
    try {
      return this.sqlite.saveKpi(projectId, body as Record<string, unknown>, undefined, catalogTs());
    } catch (e) {
      throw new BadRequestException({ error: String((e as Error).message) });
    }
  }

  updateKpi(projectId: number, kpiId: number, body: SaveKpiBody) {
    try {
      return this.sqlite.saveKpi(projectId, body as Record<string, unknown>, kpiId, catalogTs());
    } catch (e) {
      throw new BadRequestException({ error: String((e as Error).message) });
    }
  }

  deleteKpi(projectId: number, kpiId: number) {
    this.sqlite.deleteKpi(projectId, kpiId);
    return { ok: true };
  }

  syncKpisToStaff(projectId: number) {
    this.assertProject(projectId);
    return this.sqlite.syncProjectKpisToStaff(projectId, catalogTs());
  }

  pullKpisFromStaff(projectId: number) {
    this.assertProject(projectId);
    return this.sqlite.pullProjectKpisFromStaff(projectId, catalogTs());
  }

  refreshLeadsNewKpi(projectId: number, body: RefreshLeadsNewKpiBody = {}) {
    this.assertProject(projectId);
    return this.sqlite.refreshProjectReLeadsNewKpi(projectId, {
      periodMonth: body.period_month,
      ts: catalogTs(),
    });
  }

  listRisks(projectId: number) {
    return { risks: this.sqlite.listRisks(projectId) };
  }

  createRisk(projectId: number, body: SaveRiskBody) {
    try {
      return this.sqlite.saveRisk(projectId, body as Record<string, unknown>, undefined, catalogTs());
    } catch (e) {
      throw new BadRequestException({ error: String((e as Error).message) });
    }
  }

  updateRisk(projectId: number, riskId: number, body: SaveRiskBody) {
    try {
      return this.sqlite.saveRisk(projectId, body as Record<string, unknown>, riskId, catalogTs());
    } catch (e) {
      throw new BadRequestException({ error: String((e as Error).message) });
    }
  }

  deleteRisk(projectId: number, riskId: number) {
    this.sqlite.deleteRisk(projectId, riskId);
    return { ok: true };
  }

  listBudget(projectId: number) {
    return { lines: this.sqlite.listBudgetLines(projectId) };
  }

  createBudgetLine(projectId: number, body: SaveBudgetLineBody) {
    try {
      return this.sqlite.saveBudgetLine(projectId, body as Record<string, unknown>, undefined, catalogTs());
    } catch (e) {
      throw new BadRequestException({ error: String((e as Error).message) });
    }
  }

  updateBudgetLine(projectId: number, lineId: number, body: SaveBudgetLineBody) {
    try {
      return this.sqlite.saveBudgetLine(projectId, body as Record<string, unknown>, lineId, catalogTs());
    } catch (e) {
      throw new BadRequestException({ error: String((e as Error).message) });
    }
  }

  deleteBudgetLine(projectId: number, lineId: number) {
    this.sqlite.deleteBudgetLine(projectId, lineId);
    return { ok: true };
  }
}
