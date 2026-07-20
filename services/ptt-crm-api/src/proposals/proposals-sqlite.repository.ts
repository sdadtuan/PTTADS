import { Injectable, OnModuleDestroy } from '@nestjs/common';
import { DatabaseSync } from 'node:sqlite';
import { catalogTs } from '../catalog/catalog-slug.util';
import { AppConfigService } from '../config/app-config.service';
import { CreateProposalBody, ProposalRow } from './proposals.types';

@Injectable()
export class ProposalsSqliteRepository implements OnModuleDestroy {
  private db: DatabaseSync | null = null;

  constructor(private readonly config: AppConfigService) {}

  private get database(): DatabaseSync {
    if (!this.db) {
      this.db = new DatabaseSync(this.config.sqlitePath);
      this.db.exec('PRAGMA foreign_keys = ON');
      this.ensureSchema();
    }
    return this.db;
  }

  onModuleDestroy(): void {
    if (this.db) {
      this.db.close();
      this.db = null;
    }
  }

  private ensureSchema(): void {
    this.database.exec(`
      CREATE TABLE IF NOT EXISTS crm_proposals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_id INTEGER NOT NULL REFERENCES crm_customers(id) ON DELETE CASCADE,
        lifecycle_id INTEGER REFERENCES crm_service_lifecycle(id) ON DELETE SET NULL,
        service_slugs TEXT NOT NULL DEFAULT '[]',
        total_vnd INTEGER NOT NULL DEFAULT 0,
        timeline_months INTEGER NOT NULL DEFAULT 1,
        notes TEXT NOT NULL DEFAULT '',
        ai_output TEXT NOT NULL DEFAULT '{}',
        created_at TEXT NOT NULL DEFAULT '',
        updated_at TEXT NOT NULL DEFAULT ''
      );
      CREATE INDEX IF NOT EXISTS idx_crm_proposals_customer ON crm_proposals (customer_id);
    `);
  }

  listByCustomer(customerId: number): ProposalRow[] {
    const rows = this.database
      .prepare('SELECT * FROM crm_proposals WHERE customer_id = ? ORDER BY id DESC')
      .all(customerId) as unknown as Array<Record<string, unknown>>;
    return rows.map((r) => this.mapProposalRow(r, false));
  }

  getById(proposalId: number): ProposalRow | null {
    const row = this.database
      .prepare('SELECT * FROM crm_proposals WHERE id = ?')
      .get(proposalId) as unknown as Record<string, unknown> | undefined;
    return row ? this.mapProposalRow(row, true) : null;
  }

  create(body: CreateProposalBody): { id: number } {
    const slugs = (body.service_slugs ?? []).map((s) => String(s).trim()).filter(Boolean);
    const ts = catalogTs();
    const result = this.database
      .prepare(
        `INSERT INTO crm_proposals (
           customer_id, lifecycle_id, service_slugs, total_vnd, timeline_months,
           notes, ai_output, created_at, updated_at
         ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`,
      )
      .run(
        Number(body.customer_id),
        body.lifecycle_id != null ? Number(body.lifecycle_id) : null,
        JSON.stringify(slugs),
        Math.max(0, Number(body.total_vnd ?? 0)),
        Math.max(1, Number(body.timeline_months ?? 1)),
        String(body.notes ?? '').slice(0, 2000),
        '{}',
        ts,
        ts,
      );
    return { id: Number(result.lastInsertRowid) };
  }

  delete(proposalId: number): boolean {
    const result = this.database
      .prepare('DELETE FROM crm_proposals WHERE id = ?')
      .run(proposalId);
    return Number(result.changes) > 0;
  }

  private mapProposalRow(row: Record<string, unknown>, parseAi: boolean): ProposalRow {
    let serviceSlugs: string[] = [];
    try {
      serviceSlugs = JSON.parse(String(row.service_slugs ?? '[]'));
    } catch {
      serviceSlugs = [];
    }
    let aiOutput: Record<string, unknown> = {};
    const rawAi = String(row.ai_output ?? '{}');
    if (parseAi) {
      try {
        aiOutput = JSON.parse(rawAi) as Record<string, unknown>;
      } catch {
        aiOutput = {};
      }
    } else {
      try {
        const parsed = JSON.parse(rawAi) as Record<string, unknown>;
        aiOutput = parsed;
      } catch {
        aiOutput = {};
      }
    }
    const generated = Object.values(aiOutput).some((v) => Boolean(v));
    return {
      id: Number(row.id),
      customer_id: Number(row.customer_id),
      lifecycle_id: row.lifecycle_id != null ? Number(row.lifecycle_id) : null,
      service_slugs: serviceSlugs,
      total_vnd: Number(row.total_vnd ?? 0),
      timeline_months: Number(row.timeline_months ?? 1),
      notes: String(row.notes ?? ''),
      ai_output: parseAi ? aiOutput : aiOutput,
      generated,
      created_at: String(row.created_at ?? ''),
      updated_at: String(row.updated_at ?? ''),
    };
  }
}
