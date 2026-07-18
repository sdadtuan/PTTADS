import { Injectable, NestMiddleware } from '@nestjs/common';
import type { NextFunction, Request, Response } from 'express';
import { randomUUID } from 'crypto';

export const CORRELATION_ID_HEADER = 'x-correlation-id';

@Injectable()
export class CorrelationMiddleware implements NestMiddleware {
  use(req: Request, res: Response, next: NextFunction): void {
    const incoming =
      req.header('X-Correlation-Id') ??
      req.header('X-Request-Id') ??
      randomUUID();
    (req as Request & { correlationId?: string }).correlationId = incoming;
    res.setHeader('X-Correlation-Id', incoming);
    next();
  }
}

export function getRequestCorrelationId(req: Request): string | undefined {
  return (req as Request & { correlationId?: string }).correlationId;
}
