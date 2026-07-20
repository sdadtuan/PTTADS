import { Module } from '@nestjs/common';
import { StaffAuthModule } from '../staff-auth/staff-auth.module';
import { CustomersController } from './customers.controller';
import { CustomersService } from './customers.service';
import { CustomersSqliteRepository } from './customers-sqlite.repository';
import { StaffCustomersViewGuard, StaffCustomersWriteGuard } from './guards/staff-customers.guard';

@Module({
  imports: [StaffAuthModule],
  controllers: [CustomersController],
  providers: [
    CustomersService,
    CustomersSqliteRepository,
    StaffCustomersViewGuard,
    StaffCustomersWriteGuard,
  ],
  exports: [CustomersService],
})
export class CustomersModule {}
