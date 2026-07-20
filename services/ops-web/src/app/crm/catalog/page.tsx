'use client';

import Link from 'next/link';
import { useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { OpsNav } from '@/components/OpsNav';
import {
  createAssignScope,
  createCatalogIndustry,
  createCatalogService,
  deleteAssignScope,
  fetchCatalogBundle,
  patchCatalogIndustry,
  patchCatalogService,
  staffMe,
  staffRefresh,
  type AssignScopeRow,
  type CatalogIndustryRow,
  type CatalogServiceRow,
  type CatalogStaffOption,
} from '@/lib/api';
import {
  clearSession,
  getAccessToken,
  getRefreshToken,
  getStoredUser,
  hasCap,
  updateAccessToken,
  updateStoredUser,
  type StoredStaffUser,
} from '@/lib/auth';

export default function CrmCatalogPage() {
  const router = useRouter();
  const [user, setUser] = useState<StoredStaffUser | null>(null);
  const [token, setToken] = useState('');
  const [services, setServices] = useState<CatalogServiceRow[]>([]);
  const [industries, setIndustries] = useState<CatalogIndustryRow[]>([]);
  const [scopes, setScopes] = useState<AssignScopeRow[]>([]);
  const [staff, setStaff] = useState<CatalogStaffOption[]>([]);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const canConfigure = hasCap(user, 'crm_leads', 'configure');

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
      if (!hasCap(me, 'crm_leads', 'view')) {
        setError('Không có quyền xem danh mục CRM');
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

  const reload = useCallback(async (accessToken: string) => {
    setLoading(true);
    setError('');
    try {
      const bundle = await fetchCatalogBundle(accessToken);
      setServices(bundle.services);
      setIndustries(bundle.industries);
      setScopes(bundle.scopes);
      setStaff(bundle.staff);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Tải catalog thất bại');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void (async () => {
      const access = await ensureAuth();
      if (!access) return;
      setToken(access);
      await reload(access);
    })();
  }, [ensureAuth, reload]);

  function logout() {
    clearSession();
    router.push('/login');
  }

  async function onAddService() {
    if (!token || !canConfigure) return;
    const slug = window.prompt('Slug dịch vụ (vd: lead-gen)')?.trim();
    const name = window.prompt('Tên dịch vụ')?.trim();
    if (!slug || !name) return;
    try {
      await createCatalogService(token, { slug, name });
      await reload(token);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Thêm dịch vụ thất bại');
    }
  }

  async function onToggleService(row: CatalogServiceRow) {
    if (!token || !canConfigure) return;
    try {
      await patchCatalogService(token, row.id, { active: !row.active });
      await reload(token);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Cập nhật dịch vụ thất bại');
    }
  }

  async function onAddIndustry() {
    if (!token || !canConfigure) return;
    const slug = window.prompt('Slug ngành (vd: spa)')?.trim();
    const name = window.prompt('Tên ngành')?.trim();
    if (!slug || !name) return;
    try {
      await createCatalogIndustry(token, { slug, name });
      await reload(token);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Thêm ngành thất bại');
    }
  }

  async function onToggleIndustry(row: CatalogIndustryRow) {
    if (!token || !canConfigure) return;
    try {
      await patchCatalogIndustry(token, row.id, { active: !row.active });
      await reload(token);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Cập nhật ngành thất bại');
    }
  }

  async function onAddScope() {
    if (!token || !canConfigure || !staff.length) return;
    const staffId = window.prompt(`Staff ID (${staff.map((s) => `${s.id}:${s.name}`).join(', ')})`);
    if (!staffId) return;
    const industry = window.prompt('Industry slug hoặc *')?.trim() || '*';
    const service = window.prompt('Service slug hoặc *')?.trim() || '*';
    try {
      await createAssignScope(token, {
        staff_id: Number(staffId),
        industry_slug: industry,
        service_slug: service,
      });
      await reload(token);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Thêm phạm vi thất bại');
    }
  }

  async function onDeleteScope(id: number) {
    if (!token || !canConfigure) return;
    if (!window.confirm('Xóa phạm vi phân lead?')) return;
    try {
      await deleteAssignScope(token, id);
      await reload(token);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Xóa phạm vi thất bại');
    }
  }

  if (!user) {
    return (
      <main style={{ padding: '2rem' }}>
        <p className="muted">Đang tải…</p>
      </main>
    );
  }

  return (
    <main style={{ maxWidth: 1200, margin: '0 auto', padding: '1.5rem' }}>
      <OpsNav user={user} onLogout={logout} />
      <div className="card" style={{ marginBottom: '1rem' }}>
        <h1 style={{ marginTop: 0 }}>Danh mục Dịch vụ &amp; Ngành</h1>
        <p className="muted">
          Quản trị slug dịch vụ PTT và ngành khách hàng — form lead, pre-sales và phân công AM.
        </p>
        <Link href="/crm/leads" className="nav-link">
          ← Quản lý Lead
        </Link>
      </div>

      {error ? <p className="error">{error}</p> : null}

      <div className="card" style={{ marginBottom: '1rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <h2 style={{ margin: 0 }}>Dịch vụ PTT</h2>
          {canConfigure ? (
            <button type="button" className="btn btn-sm" onClick={() => void onAddService()} disabled={loading}>
              Thêm dịch vụ
            </button>
          ) : null}
        </div>
        <table className="perf-table" style={{ marginTop: '0.75rem' }}>
          <thead>
            <tr>
              <th>Slug</th>
              <th>Tên</th>
              <th>Thứ tự</th>
              <th>Trạng thái</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {services.map((row) => (
              <tr key={row.id}>
                <td>{row.slug}</td>
                <td>{row.name}</td>
                <td>{row.sort_order}</td>
                <td>{row.active ? 'Active' : 'Off'}</td>
                <td>
                  {canConfigure ? (
                    <button type="button" className="btn btn-secondary btn-sm" onClick={() => void onToggleService(row)}>
                      {row.active ? 'Tắt' : 'Bật'}
                    </button>
                  ) : null}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="card" style={{ marginBottom: '1rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <h2 style={{ margin: 0 }}>Ngành khách hàng</h2>
          {canConfigure ? (
            <button type="button" className="btn btn-sm" onClick={() => void onAddIndustry()} disabled={loading}>
              Thêm ngành
            </button>
          ) : null}
        </div>
        <table className="perf-table" style={{ marginTop: '0.75rem' }}>
          <thead>
            <tr>
              <th>Slug</th>
              <th>Tên</th>
              <th>Thứ tự</th>
              <th>Trạng thái</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {industries.map((row) => (
              <tr key={row.id}>
                <td>{row.slug}</td>
                <td>{row.name}</td>
                <td>{row.sort_order}</td>
                <td>{row.active ? 'Active' : 'Off'}</td>
                <td>
                  {canConfigure ? (
                    <button
                      type="button"
                      className="btn btn-secondary btn-sm"
                      onClick={() => void onToggleIndustry(row)}
                    >
                      {row.active ? 'Tắt' : 'Bật'}
                    </button>
                  ) : null}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="card">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <h2 style={{ margin: 0 }}>Phạm vi phân lead (AM)</h2>
          {canConfigure ? (
            <button type="button" className="btn btn-sm" onClick={() => void onAddScope()} disabled={loading}>
              Thêm phạm vi
            </button>
          ) : null}
        </div>
        <table className="perf-table" style={{ marginTop: '0.75rem' }}>
          <thead>
            <tr>
              <th>AM</th>
              <th>Ngành</th>
              <th>Dịch vụ</th>
              <th>Active</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {scopes.map((row) => (
              <tr key={row.id}>
                <td>{row.staff_name || row.staff_id}</td>
                <td>{row.industry_slug}</td>
                <td>{row.service_slug}</td>
                <td>{row.active ? 'Yes' : 'No'}</td>
                <td>
                  {canConfigure ? (
                    <button type="button" className="btn btn-secondary btn-sm" onClick={() => void onDeleteScope(row.id)}>
                      Xóa
                    </button>
                  ) : null}
                </td>
              </tr>
            ))}
            {!scopes.length ? (
              <tr>
                <td colSpan={5} className="muted">
                  Chưa có phạm vi phân lead
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </main>
  );
}
