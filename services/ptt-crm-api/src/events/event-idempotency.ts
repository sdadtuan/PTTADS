export function leadAssignedIdempotencyKey(
  leadId: number | string,
  ownerId: number | string,
): string {
  return `lead:${leadId}:assigned:${ownerId}`;
}

export function leadCreatedIdempotencyKey(leadId: number | string): string {
  return `lead:${leadId}:created`;
}

export function creativeApprovedIdempotencyKey(
  creativeId: string,
  version: number | string,
): string {
  return `creative:${creativeId}:approved:v${version}`;
}

export function creativeRejectedIdempotencyKey(
  creativeId: string,
  version: number | string,
): string {
  return `creative:${creativeId}:rejected:v${version}`;
}

export function clientOffboardedIdempotencyKey(clientId: string): string {
  return `client:${clientId}:offboarded`;
}

function isIdempotencyScalar(value: unknown): value is string | number {
  return typeof value === 'string' || typeof value === 'number';
}

export function buildEventIdempotencyKey(
  eventType: string,
  payload: Record<string, unknown>,
): string | null {
  if (eventType === 'LeadAssigned') {
    const leadId = payload.lead_id;
    const ownerId = payload.owner_id;
    if (isIdempotencyScalar(leadId) && isIdempotencyScalar(ownerId)) {
      return leadAssignedIdempotencyKey(leadId, ownerId);
    }
  }
  if (eventType === 'LeadCreated') {
    const leadId = payload.lead_id;
    if (isIdempotencyScalar(leadId)) {
      return leadCreatedIdempotencyKey(leadId);
    }
  }
  if (eventType === 'CreativeApproved') {
    const creativeId = payload.creative_id;
    const version = payload.version;
    if (typeof creativeId === 'string' && isIdempotencyScalar(version)) {
      return creativeApprovedIdempotencyKey(creativeId, version);
    }
  }
  if (eventType === 'CreativeRejected') {
    const creativeId = payload.creative_id;
    const version = payload.version;
    if (typeof creativeId === 'string' && isIdempotencyScalar(version)) {
      return creativeRejectedIdempotencyKey(creativeId, version);
    }
  }
  if (eventType === 'ClientOffboarded') {
    const clientId = payload.client_id;
    if (typeof clientId === 'string' && clientId.trim()) {
      return clientOffboardedIdempotencyKey(clientId.trim());
    }
  }
  return null;
}
