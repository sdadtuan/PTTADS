import {
  BadRequestException,
  Injectable,
  NotFoundException,
} from '@nestjs/common';
import { ServiceLifecycleSqliteRepository } from './service-lifecycle-sqlite.repository';
import {
  CreateServiceLifecycleBody,
  isValidSlug,
  isValidStage,
  PatchServiceLifecycleBody,
} from './service-lifecycle.types';

@Injectable()
export class ServiceLifecycleService {
  constructor(private readonly sqlite: ServiceLifecycleSqliteRepository) {}

  list(serviceSlug?: string, amId?: string, includeDraft?: string) {
    const am = amId ? Number(amId) : undefined;
    const lifecycles = this.sqlite.listLifecycles({
      serviceSlug: serviceSlug || undefined,
      amId: am && Number.isFinite(am) && am > 0 ? am : undefined,
      includeDraft: includeDraft === '1',
    });
    return { lifecycles };
  }

  detail(id: number) {
    const lifecycle = this.sqlite.getLifecycleById(id);
    if (!lifecycle) {
      throw new NotFoundException({ error: 'Không tìm thấy lifecycle' });
    }
    const events = this.sqlite.listEvents(id);
    return { ...lifecycle, events };
  }

  create(body: CreateServiceLifecycleBody) {
    const serviceSlug = String(body.service_slug ?? '').trim();
    if (!serviceSlug) {
      throw new BadRequestException({ error: 'Cần service_slug' });
    }
    if (!isValidSlug(serviceSlug)) {
      throw new BadRequestException({ error: 'service_slug không hợp lệ' });
    }
    return this.sqlite.createDraft(body);
  }

  patch(id: number, body: PatchServiceLifecycleBody) {
    if ('stage' in body && body.stage != null) {
      const stage = String(body.stage).trim();
      if (!isValidStage(stage)) {
        throw new BadRequestException({ error: `Stage không hợp lệ: ${stage}` });
      }
    }
    if ('service_slug' in body && body.service_slug != null) {
      const slug = String(body.service_slug).trim();
      if (slug && !isValidSlug(slug)) {
        throw new BadRequestException({ error: 'service_slug không hợp lệ' });
      }
    }
    const updated = this.sqlite.patchLifecycle(id, body);
    if (!updated) {
      throw new NotFoundException({ error: 'Không tìm thấy lifecycle' });
    }
    return updated;
  }

  listTasks(id: number) {
    const lifecycle = this.sqlite.getLifecycleById(id);
    if (!lifecycle) {
      throw new NotFoundException({ error: 'Không tìm thấy lifecycle' });
    }
    return { tasks: [] };
  }
}
