import {
  BadRequestException,
  Injectable,
  NotFoundException,
  ServiceUnavailableException,
} from '@nestjs/common';
import { ReProjectsAccountingRepository } from './re-projects-accounting.repository';
import {
  AccountingDeps,
  aiProjectFinanceQuery,
  applyPredictedRisksToRegister,
  buildAccountingExportSheets,
  computeAccountingDashboard,
  deleteCashFlowLine,
  forecastFinancialOutlook,
  importCashFlowCsv,
  listCashFlowLines,
  predictFinancialRisks,
  saveCashFlowLine,
  syncBudgetFromPlans,
  syncRevenueFromInventory,
} from './re-projects-accounting.util';
import { ReProjectsSqliteRepository } from './re-projects-sqlite.repository';
import {
  AccountingAiAskBody,
  ApplyPredictedRisksBody,
  ImportCashFlowBody,
  SaveCashFlowBody,
} from './re-projects.types';

@Injectable()
export class ReProjectsAccountingService {
  private readonly deps: AccountingDeps;

  constructor(
    private readonly accounting: ReProjectsAccountingRepository,
    private readonly projects: ReProjectsSqliteRepository,
  ) {
    this.deps = { accounting, projects };
  }

  private ensureProject(projectId: number): void {
    if (!this.projects.fetchProject(projectId)) {
      throw new NotFoundException({ error: 'Không tìm thấy dự án.' });
    }
  }

  dashboard(projectId: number) {
    this.ensureProject(projectId);
    return computeAccountingDashboard(this.deps, projectId);
  }

  listCashFlow(
    projectId: number,
    filters: { flow_type?: string; category?: string; status?: string },
  ) {
    this.ensureProject(projectId);
    return { lines: listCashFlowLines(this.deps, projectId, filters) };
  }

  createCashFlow(projectId: number, body: SaveCashFlowBody, createdBy = '') {
    this.ensureProject(projectId);
    try {
      return saveCashFlowLine(this.deps, projectId, body, { createdBy, ts: this.accounting.nowTs() });
    } catch (e) {
      throw new BadRequestException({ error: String((e as Error).message) });
    }
  }

  updateCashFlow(projectId: number, lineId: number, body: SaveCashFlowBody, createdBy = '') {
    this.ensureProject(projectId);
    try {
      return saveCashFlowLine(this.deps, projectId, body, {
        lineId,
        createdBy,
        ts: this.accounting.nowTs(),
      });
    } catch (e) {
      throw new BadRequestException({ error: String((e as Error).message) });
    }
  }

  removeCashFlow(projectId: number, lineId: number) {
    this.ensureProject(projectId);
    deleteCashFlowLine(this.deps, projectId, lineId);
    return { ok: true };
  }

  importCashFlow(projectId: number, body: ImportCashFlowBody, createdBy = '') {
    this.ensureProject(projectId);
    const csvText = String(body.csv ?? '');
    if (!csvText.trim()) {
      throw new BadRequestException({ error: 'Thiếu nội dung CSV.' });
    }
    return importCashFlowCsv(this.deps, projectId, csvText, {
      createdBy,
      ts: this.accounting.nowTs(),
    });
  }

  syncFromPlans(projectId: number) {
    try {
      return syncBudgetFromPlans(this.deps, projectId, this.accounting.nowTs());
    } catch (e) {
      const msg = String((e as Error).message);
      if (msg.includes('Không tìm thấy')) throw new NotFoundException({ error: msg });
      throw new BadRequestException({ error: msg });
    }
  }

  syncInventoryRevenue(projectId: number, createdBy = '') {
    try {
      return syncRevenueFromInventory(this.deps, projectId, {
        ts: this.accounting.nowTs(),
        createdBy,
      });
    } catch (e) {
      const msg = String((e as Error).message);
      if (msg.includes('Không tìm thấy')) throw new NotFoundException({ error: msg });
      throw new BadRequestException({ error: msg });
    }
  }

  aiAsk(projectId: number, body: AccountingAiAskBody) {
    this.ensureProject(projectId);
    const question = String(body.question ?? body.q ?? '').trim();
    if (!question) {
      throw new BadRequestException({ error: 'Thiếu câu hỏi.' });
    }
    try {
      return aiProjectFinanceQuery(this.deps, question, {
        reProjectId: projectId,
        ts: this.accounting.nowTs(),
      });
    } catch (e) {
      if (e instanceof ServiceUnavailableException) throw e;
      throw new BadRequestException({ error: String((e as Error).message) });
    }
  }

  exportBundle(projectId: number) {
    try {
      const sheets = buildAccountingExportSheets(this.deps, projectId);
      const proj = this.projects.fetchProject(projectId);
      const code = String(proj?.code ?? `du-an-${projectId}`).trim() || `du-an-${projectId}`;
      const stamp = new Date().toISOString().slice(0, 10);
      return {
        filename: `ke-toan-${code}-${stamp}`.replace(/\s+/g, '-'),
        format: 'json',
        sheets,
      };
    } catch (e) {
      const msg = String((e as Error).message);
      if (msg.includes('Không tìm thấy')) throw new NotFoundException({ error: msg });
      throw new BadRequestException({ error: msg });
    }
  }

  riskPredictions(projectId: number) {
    try {
      return predictFinancialRisks(this.deps, projectId);
    } catch (e) {
      const msg = String((e as Error).message);
      if (msg.includes('Không tìm thấy')) throw new NotFoundException({ error: msg });
      throw new BadRequestException({ error: msg });
    }
  }

  forecast(projectId: number, monthsAheadRaw?: string) {
    let monthsAhead = 3;
    if (monthsAheadRaw != null) {
      const parsed = Number(monthsAheadRaw);
      if (Number.isFinite(parsed)) {
        monthsAhead = Math.max(1, Math.min(12, Math.trunc(parsed)));
      }
    }
    try {
      return forecastFinancialOutlook(this.deps, projectId, { monthsAhead });
    } catch (e) {
      const msg = String((e as Error).message);
      if (msg.includes('Không tìm thấy')) throw new NotFoundException({ error: msg });
      throw new BadRequestException({ error: msg });
    }
  }

  applyRiskPredictions(projectId: number, body: ApplyPredictedRisksBody) {
    try {
      const codes = Array.isArray(body.codes) ? body.codes.map(String) : undefined;
      return applyPredictedRisksToRegister(this.deps, projectId, {
        codes,
        ts: this.accounting.nowTs(),
      });
    } catch (e) {
      const msg = String((e as Error).message);
      if (msg.includes('Không tìm thấy')) throw new NotFoundException({ error: msg });
      throw new BadRequestException({ error: msg });
    }
  }
}
