export const SEO_GOV_SCHEMA = 'seo_aeo';

export const DEFAULT_POLICIES = [
  {
    policy_key: 'metadata_required',
    name: 'Metadata bắt buộc',
    description: 'Title, keyword/topic, meta title & description trong brief',
    rule_type: 'required_fields',
    rule_config: { fields: ['title', 'target_keyword', 'meta_title', 'meta_description'] },
    severity: 'block',
  },
  {
    policy_key: 'qa_complete',
    name: 'QA stages hoàn tất',
    description: 'SEO, AEO, Technical review đã approved',
    rule_type: 'approval_complete',
    rule_config: { stages: ['seo_review', 'aeo_review', 'technical_review'] },
    severity: 'block',
  },
  {
    policy_key: 'no_critical_technical',
    name: 'Không issue critical mở',
    description: 'Zero critical technical issues cho client',
    rule_type: 'technical_critical',
    rule_config: { max_open: 0 },
    severity: 'block',
  },
  {
    policy_key: 'schema_valid',
    name: 'Schema checklist',
    description: 'Brief checklist có mục schema',
    rule_type: 'schema_valid',
    rule_config: { require_schema_checklist: true },
    severity: 'block',
  },
] as const;

export function governanceEnabled(): boolean {
  const flag = (process.env.PTT_SEO_GOVERNANCE_ENABLED ?? '1').trim().toLowerCase();
  return !['0', 'false', 'no', 'off'].includes(flag);
}
