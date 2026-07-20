import { BadRequestException, Injectable } from '@nestjs/common';
import { SalesSqliteRepository } from './sales-sqlite.repository';
import {
  CreateMarketBody,
  CreatePartnerBody,
  CreateSalesPlanBody,
  CreateTrainingBody,
} from './sales.types';

@Injectable()
export class SalesService {
  constructor(private readonly sqlite: SalesSqliteRepository) {}

  summary() {
    return this.sqlite.fetchSummary();
  }

  listPlans() {
    return { plans: this.sqlite.listPlans() };
  }

  createPlan(body: CreateSalesPlanBody) {
    const title = String(body.title ?? '').trim();
    if (!title) {
      throw new BadRequestException({ error: 'Thiếu tên kế hoạch' });
    }
    const plan = this.sqlite.createPlan({ ...body, title });
    return plan;
  }

  listPipelineCases(stage?: string) {
    return { cases: this.sqlite.listPipelineCases(stage) };
  }

  listPartners(q?: string) {
    return { partners: this.sqlite.listPartners(q) };
  }

  createPartner(body: CreatePartnerBody) {
    const name = String(body.name ?? '').trim();
    if (!name) {
      throw new BadRequestException({ error: 'Thiếu tên đối tác' });
    }
    return this.sqlite.createPartner({ ...body, name });
  }

  listTrainings() {
    return { trainings: this.sqlite.listTrainings() };
  }

  createTraining(body: CreateTrainingBody) {
    const title = String(body.title ?? '').trim();
    if (!title) {
      throw new BadRequestException({ error: 'Thiếu tiêu đề' });
    }
    return this.sqlite.createTraining({ ...body, title });
  }

  listMarket() {
    return { research: this.sqlite.listMarketResearch() };
  }

  createMarket(body: CreateMarketBody) {
    const title = String(body.title ?? '').trim();
    if (!title) {
      throw new BadRequestException({ error: 'Thiếu tiêu đề' });
    }
    return this.sqlite.createMarketResearch({ ...body, title });
  }

  listTransactions() {
    return { transactions: this.sqlite.listTransactions() };
  }

  salesReport() {
    return this.sqlite.fetchSalesReport();
  }
}
