import type { ServiceLifecycleSqliteRepository } from './service-lifecycle-sqlite.repository';

export interface LifecycleContextDto {
  lifecycle_id: number;
  lead_id: number | null;
  customer_id: number | null;
  contract_id: number | null;
  service_slug: string;
  stage: string;
  status: string;
  lead: {
    id: number | null;
    full_name: string;
    owner_id: number | null;
    owner_name: string;
  };
  presales: {
    id: number | null;
    assigned_sp: number | null;
    assigned_sp_name: string;
  };
  contract: {
    id: number | null;
    title: string;
    amount_vnd: number;
    agency_client_id: string;
    campaign_id: number | null;
  };
  campaign: {
    id: number | null;
    name: string;
    code: string;
  };
  links: {
    service_delivery: string;
    lead: string | null;
    agency_client: string | null;
    hub: string | null;
  };
}

export function buildLifecycleContext(
  repo: ServiceLifecycleSqliteRepository,
  lifecycleId: number,
): LifecycleContextDto | null {
  return repo.getLifecycleContext(lifecycleId);
}
