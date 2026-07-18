import { NestFactory } from '@nestjs/core';
import { AppModule } from './app.module';
import { AppConfigService } from './config/app-config.service';
import { initSentry } from './observability/sentry.init';

async function bootstrap(): Promise<void> {
  initSentry('ptt-crm-api');
  const app = await NestFactory.create(AppModule, { logger: ['log', 'warn', 'error'] });
  const config = app.get(AppConfigService);
  const origins = config.portalCorsOrigins;
  if (origins.length > 0) {
    app.enableCors({
      origin: origins,
      credentials: true,
      methods: ['GET', 'POST', 'PATCH', 'OPTIONS'],
      allowedHeaders: [
        'Content-Type',
        'Authorization',
        'X-PTT-Internal-Key',
        'X-PTT-Actor',
        'X-Correlation-Id',
        'X-Request-Id',
      ],
    });
  }
  await app.listen(config.port, '0.0.0.0');
}

void bootstrap();
