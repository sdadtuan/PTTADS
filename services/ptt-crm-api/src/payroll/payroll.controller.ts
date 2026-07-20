import {
  Body,
  Controller,
  Get,
  HttpCode,
  HttpStatus,
  Param,
  ParseIntPipe,
  Patch,
  Post,
  Put,
  Query,
  UseGuards,
} from '@nestjs/common';
import { StaffOrInternalKeyGuard } from '../staff-auth/staff-or-internal-key.guard';
import {
  StaffPayrollSalaryEditGuard,
  StaffPayrollSalaryExportGuard,
  StaffPayrollSalaryViewGuard,
  StaffPayrollViewGuard,
} from './guards/staff-payroll.guard';
import { PayrollService } from './payroll.service';

@Controller('api/crm/payroll')
@UseGuards(StaffOrInternalKeyGuard)
export class PayrollController {
  constructor(private readonly payroll: PayrollService) {}

  @Get('policy')
  @UseGuards(StaffPayrollSalaryViewGuard)
  getPolicy() {
    return this.payroll.getPolicy();
  }

  @Put('policy')
  @UseGuards(StaffPayrollSalaryEditGuard)
  putPolicy(@Body() body: Record<string, unknown>) {
    return this.payroll.updatePolicy(body);
  }

  @Get('position-rates')
  @UseGuards(StaffPayrollSalaryViewGuard)
  getPositionRates() {
    return this.payroll.getPositionRates();
  }

  @Put('position-rates')
  @UseGuards(StaffPayrollSalaryEditGuard)
  putPositionRates(@Body() body: Record<string, unknown>) {
    return this.payroll.updatePositionRates(body);
  }

  @Get('dashboard')
  @UseGuards(StaffPayrollViewGuard)
  dashboard(@Query('year') year?: string, @Query('month') month?: string) {
    return this.payroll.dashboard(year, month);
  }

  @Get('export')
  @UseGuards(StaffPayrollSalaryExportGuard)
  export(
    @Query('period') period?: string,
    @Query('year') year?: string,
    @Query('month') month?: string,
    @Query('quarter') quarter?: string,
    @Query('from') from?: string,
    @Query('to') to?: string,
    @Query('staff_id') staffId?: string,
    @Query('q') q?: string,
  ) {
    return this.payroll.exportPayroll({ period, year, month, quarter, from, to, staff_id: staffId, q });
  }

  @Get('attendance')
  @UseGuards(StaffPayrollViewGuard)
  attendance(
    @Query('staff_id') staffId?: string,
    @Query('from') from?: string,
    @Query('to') to?: string,
  ) {
    return this.payroll.listAttendance({ staff_id: staffId, from, to });
  }

  @Get()
  @UseGuards(StaffPayrollSalaryViewGuard)
  getPayroll(@Query('year') year?: string, @Query('month') month?: string) {
    return this.payroll.getPayroll(year, month);
  }

  @Post('compute')
  @HttpCode(HttpStatus.OK)
  @UseGuards(StaffPayrollSalaryEditGuard)
  compute(@Body() body: Record<string, unknown>) {
    return this.payroll.computePayroll(body);
  }

  @Patch('line/:lineId')
  @UseGuards(StaffPayrollSalaryEditGuard)
  patchLine(
    @Param('lineId', ParseIntPipe) lineId: number,
    @Body() body: Record<string, unknown>,
  ) {
    return this.payroll.patchPayrollLine(lineId, body);
  }

  @Patch(':payrollId')
  @UseGuards(StaffPayrollSalaryEditGuard)
  patchPayroll(
    @Param('payrollId', ParseIntPipe) payrollId: number,
    @Body() body: Record<string, unknown>,
  ) {
    return this.payroll.patchPayroll(payrollId, body);
  }
}
