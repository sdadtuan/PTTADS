import {
  BadRequestException,
  Injectable,
  NotFoundException,
} from '@nestjs/common';
import { CustomersSqliteRepository } from './customers-sqlite.repository';
import {
  CreateCustomerBody,
  CreateIssueBody,
  CreatePurchaseBody,
  CreateRelationBody,
  GenerateBriefBody,
  PatchCustomerBody,
  PatchIssueBody,
  PatchPurchaseBody,
  PatchRelationBody,
} from './customers.types';

@Injectable()
export class CustomersService {
  constructor(private readonly sqlite: CustomersSqliteRepository) {}

  list(q?: string, limit?: number) {
    const lim = limit ? Number(limit) : 200;
    const customers = this.sqlite.listCustomers(q, Number.isFinite(lim) ? lim : 200);
    return { customers };
  }

  detail(id: number) {
    const customer = this.sqlite.getCustomerById(id);
    if (!customer) {
      throw new NotFoundException({ error: 'Không tìm thấy khách hàng' });
    }
    const relations = this.sqlite.fetchRelations(id);
    const purchases = this.sqlite.fetchPurchases(id);
    const issues = this.sqlite.fetchIssues(id);
    const stats = this.sqlite.computeStats(relations, purchases, issues);
    return { customer, relations, purchases, issues, stats };
  }

  create(body: CreateCustomerBody) {
    const name = String(body.name ?? '').trim();
    const phone = String(body.phone ?? '').trim();
    const email = String(body.email ?? '').trim();
    if (!name) {
      throw new BadRequestException({ error: 'Cần tên khách hàng' });
    }
    if (!phone && !email) {
      throw new BadRequestException({ error: 'Cần ít nhất số điện thoại hoặc email' });
    }
    const customer = this.sqlite.createCustomer(body);
    return customer;
  }

  patch(id: number, body: PatchCustomerBody) {
    const existing = this.sqlite.getCustomerById(id);
    if (!existing) {
      throw new NotFoundException({ error: 'Không tìm thấy khách hàng' });
    }
    const mergedName = 'name' in body ? String(body.name ?? '').trim() : existing.name;
    const mergedPhone = 'phone' in body ? String(body.phone ?? '').trim() : existing.phone;
    const mergedEmail = 'email' in body ? String(body.email ?? '').trim() : existing.email;
    if (!mergedName) {
      throw new BadRequestException({ error: 'Tên không được trống' });
    }
    if (!mergedPhone && !mergedEmail) {
      throw new BadRequestException({ error: 'Cần ít nhất SĐT hoặc email' });
    }
    const customer = this.sqlite.patchCustomer(id, body);
    if (!customer) {
      throw new NotFoundException({ error: 'Không tìm thấy khách hàng' });
    }
    return customer;
  }

  private ensureCustomer(id: number) {
    const customer = this.sqlite.getCustomerById(id);
    if (!customer) {
      throw new NotFoundException({ error: 'Không tìm thấy khách hàng' });
    }
    return customer;
  }

  createRelation(customerId: number, body: CreateRelationBody) {
    this.ensureCustomer(customerId);
    const fullName = String(body.full_name ?? '').trim();
    if (!fullName) {
      throw new BadRequestException({ error: 'Cần họ tên người liên quan' });
    }
    return this.sqlite.createRelation(customerId, body);
  }

  patchRelation(customerId: number, relationId: number, body: PatchRelationBody) {
    this.ensureCustomer(customerId);
    const mergedName = 'full_name' in body ? String(body.full_name ?? '').trim() : undefined;
    if (mergedName !== undefined && !mergedName) {
      throw new BadRequestException({ error: 'Họ tên không được trống' });
    }
    const relation = this.sqlite.patchRelation(customerId, relationId, body);
    if (!relation) {
      throw new NotFoundException({ error: 'Không tìm thấy quan hệ' });
    }
    return relation;
  }

  deleteRelation(customerId: number, relationId: number) {
    this.ensureCustomer(customerId);
    const ok = this.sqlite.deleteRelation(customerId, relationId);
    if (!ok) {
      throw new NotFoundException({ error: 'Không tìm thấy quan hệ' });
    }
    return { ok: true };
  }

  createPurchase(customerId: number, body: CreatePurchaseBody) {
    this.ensureCustomer(customerId);
    const product = String(body.product_name ?? '').trim();
    if (!product) {
      throw new BadRequestException({ error: 'Cần tên sản phẩm / dịch vụ' });
    }
    return this.sqlite.createPurchase(customerId, body);
  }

  patchPurchase(customerId: number, purchaseId: number, body: PatchPurchaseBody) {
    this.ensureCustomer(customerId);
    const purchase = this.sqlite.patchPurchase(customerId, purchaseId, body);
    if (!purchase) {
      throw new NotFoundException({ error: 'Không tìm thấy giao dịch' });
    }
    return purchase;
  }

  deletePurchase(customerId: number, purchaseId: number) {
    this.ensureCustomer(customerId);
    const ok = this.sqlite.deletePurchase(customerId, purchaseId);
    if (!ok) {
      throw new NotFoundException({ error: 'Không tìm thấy giao dịch' });
    }
    return { ok: true };
  }

  createIssue(customerId: number, body: CreateIssueBody) {
    this.ensureCustomer(customerId);
    const title = String(body.title ?? '').trim();
    if (!title) {
      throw new BadRequestException({ error: 'Cần tiêu đề vấn đề' });
    }
    return this.sqlite.createIssue(customerId, body);
  }

  patchIssue(customerId: number, issueId: number, body: PatchIssueBody) {
    this.ensureCustomer(customerId);
    const issue = this.sqlite.patchIssue(customerId, issueId, body);
    if (!issue) {
      throw new NotFoundException({ error: 'Không tìm thấy vấn đề' });
    }
    return issue;
  }

  latestBrief(customerId: number) {
    this.ensureCustomer(customerId);
    const brief = this.sqlite.getLatestBrief(customerId);
    return brief ?? {};
  }

  generateBrief(customerId: number, _body: GenerateBriefBody) {
    this.ensureCustomer(customerId);
    return {
      ok: true,
      stub: true,
      brief: { summary: 'AI brief stub — configure ANTHROPIC_API_KEY' },
    };
  }
}
