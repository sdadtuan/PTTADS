import {
  BadRequestException,
  Injectable,
  NotFoundException,
} from '@nestjs/common';
import { SvcFinanceSqliteRepository } from './svc-finance-sqlite.repository';

@Injectable()
export class SvcFinanceService {
  constructor(private readonly sqlite: SvcFinanceSqliteRepository) {}

  summary(lifecycleId: number) {
    if (!this.sqlite.lifecycleExists(lifecycleId)) {
      throw new NotFoundException({ error: 'Không tìm thấy lifecycle' });
    }
    const contractAmount = this.sqlite.contractAmountVnd(lifecycleId);
    return this.sqlite.getSummary(lifecycleId, contractAmount);
  }

  createPayment(body: Record<string, unknown>) {
    const lifecycleId = Number(body.lifecycle_id);
    const amountVnd = Number(body.amount_vnd);
    const receivedOn = String(body.received_on ?? '').trim();
    if (!Number.isFinite(lifecycleId) || lifecycleId <= 0) {
      throw new BadRequestException({ error: 'Cần lifecycle_id hợp lệ' });
    }
    if (!Number.isFinite(amountVnd) || amountVnd < 0) {
      throw new BadRequestException({ error: 'Cần amount_vnd hợp lệ' });
    }
    if (!receivedOn) {
      throw new BadRequestException({ error: 'Cần received_on' });
    }
    if (!this.sqlite.lifecycleExists(lifecycleId)) {
      throw new NotFoundException({ error: 'Không tìm thấy lifecycle' });
    }
    return this.sqlite.createPayment(body);
  }

  patchPayment(paymentId: number, body: Record<string, unknown>) {
    const updated = this.sqlite.patchPayment(paymentId, body);
    if (!updated) {
      throw new NotFoundException({ error: 'Không tìm thấy payment' });
    }
    return updated;
  }

  deletePayment(paymentId: number) {
    const ok = this.sqlite.deletePayment(paymentId);
    if (!ok) {
      throw new NotFoundException({ error: 'Không tìm thấy payment' });
    }
    return { ok: true };
  }
}
