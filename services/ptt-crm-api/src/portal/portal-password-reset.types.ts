export interface PortalForgotPasswordResponse {
  ok: true;
  message: string;
  /** Dev/staging only when email webhook disabled — never in production. */
  reset_url?: string;
}

export interface PortalValidateResetTokenResponse {
  ok: boolean;
  email_masked?: string;
  error?: string;
}

export interface PortalResetPasswordResponse {
  ok: boolean;
  message?: string;
}

export interface PortalChangePasswordResponse {
  ok: boolean;
  message?: string;
}

export interface PortalPasswordResetUserRow {
  id: string;
  client_id: string;
  email: string;
  password_hash: string;
}
