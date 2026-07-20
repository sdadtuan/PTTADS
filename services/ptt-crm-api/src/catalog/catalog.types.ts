export interface CatalogServiceRow {
  id: number;
  slug: string;
  name: string;
  description: string;
  sort_order: number;
  active: boolean;
  created_at: string;
  updated_at: string;
}

export interface CatalogIndustryRow {
  id: number;
  slug: string;
  name: string;
  description: string;
  traits: Record<string, unknown>;
  sort_order: number;
  active: boolean;
  created_at: string;
  updated_at: string;
}

export interface AssignScopeRow {
  id: number;
  staff_id: number;
  industry_slug: string;
  service_slug: string;
  active: boolean;
  created_at: string;
  updated_at: string;
  staff_name: string;
}

export interface StaffOption {
  id: number;
  name: string;
  internal_code: string;
}

export interface CatalogPublicPayload {
  services: CatalogServiceRow[];
  industries: CatalogIndustryRow[];
  service_slugs: string[];
  service_labels: Record<string, string>;
  industry_slugs: string[];
  industry_labels: Record<string, string>;
}

export interface CreateCatalogServiceBody {
  slug: string;
  name: string;
  description?: string;
  sort_order?: number;
  active?: boolean;
}

export interface PatchCatalogServiceBody {
  name?: string;
  description?: string;
  sort_order?: number;
  active?: boolean;
}

export interface CreateCatalogIndustryBody {
  slug: string;
  name: string;
  description?: string;
  sort_order?: number;
  active?: boolean;
}

export interface PatchCatalogIndustryBody {
  name?: string;
  description?: string;
  sort_order?: number;
  active?: boolean;
  traits?: Record<string, unknown>;
}

export interface CreateAssignScopeBody {
  staff_id: number;
  industry_slug?: string;
  service_slug?: string;
  active?: boolean;
}

export interface PatchAssignScopeBody {
  active?: boolean;
}
