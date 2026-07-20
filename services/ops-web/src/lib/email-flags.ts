/** Client-side feature flags for Email Marketing UX (Wave 3). */

export function emailModuleEnabled(): boolean {
  return process.env.NEXT_PUBLIC_PTT_EMAIL_ENABLED !== '0';
}

export function emailSendEnabled(): boolean {
  return emailModuleEnabled() && process.env.NEXT_PUBLIC_PTT_EMAIL_SEND_ENABLED !== '0';
}

export function emailJourneysEnabled(): boolean {
  return emailModuleEnabled() && process.env.NEXT_PUBLIC_PTT_EMAIL_JOURNEYS_ENABLED !== '0';
}
