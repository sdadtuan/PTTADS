'use client';

import { useState } from 'react';
import {
  EmailDnsStatus,
  EmailWarmupMeter,
} from '@/components/email';
import type { EmailDeliverabilityDomainRow } from '@/lib/api';

const DNS_HINTS = [
  { type: 'TXT', host: '@', value: 'v=spf1 include:sendgrid.net ~all', label: 'SPF' },
  { type: 'CNAME', host: 's1._domainkey', value: 's1.domainkey.uXXXX.wl.sendgrid.net', label: 'DKIM 1' },
  { type: 'CNAME', host: 's2._domainkey', value: 's2.domainkey.uXXXX.wl.sendgrid.net', label: 'DKIM 2' },
  { type: 'TXT', host: '_dmarc', value: 'v=DMARC1; p=none; rua=mailto:dmarc@yourdomain.com', label: 'DMARC' },
];

export function EmailDomainOnboardingWizard({
  clientId,
  canWrite,
  onRegister,
  onVerify,
  domains,
}: {
  clientId: string;
  canWrite: boolean;
  domains: EmailDeliverabilityDomainRow[];
  onRegister: (domain: string) => Promise<void>;
  onVerify: (domainId: string) => Promise<void>;
}) {
  const [step, setStep] = useState<1 | 2 | 3>(1);
  const [domain, setDomain] = useState('');
  const [busy, setBusy] = useState(false);
  const latest = domains.find((d) => d.domain === domain) ?? domains[0] ?? null;

  async function handleRegister() {
    if (!domain.trim()) return;
    setBusy(true);
    try {
      await onRegister(domain.trim().toLowerCase());
      setStep(2);
    } finally {
      setBusy(false);
    }
  }

  async function handleVerify() {
    if (!latest) return;
    setBusy(true);
    try {
      await onVerify(latest.id);
      setStep(3);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="card" style={{ marginBottom: '1rem' }}>
      <h3 style={{ marginTop: 0 }}>Domain onboarding wizard (E-11)</h3>
      <p className="muted" style={{ marginTop: 0 }}>
        Bước {step}/3 — Client {clientId.slice(0, 8)}…
      </p>
      <nav className="email-builder-tabs" aria-label="Domain wizard steps">
        <button type="button" className={step === 1 ? 'active' : undefined} onClick={() => setStep(1)}>
          1. Domain
        </button>
        <button type="button" className={step === 2 ? 'active' : undefined} onClick={() => setStep(2)} disabled={!domain}>
          2. DNS records
        </button>
        <button type="button" className={step === 3 ? 'active' : undefined} onClick={() => setStep(3)} disabled={!latest}>
          3. Verify &amp; warm-up
        </button>
      </nav>

      {step === 1 ? (
        <div style={{ marginTop: '1rem' }}>
          <label>
            Sending domain
            <input
              value={domain}
              onChange={(e) => setDomain(e.target.value)}
              placeholder="mail.clientdomain.com"
              disabled={!canWrite}
              style={{ display: 'block', width: '100%', maxWidth: 420, marginTop: '0.25rem' }}
            />
          </label>
          {canWrite ? (
            <button type="button" className="btn btn-sm" style={{ marginTop: '0.75rem' }} disabled={busy || !domain.trim()} onClick={() => void handleRegister()}>
              {busy ? '…' : 'Tiếp tục → DNS'}
            </button>
          ) : null}
        </div>
      ) : null}

      {step === 2 ? (
        <div style={{ marginTop: '1rem' }}>
          <p className="muted">Thêm các bản ghi sau tại DNS provider của client (SendGrid template):</p>
          <table className="perf-table">
            <thead>
              <tr>
                <th>Loại</th>
                <th>Host</th>
                <th>Value</th>
              </tr>
            </thead>
            <tbody>
              {DNS_HINTS.map((row) => (
                <tr key={row.label}>
                  <td>{row.type}</td>
                  <td>
                    <code>{row.host}.{domain || 'example.com'}</code>
                  </td>
                  <td>
                    <code style={{ fontSize: '0.8rem' }}>{row.value}</code>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {canWrite ? (
            <button type="button" className="btn btn-sm" style={{ marginTop: '0.75rem' }} onClick={() => setStep(3)}>
              Đã cấu hình DNS → Verify
            </button>
          ) : null}
        </div>
      ) : null}

      {step === 3 && latest ? (
        <div style={{ marginTop: '1rem' }}>
          <p>
            <strong>{latest.domain}</strong> — {latest.status}
          </p>
          <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', marginTop: '0.5rem' }}>
            <EmailDnsStatus status={latest.spf_status} label="SPF" />
            <EmailDnsStatus status={latest.dkim_status} label="DKIM" />
            <EmailDnsStatus status={latest.dmarc_status} label="DMARC" />
          </div>
          <div style={{ marginTop: '0.75rem' }}>
            <EmailWarmupMeter stage={latest.warm_up_stage} />
          </div>
          {canWrite ? (
            <button type="button" className="btn btn-sm" style={{ marginTop: '0.75rem' }} disabled={busy} onClick={() => void handleVerify()}>
              {busy ? '…' : 'Verify DNS now'}
            </button>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
