import {
  BadRequestException,
  Injectable,
  NotFoundException,
} from '@nestjs/common';
import { ProposalsSqliteRepository } from './proposals-sqlite.repository';
import { CreateProposalBody } from './proposals.types';

@Injectable()
export class ProposalsService {
  constructor(private readonly sqlite: ProposalsSqliteRepository) {}

  list(customerIdRaw?: string) {
    const customerId = Number(customerIdRaw ?? 0);
    if (!Number.isFinite(customerId) || customerId <= 0) {
      throw new BadRequestException({ error: 'Cần customer_id' });
    }
    return { proposals: this.sqlite.listByCustomer(customerId) };
  }

  detail(proposalId: number) {
    const proposal = this.sqlite.getById(proposalId);
    if (!proposal) {
      throw new NotFoundException({ error: 'Không tìm thấy đề xuất' });
    }
    return proposal;
  }

  create(body: CreateProposalBody) {
    const customerId = Number(body.customer_id ?? 0);
    const slugs = (body.service_slugs ?? []).map((s) => String(s).trim()).filter(Boolean);
    if (!customerId || !slugs.length) {
      throw new BadRequestException({ error: 'Thiếu customer_id hoặc service_slugs' });
    }
    return this.sqlite.create({ ...body, customer_id: customerId, service_slugs: slugs });
  }

  generate(proposalId: number) {
    const proposal = this.sqlite.getById(proposalId);
    if (!proposal) {
      throw new NotFoundException({ error: 'Không tìm thấy đề xuất' });
    }
    return {
      ok: true,
      stub: true,
      proposal_id: proposalId,
      sections: {},
      message: 'AI proposal stub — configure ANTHROPIC_API_KEY',
    };
  }

  remove(proposalId: number) {
    const ok = this.sqlite.delete(proposalId);
    if (!ok) {
      throw new NotFoundException({ error: 'Không tìm thấy đề xuất' });
    }
    return {};
  }
}
