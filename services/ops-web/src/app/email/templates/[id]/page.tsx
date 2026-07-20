'use client';

import Link from 'next/link';
import { useCallback, useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { OpsNav } from '@/components/OpsNav';
import { PreflightChecklist, TemplateBlockLibrary } from '@/components/email';
import {
  fetchEmailTemplate,
  patchEmailTemplate,
  preflightEmailTemplate,
  staffMe,
  staffRefresh,
  type EmailPreflightCheck,
  type EmailTemplateRow,
} from '@/lib/api';
import {
  clearSession,
  getAccessToken,
  getRefreshToken,
  hasCap,
  updateAccessToken,
  updateStoredUser,
  type StoredStaffUser,
} from '@/lib/auth';
import { useToast } from '@/lib/toast';

type EditorTab = 'blocks' | 'html' | 'text';

export default function EmailTemplateDetailPage() {
  const router = useRouter();
  const params = useParams();
  const templateId = String(params.id ?? '');
  const { push } = useToast();
  const [user, setUser] = useState<StoredStaffUser | null>(null);
  const [template, setTemplate] = useState<EmailTemplateRow | null>(null);
  const [name, setName] = useState('');
  const [subject, setSubject] = useState('');
  const [htmlBody, setHtmlBody] = useState('');
  const [textBody, setTextBody] = useState('');
  const [editorTab, setEditorTab] = useState<EditorTab>('blocks');
  const [checks, setChecks] = useState<EmailPreflightCheck[]>([]);
  const [preflightPassed, setPreflightPassed] = useState<boolean | null>(null);
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);

  const ensureAuth = useCallback(async (): Promise<string | null> => {
    let access = getAccessToken();
    if (!access) {
      router.replace('/login');
      return null;
    }
    try {
      const me = await staffMe(access);
      setUser(me);
      updateStoredUser(me);
      if (!hasCap(me, 'crm_email_mkt', 'view') && !hasCap(me, 'crm_agency', 'view')) {
        setError('Không có quyền');
        return null;
      }
      return access;
    } catch {
      const refresh = getRefreshToken();
      if (!refresh) {
        clearSession();
        router.replace('/login');
        return null;
      }
      const out = await staffRefresh(refresh);
      updateAccessToken(out.access_token);
      access = out.access_token;
      setUser(await staffMe(access));
      return access;
    }
  }, [router]);

  const load = useCallback(
    async (access: string) => {
      setError('');
      try {
        const row = await fetchEmailTemplate(access, templateId);
        setTemplate(row);
        setName(row.name);
        setSubject(row.subject_template);
        setHtmlBody(row.html_body);
        setTextBody(row.text_body ?? '');
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Tải template thất bại');
      }
    },
    [templateId],
  );

  useEffect(() => {
    void (async () => {
      const access = await ensureAuth();
      if (!access) return;
      await load(access);
    })();
  }, [ensureAuth, load]);

  function insertBlock(html: string) {
    setHtmlBody((prev) => (prev.trim() ? `${prev.trim()}\n\n${html}` : html));
    push('Đã chèn block vào HTML', 'success');
  }

  async function save() {
    const access = getAccessToken();
    if (!access) return;
    setSaving(true);
    setError('');
    try {
      const row = await patchEmailTemplate(access, templateId, {
        name: name.trim(),
        subject_template: subject.trim(),
        html_body: htmlBody,
        text_body: textBody.trim() || undefined,
      });
      setTemplate(row);
      push('Đã lưu template', 'success');
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Lưu thất bại';
      setError(msg);
      push(msg, 'error');
    } finally {
      setSaving(false);
    }
  }

  async function runPreflight() {
    const access = getAccessToken();
    if (!access) return;
    setError('');
    try {
      const out = await preflightEmailTemplate(access, templateId);
      setChecks(out.checks);
      setPreflightPassed(out.passed);
      push(out.passed ? 'Preflight passed' : 'Preflight có cảnh báo', out.passed ? 'success' : 'error');
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Preflight thất bại';
      setError(msg);
      push(msg, 'error');
    }
  }

  if (!user) return <main style={{ padding: '2rem' }}><p className="muted">Đang tải…</p></main>;

  const canWrite = hasCap(user, 'crm_email_mkt', 'write') || hasCap(user, 'crm_agency', 'create');

  return (
    <main style={{ maxWidth: 1180, margin: '0 auto', padding: '1.5rem' }}>
      <OpsNav user={user} onLogout={() => { clearSession(); router.push('/login'); }} />
      <div className="card" style={{ marginBottom: '1rem' }}>
        <p className="muted" style={{ marginTop: 0 }}>EM-8b E-08b — Template studio</p>
        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', alignItems: 'center' }}>
          <Link href="/email/templates" className="btn btn-secondary btn-sm">← Templates</Link>
          {canWrite ? (
            <button type="button" className="btn btn-sm" disabled={saving} onClick={() => void save()}>
              {saving ? '…' : 'Lưu'}
            </button>
          ) : null}
          <button type="button" className="btn btn-secondary btn-sm" onClick={() => void runPreflight()}>
            Preflight
          </button>
        </div>
        {template ? (
          <p className="muted" style={{ marginBottom: 0 }}>
            {template.client_name} · v{template.version} · {template.status}
          </p>
        ) : null}
      </div>
      {error ? <p className="error">{error}</p> : null}

      <div className="email-template-studio">
        <div className="email-template-editor card">
          <nav className="email-builder-tabs" aria-label="Editor tabs">
            {(['blocks', 'html', 'text'] as const).map((tab) => (
              <button
                key={tab}
                type="button"
                className={editorTab === tab ? 'active' : undefined}
                onClick={() => setEditorTab(tab)}
              >
                {tab === 'blocks' ? 'Blocks' : tab === 'html' ? 'HTML' : 'Text'}
              </button>
            ))}
          </nav>

          <label style={{ display: 'block', marginBottom: '0.75rem' }}>
            Name
            <input value={name} onChange={(e) => setName(e.target.value)} disabled={!canWrite} style={{ display: 'block', width: '100%', marginTop: '0.25rem' }} />
          </label>
          <label style={{ display: 'block', marginBottom: '0.75rem' }}>
            Subject
            <input value={subject} onChange={(e) => setSubject(e.target.value)} disabled={!canWrite} style={{ display: 'block', width: '100%', marginTop: '0.25rem' }} />
          </label>

          {editorTab === 'blocks' ? (
            <TemplateBlockLibrary onInsert={insertBlock} disabled={!canWrite} />
          ) : null}
          {editorTab === 'html' ? (
            <label style={{ display: 'block' }}>
              HTML body
              <textarea value={htmlBody} onChange={(e) => setHtmlBody(e.target.value)} disabled={!canWrite} rows={14} style={{ display: 'block', width: '100%', marginTop: '0.25rem', fontFamily: 'monospace' }} />
            </label>
          ) : null}
          {editorTab === 'text' ? (
            <label style={{ display: 'block' }}>
              Text body (optional)
              <textarea value={textBody} onChange={(e) => setTextBody(e.target.value)} disabled={!canWrite} rows={14} style={{ display: 'block', width: '100%', marginTop: '0.25rem', fontFamily: 'monospace' }} />
            </label>
          ) : null}
        </div>

        <div className="email-template-preview card">
          <h3 style={{ marginTop: 0 }}>Preview</h3>
          <div className="email-preview-dual">
            <div>
              <p className="muted" style={{ marginTop: 0, fontSize: '0.8125rem' }}>Desktop</p>
              <div className="email-preview-frame">
                <iframe title="Email preview desktop" srcDoc={htmlBody} sandbox="" />
              </div>
            </div>
            <div>
              <p className="muted" style={{ marginTop: 0, fontSize: '0.8125rem' }}>Mobile (320px)</p>
              <div className="email-preview-frame email-preview-frame--mobile">
                <iframe title="Email preview mobile" srcDoc={htmlBody} sandbox="" />
              </div>
            </div>
          </div>
        </div>
      </div>

      {checks.length > 0 ? (
        <div className="card" style={{ marginTop: '1rem' }}>
          <h2 style={{ marginTop: 0, fontSize: '1.1rem' }}>
            Preflight {preflightPassed ? '✓ passed' : '✗ failed'}
          </h2>
          <PreflightChecklist checks={checks} />
        </div>
      ) : null}
    </main>
  );
}
