import { Injectable, OnModuleDestroy } from '@nestjs/common';
import { DatabaseSync } from 'node:sqlite';
import { AppConfigService } from '../config/app-config.service';
import { buildOwnerWeeklyExportSheets, ownerWeeklyExportFilename } from './owner-weekly-export.util';
import {
  deleteCashSnapshot,
  getOwnerWeeklyDashboard,
  getOwnerWeeklyInboxSummary,
  getOwnerWeeklyTargets,
  listCashSnapshots,
  OWNER_WEEKLY_ENV_KEYS,
  OWNER_WEEKLY_TARGET_DEFAULTS,
  OWNER_WEEKLY_TARGET_GROUPS,
  OWNER_WEEKLY_TARGET_LABELS,
  resolveWeekBounds,
  setOwnerWeeklyTargets,
  syncOwnerWeeklyInboxStub,
  upsertCashSnapshot,
} from './owner-weekly.util';

@Injectable()
export class OwnerWeeklySqliteRepository implements OnModuleDestroy {
  private db: DatabaseSync | null = null;

  constructor(private readonly config: AppConfigService) {}

  private get database(): DatabaseSync {
    if (!this.db) {
      this.db = new DatabaseSync(this.config.sqlitePath);
      this.db.exec('PRAGMA foreign_keys = ON');
    }
    return this.db;
  }

  onModuleDestroy(): void {
    if (this.db) {
      this.db.close();
      this.db = null;
    }
  }

  dashboard(opts: {
    weekEnd?: string | null;
    year?: number | null;
    isoWeek?: number | null;
    trendWeeks?: number;
  }): Record<string, unknown> {
    return getOwnerWeeklyDashboard(this.database, opts);
  }

  configGet(): Record<string, unknown> {
    return {
      targets: getOwnerWeeklyTargets(this.database),
      defaults: OWNER_WEEKLY_TARGET_DEFAULTS,
      labels: OWNER_WEEKLY_TARGET_LABELS,
      env_keys: OWNER_WEEKLY_ENV_KEYS,
      target_groups: OWNER_WEEKLY_TARGET_GROUPS,
    };
  }

  configPatch(updates: Record<string, unknown>): Record<string, unknown> {
    return { ok: true, targets: setOwnerWeeklyTargets(this.database, updates) };
  }

  listCashSnapshots(limit: number): Record<string, unknown> {
    return { snapshots: listCashSnapshots(this.database, limit) };
  }

  upsertCashSnapshot(
    snapshotOn: string,
    balanceVnd: number,
    source: string,
    notes: string,
  ): Record<string, unknown> {
    const row = upsertCashSnapshot(this.database, snapshotOn, balanceVnd, source, notes);
    return { ok: true, snapshot: row };
  }

  deleteCashSnapshot(snapshotOn: string): Record<string, unknown> {
    const deleted = deleteCashSnapshot(this.database, snapshotOn);
    return { ok: true, deleted };
  }

  export(opts: {
    weekEnd?: string | null;
    year?: number | null;
    isoWeek?: number | null;
  }): Record<string, unknown> {
    const dashboard = getOwnerWeeklyDashboard(this.database, opts);
    const sheets = buildOwnerWeeklyExportSheets(dashboard);
    return {
      filename: ownerWeeklyExportFilename(dashboard),
      format: 'json',
      sheets,
    };
  }

  alertCron(isoYear?: number | null, isoWeek?: number | null): Record<string, unknown> {
    const y =
      isoYear != null && isoWeek != null ? isoYear : resolveWeekBounds({}).isoYear;
    const w =
      isoYear != null && isoWeek != null ? isoWeek : resolveWeekBounds({}).isoWeek;
    const dashboard = getOwnerWeeklyDashboard(this.database, { year: y, isoWeek: w });
    const brief = dashboard.pre_execution as Record<string, unknown>;
    return {
      ok: true,
      stub: true,
      iso_year: y,
      iso_week: w,
      red_count: brief.red_count ?? 0,
      yellow_count: brief.yellow_count ?? 0,
    };
  }

  inboxSync(isoYear?: number | null, isoWeek?: number | null): Record<string, unknown> {
    const y =
      isoYear != null && isoWeek != null ? isoYear : resolveWeekBounds({}).isoYear;
    const w =
      isoYear != null && isoWeek != null ? isoWeek : resolveWeekBounds({}).isoWeek;
    const dashboard = getOwnerWeeklyDashboard(this.database, { year: y, isoWeek: w });
    return { ok: true, inbox: syncOwnerWeeklyInboxStub(this.database, y, w, dashboard) };
  }

  inboxSummary(): Record<string, unknown> {
    return getOwnerWeeklyInboxSummary(this.database);
  }
}
