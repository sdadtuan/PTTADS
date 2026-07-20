export interface StaffSectionCap {
  section: string;
  action: string;
}

export interface StaffUserProfile {
  id: string;
  email: string;
  display_name: string;
  position_id: number;
}

export interface StaffLoginResult {
  access_token: string;
  refresh_token: string;
  token_type: 'Bearer';
  expires_in: number;
  refresh_expires_in: number;
  user: StaffUserProfile;
}

export interface StaffMeResponse extends StaffUserProfile {
  caps: StaffSectionCap[];
}
