import { BadRequestException, Injectable, NotFoundException } from '@nestjs/common';
import { computeProductInventoryStats } from './re-projects-inventory.util';
import { ReProjectsSqliteRepository } from './re-projects-sqlite.repository';
import {
  CreateReProjectBody,
  SavePriceListBody,
  SaveProductBody,
  SaveProjectTypeBody,
} from './re-projects.types';

@Injectable()
export class ReProjectsService {
  constructor(private readonly sqlite: ReProjectsSqliteRepository) {}

  listTypes(includeInactive = false) {
    const types = this.sqlite.listProjectTypes(includeInactive);
    const labels: Record<string, string> = {};
    for (const t of types) labels[t.code] = t.name;
    return { types, labels };
  }

  createType(body: SaveProjectTypeBody) {
    try {
      return this.sqlite.saveProjectType(body);
    } catch (e) {
      throw new BadRequestException({ error: String((e as Error).message) });
    }
  }

  updateType(typeId: number, body: SaveProjectTypeBody) {
    try {
      return this.sqlite.saveProjectType(body, typeId);
    } catch (e) {
      throw new BadRequestException({ error: String((e as Error).message) });
    }
  }

  deleteType(typeId: number) {
    try {
      this.sqlite.deleteProjectType(typeId);
      return { ok: true };
    } catch (e) {
      throw new BadRequestException({ error: String((e as Error).message) });
    }
  }

  listProjects(q?: string) {
    return { projects: this.sqlite.listProjects(q) };
  }

  createProject(body: CreateReProjectBody) {
    try {
      return this.sqlite.createProject(body);
    } catch (e) {
      throw new BadRequestException({ error: String((e as Error).message) });
    }
  }

  getProject(id: number) {
    const proj = this.sqlite.fetchProject(id);
    if (!proj) throw new NotFoundException({ error: 'Không tìm thấy dự án.' });
    return proj;
  }

  updateProject(id: number, body: CreateReProjectBody) {
    try {
      return this.sqlite.updateProject(id, body);
    } catch (e) {
      const msg = String((e as Error).message);
      if (msg.includes('Không tìm thấy')) throw new NotFoundException({ error: msg });
      throw new BadRequestException({ error: msg });
    }
  }

  deleteProject(id: number) {
    this.sqlite.deleteProject(id);
    return { ok: true };
  }

  projectSummary(id: number) {
    try {
      return this.sqlite.fetchProjectSummary(id);
    } catch (e) {
      throw new NotFoundException({ error: String((e as Error).message) });
    }
  }

  listProducts(projectId: number) {
    const products = this.sqlite.listProducts(projectId);
    return { products, inventory: computeProductInventoryStats(products) };
  }

  createProduct(projectId: number, body: SaveProductBody) {
    try {
      return this.sqlite.saveProduct(projectId, body);
    } catch (e) {
      throw new BadRequestException({ error: String((e as Error).message) });
    }
  }

  updateProduct(projectId: number, productId: number, body: SaveProductBody) {
    return this.sqlite.saveProduct(projectId, body, productId);
  }

  deleteProduct(projectId: number, productId: number) {
    this.sqlite.deleteProduct(projectId, productId);
    return { ok: true };
  }

  listZones(projectId: number) {
    return { zones: this.sqlite.listProjectZones(projectId) };
  }

  inventoryByZone(projectId: number) {
    return { zones: this.sqlite.inventoryByZoneSummary(projectId) };
  }

  priceBatches(projectId: number) {
    return {
      batches: this.sqlite.listPriceBatches(projectId),
      summary: this.sqlite.inventoryByPriceBatchSummary(projectId),
    };
  }

  listPriceLists(projectId: number) {
    return {
      price_lists: this.sqlite.listPriceLists(projectId),
      version_codes: this.sqlite.listAllVersionCodes(projectId),
    };
  }

  createPriceList(projectId: number, body: SavePriceListBody, createdBy = '') {
    try {
      return this.sqlite.savePriceList(projectId, body, undefined, createdBy);
    } catch (e) {
      throw new BadRequestException({ error: String((e as Error).message) });
    }
  }

  getPriceList(projectId: number, listId: number) {
    const row = this.sqlite.fetchPriceList(projectId, listId);
    if (!row) throw new NotFoundException({ error: 'Không tìm thấy bảng giá.' });
    const { items, total } = this.sqlite.listPriceListItems(listId, 500);
    return { price_list: row, items, items_total: total };
  }

  updatePriceList(projectId: number, listId: number, body: SavePriceListBody, createdBy = '') {
    try {
      return this.sqlite.savePriceList(projectId, body, listId, createdBy);
    } catch (e) {
      throw new BadRequestException({ error: String((e as Error).message) });
    }
  }

  deletePriceList(projectId: number, listId: number) {
    try {
      this.sqlite.deletePriceList(projectId, listId);
      return { ok: true };
    } catch (e) {
      throw new BadRequestException({ error: String((e as Error).message) });
    }
  }
}
