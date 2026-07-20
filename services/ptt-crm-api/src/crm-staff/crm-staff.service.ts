import {
  BadRequestException,
  Injectable,
  NotFoundException,
} from '@nestjs/common';
import { KpiService } from '../kpi/kpi.service';
import { CrmStaffSqliteRepository } from './crm-staff-sqlite.repository';
import {
  isValidEmail,
  PatchCrmStaffBody,
  StaffCompetencyPutBody,
  StaffImportBody,
  StaffLevelsPutBody,
} from './crm-staff.types';

@Injectable()
export class CrmStaffService {
  constructor(
    private readonly sqlite: CrmStaffSqliteRepository,
    private readonly kpi: KpiService,
  ) {}

  listStaff() {
    return this.sqlite.listStaff(500);
  }

  detail(staffId: number) {
    const staff = this.sqlite.getStaffById(staffId);
    if (!staff) {
      throw new NotFoundException({ error: 'Không tìm thấy nhân viên' });
    }
    return staff;
  }

  workspace(staffId: number) {
    const bundle = this.sqlite.getWorkspace(staffId);
    if (!bundle) {
      throw new NotFoundException({ error: 'Không tìm thấy nhân viên' });
    }
    return bundle;
  }

  patch(staffId: number, body: PatchCrmStaffBody) {
    if ('name' in body && body.name != null) {
      const nm = String(body.name).trim();
      if (!nm) {
        throw new BadRequestException({ error: 'Tên không được trống' });
      }
    }
    if ('email' in body && body.email != null) {
      const em = String(body.email).trim();
      if (em && !isValidEmail(em)) {
        throw new BadRequestException({ error: 'Email không hợp lệ' });
      }
    }
    const updated = this.sqlite.patchStaff(staffId, body);
    if (!updated) {
      throw new NotFoundException({ error: 'Không tìm thấy nhân viên' });
    }
    return updated;
  }

  listStaffKpi(year?: string, month?: string, staffId?: string) {
    return this.kpi.listStaffKpi(year, month, staffId);
  }

  getLevels() {
    return this.sqlite.getStaffLevels();
  }

  saveLevels(body: StaffLevelsPutBody) {
    if (!Array.isArray(body.staff_levels)) {
      throw new BadRequestException({ error: 'staff_levels phải là mảng' });
    }
    try {
      return this.sqlite.saveStaffLevels(body.staff_levels);
    } catch (err) {
      if (err instanceof Error && err.message === 'INVALID_LEVELS') {
        throw new BadRequestException({ error: 'staff_levels không hợp lệ' });
      }
      throw err;
    }
  }

  getCompetency() {
    return this.sqlite.getCompetencyConfig();
  }

  saveCompetency(body: StaffCompetencyPutBody) {
    const competency = body.competency ?? (body as unknown as Record<string, unknown>);
    if (!competency || typeof competency !== 'object') {
      throw new BadRequestException({ error: 'competency không hợp lệ' });
    }
    return this.sqlite.saveCompetencyConfig(competency as Record<string, unknown>);
  }

  importStaff(body: StaffImportBody) {
    const rows = Array.isArray(body.rows) ? body.rows : [];
    if (!rows.length) {
      throw new BadRequestException({ error: 'Thiếu rows' });
    }
    return this.sqlite.importStaffRows(rows);
  }
}
