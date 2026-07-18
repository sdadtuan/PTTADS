import { MiddlewareConsumer, Module, NestModule } from '@nestjs/common';
import { CorrelationMiddleware } from './correlation.middleware';
import { JsonAccessLogMiddleware } from './json-access-log.middleware';

@Module({})
export class ObservabilityModule implements NestModule {
  configure(consumer: MiddlewareConsumer): void {
    consumer.apply(CorrelationMiddleware, JsonAccessLogMiddleware).forRoutes('*');
  }
}
