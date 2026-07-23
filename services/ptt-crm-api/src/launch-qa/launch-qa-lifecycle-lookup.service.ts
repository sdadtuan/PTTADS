import { Injectable } from '@nestjs/common';
import { ServiceLifecycleSqliteRepository } from '../service-lifecycle/service-lifecycle-sqlite.repository';

@Injectable()
export class LaunchQaLifecycleLookupService {
  constructor(private readonly lifecycleSqlite: ServiceLifecycleSqliteRepository) {}

  buildLifecycleIndex(): Map<string, number> {
    return this.lifecycleSqlite.buildLaunchQaLifecycleIndex();
  }

  resolveLifecycleId(
    index: Map<string, number>,
    clientId: string,
    externalCampaignId: string,
  ): number | null {
    const key = `${clientId.trim()}:${externalCampaignId.trim()}`;
    const id = index.get(key);
    return id && id > 0 ? id : null;
  }
}
