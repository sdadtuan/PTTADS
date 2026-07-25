'use client';

import Link from 'next/link';
import { Suspense, useCallback, useEffect, useMemo, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { OpsNav } from '@/components/OpsNav';
import {
  autolinkSeoEntities,
  captureSeoSerpSnapshot,
  createSeoCluster,
  createSeoContentFromResearch,
  createSeoKeyword,
  createSeoQuestion,
  fetchSeoClients,
  fetchSeoResearchConsole,
  importSeoKeywordsCsv,
  previewSeoBrief,
  syncSeoPagesFromGsc,
  staffMe,
  staffRefresh,
  type SeoBriefPreviewResponse,
  type SeoClusterRow,
  type SeoHubClientRow,
  type SeoKeywordRow,
  type SeoPageRow,
  type SeoQuestionRow,
  type SeoSerpSnapshotRow,
} from '@/lib/api';
import {
  clearSession,
  getAccessToken,
  getRefreshToken,
  getStoredUser,
  updateAccessToken,
  updateStoredUser,
  type StoredStaffUser,
} from '@/lib/auth';
import { canViewSeoResearch, canWriteSeo } from '@/lib/seo/caps';
import type { SeoResearchTab } from '@/lib/seo/types';

const TABS: Array<{ key: SeoResearchTab; label: string }> = [
  { key: 'keywords', label: 'Keywords' },
  { key: 'questions', label: 'Questions' },
  { key: 'entities', label: 'Entities' },
  { key: 'clusters', label: 'Clusters' },
  { key: 'serp', label: 'SERP' },
  { key: 'pages', label: 'Pages' },
  { key: 'opportunities', label: 'Opportunities' },
];

function tabApiKey(tab: SeoResearchTab): string | undefined {
  return tab;
}

export default function SeoResearchPage() {
  return (
    <Suspense
      fallback={
        <main style={{ padding: '2rem' }}>
          <p className="muted">Đang tải research console…</p>
        </main>
      }
    >
      <SeoResearchContent />
    </Suspense>
  );
}

function SeoResearchContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [user, setUser] = useState<StoredStaffUser | null>(null);
  const [clients, setClients] = useState<SeoHubClientRow[]>([]);
  const [customerId, setCustomerId] = useState('');
  const [tab, setTab] = useState<SeoResearchTab>('keywords');
  const [keywords, setKeywords] = useState<SeoKeywordRow[]>([]);
  const [questions, setQuestions] = useState<SeoQuestionRow[]>([]);
  const [entities, setEntities] = useState<
    Array<{
      entity_key: string;
      label: string;
      intent: string;
      keyword_count: number;
      avg_opportunity_score: number;
      top_opportunity_score: number;
    }>
  >([]);
  const [clusters, setClusters] = useState<SeoClusterRow[]>([]);
  const [opportunities, setOpportunities] = useState<SeoKeywordRow[]>([]);
  const [serpSnapshots, setSerpSnapshots] = useState<SeoSerpSnapshotRow[]>([]);
  const [pages, setPages] = useState<SeoPageRow[]>([]);
  const [searchQ, setSearchQ] = useState('');
  const [intentFilter, setIntentFilter] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [briefPreview, setBriefPreview] = useState<SeoBriefPreviewResponse | null>(null);
  const [briefBusy, setBriefBusy] = useState(false);
  const [briefSource, setBriefSource] = useState<{ keywordId?: number; questionId?: number } | null>(
    null,
  );
  const [toast, setToast] = useState('');

  const ensureAuth = useCallback(async (): Promise<string | null> => {
    let access = getAccessToken();
    if (!access) {
      router.replace('/login');
      return null;
    }
    const cached = getStoredUser();
    if (cached) setUser(cached);
    try {
      const me = await staffMe(access);
      setUser(me);
      updateStoredUser(me);
      if (!canViewSeoResearch(me)) {
        setError('Không có quyền SEO Research');
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
      const me = await staffMe(access);
      setUser(me);
      updateStoredUser(me);
      return access;
    }
  }, [router]);

  const loadClients = useCallback(async (access: string) => {
    const out = await fetchSeoClients(access);
    setClients(out.clients);
    if (!customerId && out.clients[0]) {
      setCustomerId(String(out.clients[0].customer_id));
    }
  }, [customerId]);

  const loadResearch = useCallback(
    async (access: string, cid: number, activeTab: SeoResearchTab) => {
      setLoading(true);
      setError('');
      try {
        const data = await fetchSeoResearchConsole(access, cid, tabApiKey(activeTab));
        setKeywords(data.keywords);
        setQuestions(data.questions);
        setEntities(data.entities);
        setClusters(data.clusters);
        setOpportunities(data.opportunities);
        setSerpSnapshots(data.serp_snapshots ?? []);
        setPages(data.pages ?? []);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Không tải được research console');
      } finally {
        setLoading(false);
      }
    },
    [],
  );

  useEffect(() => {
    const initTab = (searchParams.get('tab') as SeoResearchTab | null) ?? 'keywords';
    if (TABS.some((t) => t.key === initTab)) setTab(initTab);
    const cid = searchParams.get('customer_id');
    if (cid) setCustomerId(cid);
  }, [searchParams]);

  useEffect(() => {
    void (async () => {
      const access = await ensureAuth();
      if (!access) return;
      await loadClients(access);
    })();
  }, [ensureAuth, loadClients]);

  useEffect(() => {
    const cid = Number.parseInt(customerId, 10);
    if (!customerId || Number.isNaN(cid)) return;
    void (async () => {
      const access = await ensureAuth();
      if (!access) return;
      await loadResearch(access, cid, tab);
    })();
  }, [customerId, tab, ensureAuth, loadResearch]);

  const filteredKeywords = useMemo(() => {
    const q = searchQ.trim().toLowerCase();
    return keywords.filter((k) => {
      if (intentFilter && k.intent !== intentFilter) return false;
      if (!q) return true;
      return k.phrase.toLowerCase().includes(q);
    });
  }, [keywords, searchQ, intentFilter]);

  const filteredQuestions = useMemo(() => {
    const q = searchQ.trim().toLowerCase();
    if (!q) return questions;
    return questions.filter((item) => item.question_text.toLowerCase().includes(q));
  }, [questions, searchQ]);

  const filteredPages = useMemo(() => {
    const q = searchQ.trim().toLowerCase();
    if (!q) return pages;
    return pages.filter(
      (p) => p.url.toLowerCase().includes(q) || p.title.toLowerCase().includes(q) || p.slug.toLowerCase().includes(q),
    );
  }, [pages, searchQ]);

  const filteredSerp = useMemo(() => {
    const q = searchQ.trim().toLowerCase();
    if (!q) return serpSnapshots;
    return serpSnapshots.filter((s) => s.phrase.toLowerCase().includes(q));
  }, [serpSnapshots, searchQ]);

  const logout = () => {
    clearSession();
    router.push('/login');
  };

  const canWrite = canWriteSeo(user);

  async function handleImportCsv() {
    if (!canWrite || !customerId) return;
    const csv = window.prompt('Dán nội dung CSV (phrase,volume,difficulty,intent,business_value)');
    if (!csv) return;
    const access = await ensureAuth();
    if (!access) return;
    try {
      const out = await importSeoKeywordsCsv(access, Number.parseInt(customerId, 10), csv);
      setToast(`Đã import ${out.imported} keyword`);
      await loadResearch(access, Number.parseInt(customerId, 10), tab);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Import thất bại');
    }
  }

  async function handleAddKeyword() {
    if (!canWrite || !customerId) return;
    const phrase = window.prompt('Keyword phrase');
    if (!phrase?.trim()) return;
    const access = await ensureAuth();
    if (!access) return;
    await createSeoKeyword(access, Number.parseInt(customerId, 10), { phrase: phrase.trim() });
    await loadResearch(access, Number.parseInt(customerId, 10), tab);
  }

  async function handleAddQuestion() {
    if (!canWrite || !customerId) return;
    const text = window.prompt('Câu hỏi AEO');
    if (!text?.trim()) return;
    const access = await ensureAuth();
    if (!access) return;
    await createSeoQuestion(access, Number.parseInt(customerId, 10), { question_text: text.trim() });
    await loadResearch(access, Number.parseInt(customerId, 10), tab);
  }

  async function handleAddCluster() {
    if (!canWrite || !customerId) return;
    const name = window.prompt('Tên cluster');
    if (!name?.trim()) return;
    const access = await ensureAuth();
    if (!access) return;
    await createSeoCluster(access, Number.parseInt(customerId, 10), { name: name.trim() });
    await loadResearch(access, Number.parseInt(customerId, 10), tab);
  }

  async function openBriefPreview(source: { keywordId?: number; questionId?: number }) {
    if (!customerId) return;
    const access = await ensureAuth();
    if (!access) return;
    setBriefBusy(true);
    setBriefSource(source);
    try {
      const preview = await previewSeoBrief(access, {
        customer_id: Number.parseInt(customerId, 10),
        keyword_id: source.keywordId,
        question_id: source.questionId,
      });
      setBriefPreview(preview);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không tạo được brief preview');
    } finally {
      setBriefBusy(false);
    }
  }

  async function acceptBrief() {
    if (!canWrite || !briefPreview || !customerId || !briefSource) return;
    const access = await ensureAuth();
    if (!access) return;
    setBriefBusy(true);
    try {
      const out = await createSeoContentFromResearch(access, {
        customer_id: Number.parseInt(customerId, 10),
        keyword_id: briefSource.keywordId,
        question_id: briefSource.questionId,
        title: briefPreview.title,
        brief: briefPreview.brief,
      });
      setBriefPreview(null);
      setBriefSource(null);
      router.push(`/seo/content/${out.content.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không tạo được content');
    } finally {
      setBriefBusy(false);
    }
  }

  async function handleSyncPages() {
    if (!canWrite || !customerId) return;
    const access = await ensureAuth();
    if (!access) return;
    try {
      const out = await syncSeoPagesFromGsc(access, Number.parseInt(customerId, 10), 90);
      setToast(`Đã sync ${out.synced} pages từ GSC`);
      await loadResearch(access, Number.parseInt(customerId, 10), tab);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Sync pages thất bại');
    }
  }

  async function handleCaptureSerp() {
    if (!canWrite || !customerId) return;
    const phrase = window.prompt('Keyword phrase để capture SERP');
    if (!phrase?.trim()) return;
    const access = await ensureAuth();
    if (!access) return;
    try {
      const out = await captureSeoSerpSnapshot(access, Number.parseInt(customerId, 10), {
        phrase: phrase.trim(),
      });
      setToast(`SERP captured (${String(out.snapshot.source ?? 'stub')})`);
      await loadResearch(access, Number.parseInt(customerId, 10), tab);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Capture SERP thất bại');
    }
  }

  async function handleAutolinkEntities() {
    if (!canWrite || !customerId) return;
    const access = await ensureAuth();
    if (!access) return;
    try {
      const out = await autolinkSeoEntities(access, Number.parseInt(customerId, 10));
      setToast(`Autolink: +${out.entities_created} entities, +${out.links_created} links`);
      await loadResearch(access, Number.parseInt(customerId, 10), tab);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Autolink thất bại');
    }
  }

  return (
    <div className="page">
      <OpsNav user={user} onLogout={logout} />
      <main className="main-content">
        <div className="page-header">
          <div>
            <h1>Nghiên cứu SEO/AEO</h1>
            <p className="muted">Research Console — keywords, questions, clusters, brief → content</p>
          </div>
          <div className="page-actions">
            <Link href="/seo/hub" className="btn btn-secondary btn-sm">
              Hub
            </Link>
            <Link href="/seo/content" className="btn btn-secondary btn-sm">
              Pipeline
            </Link>
          </div>
        </div>

        <div className="card" style={{ marginBottom: '1rem' }}>
          <div className="form-row" style={{ alignItems: 'end', gap: '1rem', flexWrap: 'wrap' }}>
            <label>
              Client
              <select value={customerId} onChange={(e) => setCustomerId(e.target.value)}>
                <option value="">— Chọn client —</option>
                {clients.map((c) => (
                  <option key={c.customer_id} value={c.customer_id}>
                    {c.customer_name} (#{c.customer_id})
                  </option>
                ))}
              </select>
            </label>
            <label>
              Tìm kiếm
              <input value={searchQ} onChange={(e) => setSearchQ(e.target.value)} placeholder="Filter…" />
            </label>
            {tab === 'keywords' && (
              <label>
                Intent
                <select value={intentFilter} onChange={(e) => setIntentFilter(e.target.value)}>
                  <option value="">Tất cả</option>
                  <option value="informational">Informational</option>
                  <option value="commercial">Commercial</option>
                  <option value="transactional">Transactional</option>
                  <option value="navigational">Navigational</option>
                </select>
              </label>
            )}
            {canWrite && (
              <>
                <button type="button" className="btn btn-sm" onClick={() => void handleImportCsv()}>
                  Import CSV
                </button>
                {tab === 'keywords' && (
                  <button type="button" className="btn btn-sm" onClick={() => void handleAddKeyword()}>
                    + Keyword
                  </button>
                )}
                {tab === 'questions' && (
                  <button type="button" className="btn btn-sm" onClick={() => void handleAddQuestion()}>
                    + Question
                  </button>
                )}
                {tab === 'clusters' && (
                  <button type="button" className="btn btn-sm" onClick={() => void handleAddCluster()}>
                    + Cluster
                  </button>
                )}
                {tab === 'serp' && (
                  <button type="button" className="btn btn-sm" onClick={() => void handleCaptureSerp()}>
                    Capture SERP
                  </button>
                )}
                {tab === 'pages' && (
                  <button type="button" className="btn btn-sm" onClick={() => void handleSyncPages()}>
                    Sync GSC pages
                  </button>
                )}
                {tab === 'entities' && (
                  <button type="button" className="btn btn-sm" onClick={() => void handleAutolinkEntities()}>
                    Auto-link clusters
                  </button>
                )}
              </>
            )}
          </div>
        </div>

        <div className="tabs" style={{ marginBottom: '1rem', flexWrap: 'wrap' }}>
          {TABS.map((t) => (
            <button
              key={t.key}
              type="button"
              className={tab === t.key ? 'tab active' : 'tab'}
              onClick={() => setTab(t.key)}
            >
              {t.label}
            </button>
          ))}
        </div>

        {error && <p className="error">{error}</p>}
        {toast && <p className="badge">{toast}</p>}

        {!customerId ? (
          <p className="muted">Chọn client để xem dữ liệu research.</p>
        ) : loading ? (
          <p className="muted">Đang tải…</p>
        ) : tab === 'serp' ? (
          <div className="table-wrap">
            {filteredSerp.length === 0 ? (
              <p className="muted">Chưa có SERP snapshot — chạy rank capture hoặc SerpAPI sync.</p>
            ) : (
              <table>
                <thead>
                  <tr>
                    <th>Keyword</th>
                    <th>Date</th>
                    <th>Source</th>
                    <th>Results</th>
                    <th>Top SERP</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredSerp.map((s) => (
                    <tr key={s.id}>
                      <td>{s.phrase || '—'}</td>
                      <td>{s.snapshot_date || '—'}</td>
                      <td>{s.source || '—'}</td>
                      <td>{s.result_count}</td>
                      <td style={{ fontSize: '0.85rem', maxWidth: 360 }}>
                        {s.top_results.length > 0
                          ? s.top_results
                              .map((r) => String(r.title ?? r.url ?? r.link ?? '—'))
                              .join(' · ')
                          : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        ) : tab === 'pages' ? (
          <div className="table-wrap">
            {filteredPages.length === 0 ? (
              <p className="muted">Chưa có page inventory — sync GSC hoặc crawl technical.</p>
            ) : (
              <table>
                <thead>
                  <tr>
                    <th>URL</th>
                    <th>Title</th>
                    <th>Type</th>
                    <th>Status</th>
                    <th>Last crawled</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredPages.map((p) => (
                    <tr key={p.id}>
                      <td style={{ maxWidth: 280, wordBreak: 'break-all' }}>{p.url}</td>
                      <td>{p.title || p.slug || '—'}</td>
                      <td>{p.content_type || '—'}</td>
                      <td>{p.status || '—'}</td>
                      <td>{p.last_crawled_at ?? '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        ) : tab === 'keywords' ? (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Keyword</th>
                  <th>Vol</th>
                  <th>KD</th>
                  <th>Intent</th>
                  <th>Cluster</th>
                  <th>Opp</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {filteredKeywords.map((k) => (
                  <tr key={k.id}>
                    <td>{k.phrase}</td>
                    <td>{k.volume ?? '—'}</td>
                    <td>{k.difficulty ?? '—'}</td>
                    <td>{k.intent || '—'}</td>
                    <td>{k.cluster_name ?? '—'}</td>
                    <td>{k.opportunity_score ?? '—'}</td>
                    <td>
                      <button
                        type="button"
                        className="btn btn-secondary btn-sm"
                        onClick={() => void openBriefPreview({ keywordId: k.id })}
                      >
                        → Brief
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : tab === 'questions' ? (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Question</th>
                  <th>Intent</th>
                  <th>Funnel</th>
                  <th>Source</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {filteredQuestions.map((q) => (
                  <tr key={q.id}>
                    <td>{q.question_text}</td>
                    <td>{q.intent || '—'}</td>
                    <td>{q.funnel_stage || '—'}</td>
                    <td>{q.source || '—'}</td>
                    <td>
                      <button
                        type="button"
                        className="btn btn-secondary btn-sm"
                        onClick={() => void openBriefPreview({ questionId: q.id })}
                      >
                        → Brief
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : tab === 'entities' ? (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Entity</th>
                  <th>Intent</th>
                  <th>Keywords</th>
                  <th>Avg opp</th>
                  <th>Top opp</th>
                </tr>
              </thead>
              <tbody>
                {entities.map((e) => (
                  <tr key={e.entity_key}>
                    <td>{e.label}</td>
                    <td>{e.intent}</td>
                    <td>{e.keyword_count}</td>
                    <td>{e.avg_opportunity_score}</td>
                    <td>{e.top_opportunity_score}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : tab === 'clusters' ? (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Cluster</th>
                  <th>Intent</th>
                  <th>Keywords</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {clusters.map((c) => (
                  <tr key={c.id}>
                    <td>{c.name}</td>
                    <td>{c.intent || '—'}</td>
                    <td>{c.keyword_count}</td>
                    <td>{c.status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Keyword</th>
                  <th>Opp score</th>
                  <th>Vol</th>
                  <th>KD</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {opportunities.map((k) => (
                  <tr key={k.id}>
                    <td>{k.phrase}</td>
                    <td>{k.opportunity_score ?? '—'}</td>
                    <td>{k.volume ?? '—'}</td>
                    <td>{k.difficulty ?? '—'}</td>
                    <td>
                      <button
                        type="button"
                        className="btn btn-secondary btn-sm"
                        onClick={() => void openBriefPreview({ keywordId: k.id })}
                      >
                        → Brief
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {briefPreview && (
          <div className="modal-backdrop" role="presentation" onClick={() => setBriefPreview(null)}>
            <div
              className="modal card"
              role="dialog"
              aria-modal="true"
              onClick={(e) => e.stopPropagation()}
              style={{ maxWidth: 720 }}
            >
              <h2>Brief preview — {briefPreview.title}</h2>
              <p className="muted">
                Nguồn: {briefPreview.source}
                {briefPreview.ai_available ? ' · AI có thể bật (ANTHROPIC_API_KEY)' : ' · Template only'}
              </p>
              <pre style={{ whiteSpace: 'pre-wrap', fontSize: '0.85rem' }}>
                {JSON.stringify(briefPreview.brief, null, 2)}
              </pre>
              <div className="page-actions">
                <button type="button" className="btn btn-secondary" onClick={() => setBriefPreview(null)}>
                  Đóng
                </button>
                {canWrite && (
                  <button type="button" className="btn" disabled={briefBusy} onClick={() => void acceptBrief()}>
                    {briefBusy ? 'Đang tạo…' : 'Tạo content → Pipeline'}
                  </button>
                )}
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
