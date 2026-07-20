/** CRM email revenue attribution SQL (Wave 2 — mirrors ptt_email/attribution.py). */

export const EMAIL_LEAD_FILTER_SQL = `
  (
    LOWER(COALESCE(cl.meta_json->>'utm_medium', '')) = 'email'
    OR COALESCE(cl.meta_json->>'email_send_id', '') <> ''
    OR COALESCE(cl.meta_json->>'utm_source', '') ILIKE '%email%'
    OR LOWER(COALESCE(cl.channel, '')) LIKE '%email%'
    OR LOWER(COALESCE(cl.source, '')) LIKE '%email%'
  )
`;

export function revenueAttributedQuery(clientParamIndex?: number): { sql: string; extraValues: unknown[] } {
  const clientClause = clientParamIndex
    ? ` AND cl.agency_client_id = $${clientParamIndex}::uuid`
    : '';
  return {
    sql: `
      SELECT COALESCE(SUM(
        NULLIF(regexp_replace(COALESCE(cl.meta_json->>'deal_value_vnd', '0'), '[^0-9.-]', '', 'g'), '')::numeric
      ), 0) AS total
      FROM crm_leads cl
      WHERE cl.is_duplicate IS NOT TRUE
        AND LOWER(COALESCE(cl.status, '')) IN ('won', 'closed_won', 'closed won')
        AND COALESCE(cl.created_at, cl.received_at) >= NOW() - ($1::int || ' days')::interval
        AND ${EMAIL_LEAD_FILTER_SQL}
        ${clientClause}
    `,
    extraValues: [],
  };
}
