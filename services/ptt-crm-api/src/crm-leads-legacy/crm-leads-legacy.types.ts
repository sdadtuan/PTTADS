export interface LeadActivityRow {
  id: number;
  lead_id: number;
  user_id: number | null;
  user_name: string;
  activity_type: string;
  activity_type_label: string;
  content: string;
  result: string;
  next_action: string;
  next_action_at: string;
  created_at: string;
  created_by: string;
}

export interface LeadStatusLogRow {
  id: number;
  lead_id: number;
  old_status: string;
  new_status: string;
  changed_by: string;
  note: string;
  created_at: string;
}

export interface LeadAssignmentLogRow {
  id: number;
  lead_id: number;
  from_user_id: number | null;
  from_name: string;
  to_user_id: number | null;
  to_name: string;
  reason: string;
  created_by: string;
  created_at: string;
}

export interface CreateLeadActivityBody {
  activity_type?: string;
  content?: string;
  result?: string;
  next_action?: string;
  next_action_at?: string;
}

export interface AssignLeadBody {
  to_user_id?: number;
  owner_id?: number;
  reason: string;
}

export const ACTIVITY_TYPES = [
  'call',
  'email',
  'message',
  'meeting',
  'note',
  'proposal',
  'task',
  'reminder',
  'system',
] as const;

export const ACTIVITY_TYPE_LABELS: Record<string, string> = {
  call: 'Gọi điện',
  email: 'Email',
  message: 'Tin nhắn',
  meeting: 'Họp',
  note: 'Ghi chú',
  proposal: 'Báo giá',
  task: 'Công việc',
  reminder: 'Nhắc việc',
  system: 'Hệ thống',
};
