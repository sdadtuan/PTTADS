/* cms_landing.js — CMS quản lý Landing Page PTT */
'use strict';

// ── Utils ────────────────────────────────────────────────────────────────────

function qs(sel, ctx) { return (ctx || document).querySelector(sel); }
function qsa(sel, ctx) { return Array.from((ctx || document).querySelectorAll(sel)); }

function showMsg(el, text, isErr) {
  if (!el) return;
  el.textContent = text;
  el.className = 'clp-save-msg' + (isErr ? ' is-error' : ' is-ok');
  clearTimeout(el._t);
  el._t = setTimeout(() => { el.textContent = ''; el.className = 'clp-save-msg'; }, 4000);
  if (!isErr) markPreviewStale();
}

function markPreviewStale() {
  if (_previewOpen) qs('#preview-stale-badge')?.classList.remove('is-hidden');
}

async function apiFetch(url, opts) {
  const r = await fetch(url, opts);
  if (!r.ok) {
    const j = await r.json().catch(() => ({}));
    throw new Error(j.error || `HTTP ${r.status}`);
  }
  if (r.status === 204) return null;
  return r.json();
}

/** Upload ảnh CMS; purpose=hero_desktop|hero_mobile|project|… → server auto crop cover. */
async function uploadMediaFile(file, purpose) {
  const fd = new FormData();
  fd.append('file', file);
  if (purpose) fd.append('purpose', purpose);
  const r = await fetch('/api/cms/media/upload', { method: 'POST', body: fd });
  if (!r.ok) {
    const j = await r.json().catch(() => ({}));
    throw new Error(j.error || `HTTP ${r.status}`);
  }
  return r.json();
}

function formatUploadStatus(j) {
  const parts = [];
  if (j.cropped && j.width && j.height) {
    const desktop = `${j.width}×${j.height}`;
    const mobile = j.width_mobile && j.height_mobile ? ` + mobile ${j.width_mobile}×${j.height_mobile}` : '';
    parts.push(`${desktop} cover${mobile}`);
  }
  if (j.optimized && j.size_before && j.size) {
    const saved = Math.max(0, Math.round((1 - j.size / j.size_before) * 100));
    parts.push(`tối ưu −${saved}%`);
  }
  if (j.video_codec) parts.push(String(j.video_codec).toUpperCase());
  if (j.ext) parts.push(j.ext.toUpperCase());
  if (j.size) {
    const kb = j.size / 1024;
    parts.push(kb >= 1024 ? `${Math.round(kb / 102.4) / 10} MB` : `${Math.round(kb)}KB`);
  }
  return parts.join(', ');
}

function imgOrPlaceholder(url) {
  return url ? `<img src="${escH(url)}" class="clp-thumb" alt="" loading="lazy" />` : '<span class="clp-no-img">—</span>';
}

function escH(s) {
  return String(s || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function stripHtml(s) {
  const el = document.createElement('div');
  el.innerHTML = String(s || '');
  return (el.textContent || el.innerText || '').trim();
}

/** Plain-text excerpt for list cards (Quill HTML → text, truncated). */
function excerptHtml(s, maxLen = 200) {
  const text = stripHtml(s);
  if (text.length <= maxLen) return text;
  return text.slice(0, maxLen) + '…';
}

function fmtSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes/1024).toFixed(1)} KB`;
  return `${(bytes/1024/1024).toFixed(1)} MB`;
}

// ── Tab switching ─────────────────────────────────────────────────────────────

const TABS = ['hero','content','projects','blog','services','media'];

function activateTab(name) {
  qsa('.clp-tab').forEach(btn => {
    const active = btn.dataset.tab === name;
    btn.classList.toggle('is-active', active);
    btn.setAttribute('aria-selected', active ? 'true' : 'false');
  });
  TABS.forEach(t => {
    const panel = qs(`#tab-${t}`);
    if (panel) panel.classList.toggle('is-hidden', t !== name);
  });
  if (name === 'media') loadMedia();
  if (name === 'projects') { _initProjectQuill(); loadProjects(); }
  if (name === 'blog') { _initBlogQuill(); loadBlog(); }
  if (name === 'services') loadServices();
  if (name === 'content') {
    renderPartnersEditor();
    renderCapabilitiesEditor();
  }
}

qsa('.clp-tab').forEach(btn => {
  btn.addEventListener('click', () => activateTab(btn.dataset.tab));
});

// ── Settings loader ───────────────────────────────────────────────────────────

let _settings = {};

async function loadSettings() {
  try {
    _settings = await apiFetch('/api/settings');
    _partnerRows = [];
    _capabilityRows = [];
    const form = qs('#content-form');
    if (!form) return;
    form.querySelectorAll('[name]').forEach(el => {
      const v = _settings[el.name];
      if (v !== undefined) el.value = v;
    });
    renderPartnersEditor();
    renderCapabilitiesEditor();
  } catch (e) {
    console.warn('loadSettings:', e);
    renderPartnersEditor();
    renderCapabilitiesEditor();
  }
}

qs('#content-form')?.addEventListener('submit', async (e) => {
  e.preventDefault();
  const msg = qs('#content-save-msg');
  syncPartnersJsonField();
  syncCapabilitiesJsonField();
  const data = {};
  new FormData(e.target).forEach((v, k) => { data[k] = v; });
  try {
    await apiFetch('/api/settings', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    showMsg(msg, '✓ Đã lưu cài đặt');
  } catch (err) {
    showMsg(msg, '✗ ' + err.message, true);
  }
});

// ── Partners editor (content tab) ─────────────────────────────────────────────

let _partnerRows = [];

function _normalizePartnerLogoUrl(url) {
  const u = String(url || '').trim();
  if (!u) return '';
  if (u.startsWith('http') || u.startsWith('/')) return u;
  return `/static/${u.replace(/^\//, '')}`;
}

function _parsePartnerRowList(data) {
  if (!Array.isArray(data)) return [];
  return data.map(item => ({
    name: String(item?.name || '').trim(),
    site: String(item?.site || '').trim(),
    logo_url: _normalizePartnerLogoUrl(item?.logo_url || item?.logo_file),
  })).filter(row => row.name && row.logo_url);
}

function _defaultPartnerRows() {
  const fromApi = (_settings.partner_logos_effective_json || '').trim();
  if (fromApi) {
    try {
      const rows = _parsePartnerRowList(JSON.parse(fromApi));
      if (rows.length) return rows;
    } catch (_) {
      /* fall through */
    }
  }
  const seed = window.CLP_PARTNER_LOGOS_SEED;
  if (Array.isArray(seed) && seed.length) {
    return _parsePartnerRowList(seed);
  }
  return [];
}

function _readPartnerRowsFromSettings() {
  const raw = (_settings.partner_logos_json || qs('#partner-logos-json')?.value || '').trim();
  if (raw) {
    try {
      const rows = _parsePartnerRowList(JSON.parse(raw));
      if (rows.length) return rows;
    } catch (_) {
      /* fall through to defaults */
    }
  }
  return _defaultPartnerRows();
}

function syncPartnersJsonField() {
  const hidden = qs('#partner-logos-json');
  if (!hidden) return;
  const cleaned = _partnerRows
    .map(row => ({
      name: String(row.name || '').trim(),
      site: String(row.site || '').trim() || '#',
      logo_url: String(row.logo_url || '').trim(),
    }))
    .filter(row => row.name && row.logo_url);
  hidden.value = cleaned.length ? JSON.stringify(cleaned) : '';
}

function renderPartnersEditor() {
  const list = qs('#partners-editor-list');
  if (!list) return;
  if (!_partnerRows.length) _partnerRows = _readPartnerRowsFromSettings();
  if (!_partnerRows.length) {
    list.innerHTML = '<p class="muted">Chưa có logo đối tác. Nhấn + Thêm đối tác để bắt đầu.</p>';
    syncPartnersJsonField();
    return;
  }
  list.innerHTML = _partnerRows.map((row, idx) => `
    <div class="clp-partner-row panel" data-idx="${idx}" style="margin-bottom:.75rem;padding:.75rem">
      <div class="clp-form-row">
        <label class="clp-label">Tên
          <input type="text" class="partner-name-inp" data-idx="${idx}" value="${escH(row.name)}" placeholder="Tên đối tác" />
        </label>
        <label class="clp-label">Website
          <input type="url" class="partner-site-inp" data-idx="${idx}" value="${escH(row.site)}" placeholder="https://..." />
        </label>
      </div>
      <label class="clp-label">Logo URL
        <div class="clp-img-actions">
          <input type="text" class="partner-logo-inp" data-idx="${idx}" value="${escH(row.logo_url)}" placeholder="URL logo..." />
          <button type="button" class="btn clp-pick-btn partner-pick-btn" data-idx="${idx}">Chọn từ Media</button>
          <button type="button" class="btn clp-btn-sm clp-btn-danger partner-del-btn" data-idx="${idx}">Xóa</button>
        </div>
      </label>
      ${row.logo_url ? `<img src="${escH(row.logo_url)}" alt="" class="clp-thumb" loading="lazy" style="margin-top:.5rem;max-height:48px" />` : ''}
    </div>
  `).join('');

  list.querySelectorAll('.partner-name-inp').forEach(inp => {
    inp.addEventListener('input', () => {
      _partnerRows[inp.dataset.idx].name = inp.value;
      syncPartnersJsonField();
    });
  });
  list.querySelectorAll('.partner-site-inp').forEach(inp => {
    inp.addEventListener('input', () => {
      _partnerRows[inp.dataset.idx].site = inp.value;
      syncPartnersJsonField();
    });
  });
  list.querySelectorAll('.partner-logo-inp').forEach(inp => {
    inp.addEventListener('input', () => {
      _partnerRows[inp.dataset.idx].logo_url = inp.value;
      syncPartnersJsonField();
    });
  });
  list.querySelectorAll('.partner-pick-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const idx = parseInt(btn.dataset.idx, 10);
      openMediaPicker(url => {
        _partnerRows[idx].logo_url = url;
        renderPartnersEditor();
        syncPartnersJsonField();
      });
    });
  });
  list.querySelectorAll('.partner-del-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      _partnerRows.splice(parseInt(btn.dataset.idx, 10), 1);
      renderPartnersEditor();
      syncPartnersJsonField();
    });
  });
  syncPartnersJsonField();
}

qs('#partner-add-btn')?.addEventListener('click', () => {
  _partnerRows.push({ name: '', site: '', logo_url: '' });
  renderPartnersEditor();
});

// ── Capabilities editor (content tab) ───────────────────────────────────────

const CAPABILITY_ICON_PRESETS = [
  { value: '0', label: 'Automation — mũi tên vòng' },
  { value: '1', label: 'AI — bóng đèn' },
  { value: '2', label: 'Dữ liệu — biểu đồ' },
  { value: '3', label: 'CRM — nhóm người' },
  { value: '4', label: 'Paid media — con trỏ' },
  { value: '5', label: 'Chat — trải nghiệm' },
];

/** SVG preset — khớp partials/capability_icon.html trên landing */
const CAPABILITY_PRESET_SVGS = [
  '<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/></svg>',
  '<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"/></svg>',
  '<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"/></svg>',
  '<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z"/></svg>',
  '<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M15 15l-2 5L9 9l11 4-5 2zm0 0l5 5M7.188 2.239l.777 2.897M5.136 7.965l-2.898-.777M13.95 4.05l-2.122 2.122m-5.657 5.656l-2.12 2.122"/></svg>',
  '<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z"/></svg>',
];

let _capabilityRows = [];

function _normalizeCapabilityIcon(iconRaw, index) {
  const n = parseInt(String(iconRaw ?? ''), 10);
  if (Number.isFinite(n) && n >= 0 && n <= 5) return String(n);
  return String(((index % 6) + 6) % 6);
}

function _capabilityPresetOptions(selected) {
  return CAPABILITY_ICON_PRESETS.map(
    p => `<option value="${p.value}"${String(selected) === p.value ? ' selected' : ''}>${escH(p.label)}</option>`
  ).join('');
}

function _capabilityIconPreviewHtml(icon, iconUrl) {
  const url = String(iconUrl || '').trim();
  if (url) {
    return `<img src="${escH(url)}" alt="" class="clp-capability-icon-preview-img" loading="lazy" />`;
  }
  const idx = parseInt(String(icon ?? '0'), 10);
  const safe = Number.isFinite(idx) ? ((idx % 6) + 6) % 6 : 0;
  return CAPABILITY_PRESET_SVGS[safe] || CAPABILITY_PRESET_SVGS[0];
}

function _parseCapabilityRowList(data) {
  if (!Array.isArray(data)) return [];
  return data.map((item, i) => {
    if (typeof item === 'string') {
      return { title: item.trim(), icon: String(i % 6), icon_url: '' };
    }
    return {
      title: String(item?.title || item?.text || '').trim(),
      icon: _normalizeCapabilityIcon(item?.icon ?? item?.icon_preset, i),
      icon_url: String(item?.icon_url || '').trim(),
    };
  }).filter(row => row.title);
}

function _defaultCapabilityRows() {
  const fromApi = (_settings.capabilities_items_effective_json || '').trim();
  if (fromApi) {
    try {
      const rows = _parseCapabilityRowList(JSON.parse(fromApi));
      if (rows.length) return rows;
    } catch (_) {
      /* fall through */
    }
  }
  const seed = window.CLP_CAPABILITIES_ITEMS_SEED;
  if (Array.isArray(seed) && seed.length) {
    return _parseCapabilityRowList(seed);
  }
  return _parseCapabilityRowList([
    { title: 'Marketing Automation', icon: '0', icon_url: '' },
    { title: 'AI Content & Personalization', icon: '1', icon_url: '' },
    { title: 'Data Analytics & Business Intelligence', icon: '2', icon_url: '' },
    { title: 'CRM & Lead Intelligence', icon: '3', icon_url: '' },
    { title: 'Paid Media đa kênh & Tối ưu ROI', icon: '4', icon_url: '' },
    { title: 'AI Agent & Customer Experience', icon: '5', icon_url: '' },
  ]);
}

function _readCapabilityRowsFromSettings() {
  const raw = (_settings.capabilities_items_json || qs('#capabilities-items-json')?.value || '').trim();
  if (raw) {
    try {
      const rows = _parseCapabilityRowList(JSON.parse(raw));
      if (rows.length) return rows;
    } catch (_) {
      /* fall through */
    }
  }
  return _defaultCapabilityRows();
}

function _updateCapabilityIconPreview(list, idx) {
  const row = _capabilityRows[idx];
  const box = list?.querySelector(`.clp-capability-icon-preview[data-idx="${idx}"]`);
  if (!row || !box) return;
  box.innerHTML = _capabilityIconPreviewHtml(row.icon, row.icon_url);
}

function syncCapabilitiesJsonField() {
  const hidden = qs('#capabilities-items-json');
  if (!hidden) return;
  const cleaned = _capabilityRows
    .map((row, i) => ({
      title: String(row.title || '').trim(),
      icon: String(row.icon ?? i % 6),
      icon_url: String(row.icon_url || '').trim(),
    }))
    .filter(row => row.title);
  hidden.value = cleaned.length ? JSON.stringify(cleaned) : '';
}

function renderCapabilitiesEditor() {
  const list = qs('#capabilities-editor-list');
  if (!list) return;
  if (!_capabilityRows.length) _capabilityRows = _readCapabilityRowsFromSettings();
  if (!_capabilityRows.length) {
    list.innerHTML = '<p class="muted">Chưa có mục năng lực. Nhấn + Thêm mục năng lực để bắt đầu.</p>';
    syncCapabilitiesJsonField();
    return;
  }

  list.innerHTML = _capabilityRows.map((row, idx) => `
    <div class="clp-capability-row panel" data-idx="${idx}" style="margin-bottom:.75rem;padding:.75rem">
      <div class="clp-capability-row-head">
        <div class="clp-capability-icon-preview" data-idx="${idx}" aria-hidden="true">
          ${_capabilityIconPreviewHtml(row.icon, row.icon_url)}
        </div>
        <div class="clp-capability-row-fields">
          <div class="clp-form-row">
            <label class="clp-label" style="flex:1">Tiêu đề
              <input type="text" class="capability-title-inp" data-idx="${idx}" value="${escH(row.title)}" placeholder="VD: Marketing Automation" />
            </label>
            <label class="clp-label" style="min-width:220px">Icon có sẵn
              <select class="capability-icon-inp" data-idx="${idx}">${_capabilityPresetOptions(row.icon)}</select>
            </label>
          </div>
          <label class="clp-label">Icon tùy chỉnh (URL — ưu tiên hơn icon có sẵn)
            <div class="clp-img-actions">
              <input type="text" class="capability-icon-url-inp" data-idx="${idx}" value="${escH(row.icon_url)}" placeholder="https://... hoặc /static/uploads/..." />
              <button type="button" class="btn clp-pick-btn capability-pick-btn" data-idx="${idx}">Chọn từ Media</button>
              <button type="button" class="btn clp-btn-sm capability-up-btn" data-idx="${idx}" title="Lên">↑</button>
              <button type="button" class="btn clp-btn-sm capability-down-btn" data-idx="${idx}" title="Xuống">↓</button>
              <button type="button" class="btn clp-btn-sm clp-btn-danger capability-del-btn" data-idx="${idx}">Xóa</button>
            </div>
          </label>
        </div>
      </div>
    </div>
  `).join('');

  list.querySelectorAll('.capability-title-inp').forEach(inp => {
    inp.addEventListener('input', () => {
      _capabilityRows[inp.dataset.idx].title = inp.value;
      syncCapabilitiesJsonField();
    });
  });
  list.querySelectorAll('.capability-icon-inp').forEach(sel => {
    sel.addEventListener('change', () => {
      _capabilityRows[sel.dataset.idx].icon = sel.value;
      syncCapabilitiesJsonField();
      _updateCapabilityIconPreview(list, sel.dataset.idx);
    });
  });
  list.querySelectorAll('.capability-icon-url-inp').forEach(inp => {
    inp.addEventListener('input', () => {
      _capabilityRows[inp.dataset.idx].icon_url = inp.value;
      syncCapabilitiesJsonField();
      _updateCapabilityIconPreview(list, inp.dataset.idx);
    });
  });
  list.querySelectorAll('.capability-pick-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const idx = parseInt(btn.dataset.idx, 10);
      openMediaPicker(url => {
        _capabilityRows[idx].icon_url = url;
        renderCapabilitiesEditor();
        syncCapabilitiesJsonField();
      });
    });
  });
  list.querySelectorAll('.capability-up-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const i = parseInt(btn.dataset.idx, 10);
      if (i <= 0) return;
      [_capabilityRows[i - 1], _capabilityRows[i]] = [_capabilityRows[i], _capabilityRows[i - 1]];
      renderCapabilitiesEditor();
      syncCapabilitiesJsonField();
    });
  });
  list.querySelectorAll('.capability-down-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const i = parseInt(btn.dataset.idx, 10);
      if (i >= _capabilityRows.length - 1) return;
      [_capabilityRows[i], _capabilityRows[i + 1]] = [_capabilityRows[i + 1], _capabilityRows[i]];
      renderCapabilitiesEditor();
      syncCapabilitiesJsonField();
    });
  });
  list.querySelectorAll('.capability-del-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      _capabilityRows.splice(parseInt(btn.dataset.idx, 10), 1);
      renderCapabilitiesEditor();
      syncCapabilitiesJsonField();
    });
  });
  syncCapabilitiesJsonField();
}

qs('#capability-add-btn')?.addEventListener('click', () => {
  _capabilityRows.push({
    title: '',
    icon: String(_capabilityRows.length % 6),
    icon_url: '',
  });
  renderCapabilitiesEditor();
});

// ── Hero Slides ───────────────────────────────────────────────────────────────

let _slides = [];

function renderSlides() {
  const list = qs('#hero-slides-list');
  if (!list) return;
  if (!_slides.length) {
    list.innerHTML = '<p class="muted">Chưa có slide nào. Nhấn <strong>+ Thêm slide</strong> để bắt đầu.</p>';
    return;
  }
  list.innerHTML = _slides.map((s, i) => `
    <div class="clp-slide-card" data-idx="${i}" style="display:flex;align-items:center;gap:.9rem;padding:.85rem 1rem;background:var(--panel-bg,#fff);border:1px solid var(--border,#e2e8f0);border-radius:8px;margin-bottom:.6rem">
      <span style="font-size:.8rem;font-weight:700;color:var(--muted,#64748b);min-width:1.4rem">${i + 1}</span>
      <div style="width:72px;height:48px;flex-shrink:0;border-radius:4px;overflow:hidden;background:#e2e8f0">
        ${s.image_url
          ? `<img src="${escH(s.image_url)}" style="width:100%;height:100%;object-fit:cover" alt="" loading="lazy" />`
          : `<div style="width:100%;height:100%;display:flex;align-items:center;justify-content:center;font-size:.7rem;color:#94a3b8">${s.video_url ? '▶ video' : 'No img'}</div>`}
      </div>
      <div style="flex:1;min-width:0">
        <div style="font-weight:600;font-size:.88rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${escH(s.heading || '(chưa có heading)')}</div>
        <div style="font-size:.75rem;color:var(--muted,#64748b);margin-top:.15rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${escH(s.kicker || '')}${s.image_url_mobile ? ' · 📱 mobile' : ''}</div>
      </div>
      <div style="display:flex;gap:.4rem;flex-shrink:0">
        ${i > 0 ? `<button type="button" class="btn clp-btn-icon slide-move-up" data-idx="${i}" title="Lên">↑</button>` : ''}
        ${i < _slides.length - 1 ? `<button type="button" class="btn clp-btn-icon slide-move-down" data-idx="${i}" title="Xuống">↓</button>` : ''}
        <button type="button" class="btn slide-edit" data-idx="${i}">Sửa</button>
        <button type="button" class="btn clp-btn-danger slide-delete" data-idx="${i}" title="Xóa">✕</button>
      </div>
    </div>
  `).join('');

  list.querySelectorAll('.slide-edit').forEach(btn =>
    btn.addEventListener('click', () => openSlideModal(parseInt(btn.dataset.idx, 10)))
  );
  list.querySelectorAll('.slide-delete').forEach(btn => {
    btn.addEventListener('click', async () => {
      if (!confirm('Xóa slide này?')) return;
      _slides.splice(parseInt(btn.dataset.idx, 10), 1);
      await _saveSlides();
      renderSlides();
    });
  });
  list.querySelectorAll('.slide-move-up').forEach(btn => {
    btn.addEventListener('click', async () => {
      const i = parseInt(btn.dataset.idx, 10);
      [_slides[i-1], _slides[i]] = [_slides[i], _slides[i-1]];
      await _saveSlides();
      renderSlides();
    });
  });
  list.querySelectorAll('.slide-move-down').forEach(btn => {
    btn.addEventListener('click', async () => {
      const i = parseInt(btn.dataset.idx, 10);
      [_slides[i], _slides[i+1]] = [_slides[i+1], _slides[i]];
      await _saveSlides();
      renderSlides();
    });
  });
}

async function _saveSlides() {
  const msg = qs('#hero-save-msg');
  try {
    await apiFetch('/api/settings', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ hero_slides_json: JSON.stringify(_slides) }),
    });
    showMsg(msg, '✓ Đã lưu');
  } catch (err) {
    showMsg(msg, '✗ ' + err.message, true);
    throw err;
  }
}

async function loadHeroSlides() {
  try {
    const data = await apiFetch('/api/settings');
    const raw = data.hero_slides_json;
    _slides = raw ? JSON.parse(raw) : [];
  } catch (e) {
    _slides = [];
  }
  renderSlides();
}

// ── Slide modal ───────────────────────────────────────────────────────────────

function openSlideModal(idx) {
  const s = idx === null ? null : _slides[idx];
  qs('#slide-modal-title').textContent = s ? `Sửa slide ${idx + 1}` : 'Thêm slide mới';
  qs('#slide-edit-idx').value = idx === null ? '' : String(idx);

  const imgUrl = s?.image_url || '';
  const mobileUrl = s?.image_url_mobile || '';
  qs('#slide-image-url').value = imgUrl;
  qs('#slide-image-mobile-url').value = mobileUrl;
  _updateSlideImagePreview({ url: imgUrl, thumbId: 'slide-desktop-thumb', previewId: 'slide-desktop-preview' });
  _updateSlideImagePreview({ url: mobileUrl, thumbId: 'slide-mobile-thumb', previewId: 'slide-mobile-preview' });
  const desktopStatus = qs('#slide-upload-desktop-status');
  const mobileStatus = qs('#slide-upload-mobile-status');
  if (desktopStatus) { desktopStatus.textContent = ''; desktopStatus.style.color = '#64748b'; }
  if (mobileStatus) { mobileStatus.textContent = ''; mobileStatus.style.color = '#64748b'; }

  qs('#slide-video-url').value = s?.video_url || '';
  if (qs('#slide-alt-text')) qs('#slide-alt-text').value = s?.alt_text || '';
  qs('#slide-kicker').value = s?.kicker || '';
  qs('#slide-heading').value = s?.heading || '';
  qs('#slide-lead').value = s?.lead || '';
  qs('#slide-cta-p-label').value = s?.cta_primary_label || '';
  qs('#slide-cta-p-href').value = s?.cta_primary_href || '#contact';
  qs('#slide-cta-g-label').value = s?.cta_ghost_label || '';
  qs('#slide-cta-g-href').value = s?.cta_ghost_href || '';
  qs('#slide-modal-msg').textContent = '';
  qs('#slide-modal').classList.remove('is-hidden');
  qs('#slide-heading').focus();
}

function closeSlideModal() {
  qs('#slide-modal').classList.add('is-hidden');
}

function _updateSlideImagePreview({ url, thumbId, previewId }) {
  const thumb = qs(`#${thumbId}`);
  const prev = qs(`#${previewId}`);
  if (!thumb || !prev) return;
  if (url) {
    prev.src = url;
    thumb.classList.remove('is-hidden');
  } else {
    prev.src = '';
    thumb.classList.add('is-hidden');
  }
}

function _wireSlideImageField({
  urlInputId, fileInputId, uploadBtnId, pickBtnId, statusId, thumbId, previewId, purpose,
}) {
  const urlInput = qs(`#${urlInputId}`);
  urlInput?.addEventListener('input', () => {
    _updateSlideImagePreview({
      url: urlInput.value.trim(),
      thumbId,
      previewId,
    });
  });

  qs(`#${uploadBtnId}`)?.addEventListener('click', () => {
    qs(`#${fileInputId}`)?.click();
  });

  qs(`#${fileInputId}`)?.addEventListener('change', async () => {
    const inp = qs(`#${fileInputId}`);
    if (!inp?.files?.length) return;
    const file = inp.files[0];
    const status = qs(`#${statusId}`);
    if (status) {
      status.textContent = 'Đang upload...';
      status.style.color = '#64748b';
    }
    try {
      const j = await uploadMediaFile(file, purpose);
      if (!j.url) throw new Error('Upload thất bại — không có URL');
      if (urlInput) urlInput.value = j.url;
      _updateSlideImagePreview({ url: j.url, thumbId, previewId });
      if (status) status.textContent = `✓ Đã crop & upload (${formatUploadStatus(j)})`;
    } catch (e) {
      if (status) {
        status.textContent = '✗ ' + e.message;
        status.style.color = '#dc2626';
      }
    }
    inp.value = '';
  });

  qs(`#${pickBtnId}`)?.addEventListener('click', () => {
    openMediaPicker((url) => {
      if (urlInput) urlInput.value = url;
      _updateSlideImagePreview({ url, thumbId, previewId });
    }, purpose);
  });
}

_wireSlideImageField({
  urlInputId: 'slide-image-url',
  fileInputId: 'slide-upload-desktop-input',
  uploadBtnId: 'slide-upload-desktop-btn',
  pickBtnId: 'slide-pick-desktop-btn',
  statusId: 'slide-upload-desktop-status',
  thumbId: 'slide-desktop-thumb',
  previewId: 'slide-desktop-preview',
  purpose: 'hero_desktop',
});

_wireSlideImageField({
  urlInputId: 'slide-image-mobile-url',
  fileInputId: 'slide-upload-mobile-input',
  uploadBtnId: 'slide-upload-mobile-btn',
  pickBtnId: 'slide-pick-mobile-btn',
  statusId: 'slide-upload-mobile-status',
  thumbId: 'slide-mobile-thumb',
  previewId: 'slide-mobile-preview',
  purpose: 'hero_mobile',
});

qs('#slide-video-upload-btn')?.addEventListener('click', () => {
  qs('#slide-video-upload-input')?.click();
});

qs('#slide-video-upload-input')?.addEventListener('change', async () => {
  const inp = qs('#slide-video-upload-input');
  if (!inp?.files?.length) return;
  const file = inp.files[0];
  const status = qs('#slide-video-upload-status');
  const maxBytes = 80 * 1024 * 1024;
  if (status) {
    status.textContent = 'Đang upload & tối ưu video...';
    status.style.color = '#64748b';
  }
  if (file.size > maxBytes) {
    if (status) {
      status.textContent = '✗ Video quá lớn (tối đa 80 MB)';
      status.style.color = '#dc2626';
    }
    inp.value = '';
    return;
  }
  try {
    const j = await uploadMediaFile(file, 'hero_video');
    qs('#slide-video-url').value = j.url;
    if (status) status.textContent = `✓ Đã upload video (${formatUploadStatus(j)})`;
  } catch (e) {
    if (status) { status.textContent = '✗ ' + e.message; status.style.color = '#dc2626'; }
  }
  inp.value = '';
});

qs('#slide-modal-close')?.addEventListener('click', closeSlideModal);
qs('#slide-modal-cancel')?.addEventListener('click', closeSlideModal);
qs('#slide-modal-backdrop')?.addEventListener('click', closeSlideModal);
document.addEventListener('keydown', e => { if (e.key === 'Escape') closeSlideModal(); });

qs('#slide-modal-save')?.addEventListener('click', async () => {
  const msg = qs('#slide-modal-msg');
  const heading = qs('#slide-heading').value.trim();
  const slide = {
    image_url: qs('#slide-image-url').value.trim(),
    image_url_mobile: qs('#slide-image-mobile-url')?.value.trim() || '',
    video_url: qs('#slide-video-url').value.trim(),
    alt_text: qs('#slide-alt-text')?.value.trim() || '',
    kicker: qs('#slide-kicker').value.trim(),
    heading,
    lead: qs('#slide-lead').value.trim(),
    cta_primary_label: qs('#slide-cta-p-label').value.trim(),
    cta_primary_href: qs('#slide-cta-p-href').value.trim() || '#contact',
    cta_ghost_label: qs('#slide-cta-g-label').value.trim(),
    cta_ghost_href: qs('#slide-cta-g-href').value.trim(),
  };
  const rawIdx = qs('#slide-edit-idx').value;
  if (rawIdx === '') {
    _slides.push(slide);
  } else {
    _slides[parseInt(rawIdx, 10)] = slide;
  }
  try {
    await _saveSlides();
    closeSlideModal();
    renderSlides();
  } catch (_) { /* error shown by _saveSlides */ }
});

qs('#hero-add-slide')?.addEventListener('click', () => openSlideModal(null));

// ── Projects ─────────────────────────────────────────────────────────────────

let _editProjectId = null;

function bindImgPreview(urlInputId, previewId, placeholderId) {
  const inp = qs(`#${urlInputId}`);
  const prev = qs(`#${previewId}`);
  const ph = qs(`#${placeholderId}`);
  if (!inp) return;
  inp.addEventListener('input', () => {
    if (inp.value.trim()) {
      if (prev) { prev.src = inp.value; prev.classList.remove('is-hidden'); }
      if (ph) ph.classList.add('is-hidden');
    } else {
      if (prev) { prev.src = ''; prev.classList.add('is-hidden'); }
      if (ph) ph.classList.remove('is-hidden');
    }
  });
}
bindImgPreview('project-image-url','project-img-preview','project-img-placeholder');
bindImgPreview('blog-image-url','blog-img-preview','blog-img-placeholder');

// ── Quill custom blots ────────────────────────────────────────────────────────

(function _registerQuillBlots() {
  if (typeof Quill === 'undefined') return;
  const BlockEmbed = Quill.import('blots/block/embed');
  class VideoFileBlot extends BlockEmbed {
    static create(url) {
      const node = super.create();
      node.setAttribute('src', url);
      node.setAttribute('controls', '');
      node.setAttribute('style', 'max-width:100%;border-radius:4px;display:block;margin:.5rem 0');
      return node;
    }
    static value(node) { return node.getAttribute('src'); }
  }
  VideoFileBlot.blotName = 'video-file';
  VideoFileBlot.tagName = 'video';
  try { Quill.register(VideoFileBlot); } catch (e) { /* already registered */ }
})();

async function _quillUploadFile(file) {
  return uploadMediaFile(file, null);
}

let _projectQuill = null;

function _initProjectQuill() {
  if (_projectQuill) return;
  const el = qs('#project-description-editor');
  if (!el || typeof Quill === 'undefined') return;
  _projectQuill = new Quill(el, {
    theme: 'snow',
    placeholder: 'Nội dung đầy đủ: bối cảnh, giải pháp, kết quả... (chỉ hiển thị trên trang chi tiết dự án)',
    modules: {
      toolbar: {
        container: [
          [{ header: [2, 3, false] }],
          ['bold', 'italic', 'underline', 'strike'],
          [{ list: 'ordered' }, { list: 'bullet' }, 'blockquote'],
          ['link', 'image', 'video'],
          ['clean'],
        ],
        handlers: {
          image() {
            const inp = document.createElement('input');
            inp.type = 'file';
            inp.accept = 'image/jpeg,image/png,image/webp,image/gif';
            inp.onchange = async () => {
              const file = inp.files[0];
              if (!file) return;
              try {
                const j = await _quillUploadFile(file);
                const range = _projectQuill.getSelection(true);
                _projectQuill.insertEmbed(range.index, 'image', j.url);
                _projectQuill.setSelection(range.index + 1);
              } catch (e) { alert('Lỗi upload ảnh: ' + e.message); }
            };
            inp.click();
          },
          video() {
            const inp = document.createElement('input');
            inp.type = 'file';
            inp.accept = 'video/mp4,video/webm,video/quicktime';
            inp.onchange = async () => {
              const file = inp.files[0];
              if (!file) return;
              try {
                const j = await _quillUploadFile(file);
                const range = _projectQuill.getSelection(true);
                _projectQuill.insertEmbed(range.index, 'video-file', j.url);
                _projectQuill.setSelection(range.index + 1);
              } catch (e) { alert('Lỗi upload video: ' + e.message); }
            };
            inp.click();
          },
        },
      },
    },
  });
}

function resetProjectForm() {
  _editProjectId = null;
  qs('#project-form-title').textContent = 'Thêm dự án mới';
  qs('#project-submit').textContent = 'Thêm dự án';
  qs('#project-cancel').classList.add('is-hidden');
  ['project-edit-id','project-image-url','project-title','project-category','project-intro'].forEach(id => {
    const el = qs(`#${id}`);
    if (el) el.value = '';
  });
  if (_projectQuill) _projectQuill.setContents([]);
  const prev = qs('#project-img-preview');
  if (prev) { prev.src = ''; prev.classList.add('is-hidden'); }
  const ph = qs('#project-img-placeholder');
  if (ph) ph.classList.remove('is-hidden');
}

async function loadProjects() {
  const list = qs('#projects-list');
  if (!list) return;
  try {
    const items = await apiFetch('/api/projects');
    if (!items.length) { list.innerHTML = '<p class="muted">Chưa có dự án nào.</p>'; return; }
    list.innerHTML = items.map(p => {
      const excerpt = stripHtml(p.intro || p.description || '');
      return `
      <div class="clp-item-card" data-id="${p.id}">
        <div class="clp-item-thumb">${imgOrPlaceholder(p.image_url)}</div>
        <div class="clp-item-info">
          <strong>${escH(p.title)}</strong>
          <span class="clp-item-sub">${escH(p.category)}</span>
          <p class="clp-item-desc">${escH(excerpt)}</p>
        </div>
        <div class="clp-item-actions">
          <button class="btn clp-btn-sm project-edit" data-id="${p.id}">Sửa</button>
          <button class="btn clp-btn-sm clp-btn-danger project-delete" data-id="${p.id}">Xóa</button>
        </div>
      </div>
    `;
    }).join('');

    list.querySelectorAll('.project-edit').forEach(btn => {
      btn.addEventListener('click', () => editProject(items.find(p => p.id == btn.dataset.id)));
    });
    list.querySelectorAll('.project-delete').forEach(btn => {
      btn.addEventListener('click', () => deleteProject(parseInt(btn.dataset.id,10)));
    });
  } catch (e) {
    list.innerHTML = `<p class="muted is-error">${escH(e.message)}</p>`;
  }
}

function editProject(p) {
  _editProjectId = p.id;
  qs('#project-form-title').textContent = 'Sửa dự án';
  qs('#project-submit').textContent = 'Lưu thay đổi';
  qs('#project-cancel').classList.remove('is-hidden');
  qs('#project-edit-id').value = p.id;
  qs('#project-image-url').value = p.image_url || '';
  qs('#project-title').value = p.title || '';
  qs('#project-category').value = p.category || '';
  qs('#project-intro').value = p.intro || '';
  if (_projectQuill) _projectQuill.root.innerHTML = p.description || '';
  const prev = qs('#project-img-preview');
  const ph = qs('#project-img-placeholder');
  if (p.image_url) {
    if (prev) { prev.src = p.image_url; prev.classList.remove('is-hidden'); }
    if (ph) ph.classList.add('is-hidden');
  } else {
    if (prev) { prev.src = ''; prev.classList.add('is-hidden'); }
    if (ph) ph.classList.remove('is-hidden');
  }
  qs('#project-title').scrollIntoView({ behavior: 'smooth', block: 'center' });
}

qs('#project-cancel')?.addEventListener('click', resetProjectForm);

qs('#project-submit')?.addEventListener('click', async () => {
  const msg = qs('#project-msg');
  const title = qs('#project-title')?.value.trim();
  const category = qs('#project-category')?.value.trim();
  const image_url = qs('#project-image-url')?.value.trim();
  const intro = qs('#project-intro')?.value.trim();
  const description = _projectQuill ? _projectQuill.root.innerHTML.trim() : '';
  if (!title || !category || !intro) { showMsg(msg,'✗ Điền đủ tên, danh mục và intro', true); return; }
  const body = { title, category, image_url: image_url || '', intro, description: description || '' };
  try {
    if (_editProjectId) {
      await apiFetch(`/api/projects/${_editProjectId}`, { method:'PUT', headers:{'Content-Type':'application/json'}, body: JSON.stringify(body) });
      showMsg(msg, '✓ Đã cập nhật dự án');
    } else {
      await apiFetch('/api/projects', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(body) });
      showMsg(msg, '✓ Đã thêm dự án');
    }
    resetProjectForm();
    await loadProjects();
  } catch (e) {
    showMsg(msg,'✗ ' + e.message, true);
  }
});

async function deleteProject(id) {
  if (!confirm('Xóa dự án này?')) return;
  try {
    await apiFetch(`/api/projects/${id}`, { method: 'DELETE' });
    await loadProjects();
  } catch (e) {
    alert('Lỗi: ' + e.message);
  }
}

// ── Blog / News ───────────────────────────────────────────────────────────────

let _blogQuill = null;

function _initBlogQuill() {
  if (_blogQuill) return;
  const el = qs('#blog-summary-editor');
  if (!el || typeof Quill === 'undefined') return;
  _blogQuill = new Quill(el, {
    theme: 'snow',
    placeholder: 'Nội dung tóm tắt hiển thị trên landing...',
    modules: {
      toolbar: {
        container: [
          [{ header: [2, 3, false] }],
          ['bold', 'italic', 'underline', 'strike'],
          [{ list: 'ordered' }, { list: 'bullet' }, 'blockquote'],
          ['link', 'image', 'video'],
          ['clean'],
        ],
        handlers: {
          image() {
            const inp = document.createElement('input');
            inp.type = 'file';
            inp.accept = 'image/jpeg,image/png,image/webp,image/gif';
            inp.onchange = async () => {
              const file = inp.files[0];
              if (!file) return;
              try {
                const j = await _quillUploadFile(file);
                const range = _blogQuill.getSelection(true);
                _blogQuill.insertEmbed(range.index, 'image', j.url);
                _blogQuill.setSelection(range.index + 1);
              } catch (e) { alert('Lỗi upload ảnh: ' + e.message); }
            };
            inp.click();
          },
          video() {
            const inp = document.createElement('input');
            inp.type = 'file';
            inp.accept = 'video/mp4,video/webm,video/quicktime';
            inp.onchange = async () => {
              const file = inp.files[0];
              if (!file) return;
              try {
                const j = await _quillUploadFile(file);
                const range = _blogQuill.getSelection(true);
                _blogQuill.insertEmbed(range.index, 'video-file', j.url);
                _blogQuill.setSelection(range.index + 1);
              } catch (e) { alert('Lỗi upload video: ' + e.message); }
            };
            inp.click();
          },
        },
      },
    },
  });
}

let _editBlogId = null;

function resetBlogForm() {
  _editBlogId = null;
  qs('#blog-form-title').textContent = 'Thêm bài viết mới';
  qs('#blog-submit').textContent = 'Thêm bài viết';
  qs('#blog-cancel').classList.add('is-hidden');
  ['blog-edit-id','blog-image-url','blog-title','blog-url'].forEach(id => {
    const el = qs(`#${id}`);
    if (el) el.value = '';
  });
  if (_blogQuill) _blogQuill.setContents([]);
  const dp = qs('#blog-published-at');
  if (dp) dp.value = new Date().toISOString().slice(0,10);
  const prev = qs('#blog-img-preview');
  if (prev) { prev.src = ''; prev.classList.add('is-hidden'); }
  const ph = qs('#blog-img-placeholder');
  if (ph) ph.classList.remove('is-hidden');
}

async function loadBlog() {
  const list = qs('#blog-list');
  if (!list) return;
  try {
    const items = await apiFetch('/api/news');
    if (!items.length) { list.innerHTML = '<p class="muted">Chưa có bài viết nào.</p>'; return; }
    list.innerHTML = items.map(n => {
      const excerpt = excerptHtml(n.summary);
      return `
      <div class="clp-item-card" data-id="${n.id}">
        <div class="clp-item-thumb">${imgOrPlaceholder(n.image_url)}</div>
        <div class="clp-item-info">
          <strong>${escH(n.title)}</strong>
          <span class="clp-item-sub">${escH(n.published_at || '')}</span>
          <p class="clp-item-desc">${escH(excerpt)}</p>
        </div>
        <div class="clp-item-actions">
          <button class="btn clp-btn-sm blog-edit" data-id="${n.id}">Sửa</button>
          <button class="btn clp-btn-sm clp-btn-danger blog-delete" data-id="${n.id}">Xóa</button>
        </div>
      </div>
    `;
    }).join('');

    list.querySelectorAll('.blog-edit').forEach(btn => {
      btn.addEventListener('click', () => editBlog(items.find(n => n.id == btn.dataset.id)));
    });
    list.querySelectorAll('.blog-delete').forEach(btn => {
      btn.addEventListener('click', () => deleteBlog(parseInt(btn.dataset.id,10)));
    });
  } catch (e) {
    list.innerHTML = `<p class="muted is-error">${escH(e.message)}</p>`;
  }
}

function editBlog(n) {
  _editBlogId = n.id;
  qs('#blog-form-title').textContent = 'Sửa bài viết';
  qs('#blog-submit').textContent = 'Lưu thay đổi';
  qs('#blog-cancel').classList.remove('is-hidden');
  qs('#blog-image-url').value = n.image_url || '';
  qs('#blog-title').value = n.title || '';
  if (_blogQuill) _blogQuill.root.innerHTML = n.summary || '';
  qs('#blog-url').value = n.url || '';
  qs('#blog-published-at').value = n.published_at || '';
  const prev = qs('#blog-img-preview');
  const ph = qs('#blog-img-placeholder');
  if (n.image_url) {
    if (prev) { prev.src = n.image_url; prev.classList.remove('is-hidden'); }
    if (ph) ph.classList.add('is-hidden');
  } else {
    if (prev) { prev.src = ''; prev.classList.add('is-hidden'); }
    if (ph) ph.classList.remove('is-hidden');
  }
  qs('#blog-title').scrollIntoView({ behavior: 'smooth', block: 'center' });
}

qs('#blog-cancel')?.addEventListener('click', resetBlogForm);

qs('#blog-submit')?.addEventListener('click', async () => {
  const msg = qs('#blog-msg');
  const title = qs('#blog-title')?.value.trim();
  const summary = _blogQuill ? _blogQuill.root.innerHTML.trim() : '';
  const url = qs('#blog-url')?.value.trim();
  const image_url = qs('#blog-image-url')?.value.trim();
  const published_at = qs('#blog-published-at')?.value || new Date().toISOString().slice(0,10);
  const summaryText = _blogQuill ? _blogQuill.getText().trim() : summary;
  if (!title || !summaryText) { showMsg(msg,'✗ Điền đủ tiêu đề và tóm tắt', true); return; }
  const body = { title, summary, url: url || '#', image_url: image_url || '', published_at };
  try {
    if (_editBlogId) {
      await apiFetch(`/api/news/${_editBlogId}`, { method:'PUT', headers:{'Content-Type':'application/json'}, body: JSON.stringify(body) });
      showMsg(msg, '✓ Đã cập nhật bài viết');
    } else {
      await apiFetch('/api/news', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(body) });
      showMsg(msg, '✓ Đã thêm bài viết');
    }
    resetBlogForm();
    await loadBlog();
  } catch (e) {
    showMsg(msg,'✗ ' + e.message, true);
  }
});

async function deleteBlog(id) {
  if (!confirm('Xóa bài viết này?')) return;
  try {
    await apiFetch(`/api/news/${id}`, { method: 'DELETE' });
    await loadBlog();
  } catch (e) {
    alert('Lỗi: ' + e.message);
  }
}

// ── Media Library ─────────────────────────────────────────────────────────────

let _mediaItems = [];

async function loadMedia() {
  const grid = qs('#media-grid');
  if (!grid) return;
  grid.innerHTML = '<p class="muted">Đang tải...</p>';
  try {
    _mediaItems = await apiFetch('/api/cms/media');
    renderMediaGrid(grid, _mediaItems, false);
  } catch (e) {
    grid.innerHTML = `<p class="muted is-error">${escH(e.message)}</p>`;
  }
}

function renderMediaGrid(grid, items, pickerMode, onPick) {
  if (!items.length) {
    grid.innerHTML = '<p class="muted">Chưa có ảnh nào trong thư viện.</p>';
    return;
  }
  grid.innerHTML = items.map(f => `
    <div class="clp-media-item" data-url="${escH(f.url)}" data-filename="${escH(f.filename)}">
      <div class="clp-media-thumb">
        <img src="${escH(f.url)}" alt="${escH(f.filename)}" loading="lazy" />
      </div>
      <div class="clp-media-info">
        <span class="clp-media-name" title="${escH(f.filename)}">${escH(f.filename.slice(0,20))}${f.filename.length>20?'…':''}</span>
        <span class="clp-media-size">${fmtSize(f.size)}</span>
      </div>
      ${pickerMode
        ? `<button type="button" class="btn clp-btn-sm media-pick-use">Dùng ảnh này</button>`
        : `<div class="clp-media-overlay">
            <button type="button" class="btn clp-btn-sm media-copy-url" data-url="${escH(f.url)}">Copy URL</button>
            <button type="button" class="btn clp-btn-sm clp-btn-danger media-delete" data-filename="${escH(f.filename)}">Xóa</button>
          </div>`
      }
    </div>
  `).join('');

  if (pickerMode) {
    grid.querySelectorAll('.media-pick-use').forEach(btn => {
      btn.addEventListener('click', () => {
        const url = btn.closest('.clp-media-item').dataset.url;
        if (onPick) onPick(url);
      });
    });
  } else {
    grid.querySelectorAll('.media-copy-url').forEach(btn => {
      btn.addEventListener('click', async () => {
        await navigator.clipboard.writeText(window.location.origin + btn.dataset.url).catch(() => {});
        const orig = btn.textContent;
        btn.textContent = '✓ Đã copy';
        setTimeout(() => { btn.textContent = orig; }, 2000);
      });
    });
    grid.querySelectorAll('.media-delete').forEach(btn => {
      btn.addEventListener('click', async () => {
        if (!confirm('Xóa ảnh này?')) return;
        try {
          await apiFetch(`/api/cms/media/${encodeURIComponent(btn.dataset.filename)}`, { method: 'DELETE' });
          await loadMedia();
        } catch (e) {
          alert('Lỗi: ' + e.message);
        }
      });
    });
  }
}

async function uploadFiles(files, onDone, purpose) {
  const prog = qs('#media-upload-progress');
  const fill = qs('#media-progress-fill');
  const status = qs('#media-upload-status');
  if (prog) prog.classList.remove('is-hidden');
  let done = 0;
  for (const file of files) {
    try {
      if (status) status.textContent = `Đang tải: ${file.name}`;
      await uploadMediaFile(file, purpose || null);
      done++;
      if (fill) fill.style.width = `${(done/files.length)*100}%`;
    } catch (e) {
      alert(`Lỗi upload ${file.name}: ${e.message}`);
    }
  }
  if (prog) prog.classList.add('is-hidden');
  if (fill) fill.style.width = '0';
  if (onDone) onDone();
}

// Upload zone
const uploadZone = qs('#media-upload-zone');
const fileInput = qs('#media-file-input');
const browseBtn = qs('#media-browse-btn');

browseBtn?.addEventListener('click', () => fileInput?.click());
fileInput?.addEventListener('change', async () => {
  if (!fileInput.files.length) return;
  await uploadFiles(Array.from(fileInput.files), loadMedia);
  fileInput.value = '';
});

uploadZone?.addEventListener('dragover', (e) => { e.preventDefault(); uploadZone.classList.add('is-drag-over'); });
uploadZone?.addEventListener('dragleave', () => uploadZone.classList.remove('is-drag-over'));
uploadZone?.addEventListener('drop', async (e) => {
  e.preventDefault();
  uploadZone.classList.remove('is-drag-over');
  const files = Array.from(e.dataTransfer.files).filter(f => f.type.startsWith('image/'));
  if (!files.length) return;
  await uploadFiles(files, loadMedia);
});

// ── Media Picker Modal ────────────────────────────────────────────────────────

let _pickerCallback = null;
let _pickerPurpose = null;

const PICK_TARGET_PURPOSE = {
  'project-image-url': 'project',
  'blog-image-url': 'news',
};

function openMediaPicker(cb, purpose) {
  _pickerCallback = cb;
  _pickerPurpose = purpose || null;
  const modal = qs('#media-picker-modal');
  if (modal) modal.classList.remove('is-hidden');
  loadPickerMedia();
}

function closeMediaPicker() {
  qs('#media-picker-modal')?.classList.add('is-hidden');
  _pickerCallback = null;
  _pickerPurpose = null;
}

async function loadPickerMedia() {
  const grid = qs('#media-picker-grid');
  if (!grid) return;
  grid.innerHTML = '<p class="muted">Đang tải...</p>';
  try {
    const items = await apiFetch('/api/cms/media');
    renderMediaGrid(grid, items, true, (url) => {
      if (_pickerCallback) _pickerCallback(url);
      closeMediaPicker();
    });
  } catch (e) {
    grid.innerHTML = `<p class="muted is-error">${escH(e.message)}</p>`;
  }
}

qs('#media-picker-close')?.addEventListener('click', closeMediaPicker);
qs('#media-picker-backdrop')?.addEventListener('click', closeMediaPicker);

// Modal upload
const modalFileInput = qs('#modal-file-input');
qs('#modal-upload-btn')?.addEventListener('click', () => modalFileInput?.click());
modalFileInput?.addEventListener('change', async () => {
  if (!modalFileInput.files.length) return;
  await uploadFiles(Array.from(modalFileInput.files), loadPickerMedia, _pickerPurpose);
  modalFileInput.value = '';
});

// Generic "Chọn từ Media" buttons (non-hero)
qsa('.clp-pick-btn:not([data-slide-idx])').forEach(btn => {
  btn.addEventListener('click', () => {
    const targetId = btn.dataset.pickTarget;
    const previewId = btn.dataset.preview;
    const phId = btn.dataset.placeholder;
    openMediaPicker((url) => {
      const inp = qs(`#${targetId}`);
      if (inp) {
        inp.value = url;
        inp.dispatchEvent(new Event('input'));
      }
      const prev = qs(`#${previewId}`);
      const ph = qs(`#${phId}`);
      if (prev) { prev.src = url; prev.classList.remove('is-hidden'); }
      if (ph) ph.classList.add('is-hidden');
    }, PICK_TARGET_PURPOSE[targetId] || null);
  });
});

// ── Preview ───────────────────────────────────────────────────────────────────

const _previewOverlay = () => qs('#preview-overlay');
const _previewIframe  = () => qs('#preview-iframe');
let _previewOpen = false;
let _previewLoaded = false;

function openPreview() {
  const overlay = _previewOverlay();
  if (!overlay) return;
  overlay.hidden = false;
  document.body.style.overflow = 'hidden';
  _previewOpen = true;
  // Lazy-load iframe on first open
  if (!_previewLoaded) {
    const iframe = _previewIframe();
    const loading = qs('#preview-loading');
    if (iframe) {
      iframe.addEventListener('load', () => {
        if (loading) loading.classList.add('is-hidden');
        iframe.classList.add('is-loaded');
      }, { once: false });
      iframe.src = '/';
      _previewLoaded = true;
    }
  }
}

function closePreview() {
  const overlay = _previewOverlay();
  if (!overlay) return;
  overlay.hidden = true;
  document.body.style.overflow = '';
  _previewOpen = false;
}

function refreshPreview() {
  const iframe = _previewIframe();
  const loading = qs('#preview-loading');
  if (!iframe) return;
  if (loading) loading.classList.remove('is-hidden');
  iframe.classList.remove('is-loaded');
  // Cache-bust with timestamp
  iframe.src = '/?_pv=' + Date.now();
  qs('#preview-stale-badge')?.classList.add('is-hidden');
}

// Device switching
const DEVICE_WIDTHS = { desktop: null, tablet: '768px', mobile: '390px' };

function setPreviewDevice(device) {
  qsa('.clp-dev-btn').forEach(b => b.classList.toggle('is-active', b.dataset.device === device));
  const wrap = qs('#preview-frame-wrap');
  if (wrap) wrap.dataset.device = device;
}

qs('#preview-open-btn')?.addEventListener('click', openPreview);
qs('#preview-close-btn')?.addEventListener('click', closePreview);
qs('#preview-refresh-btn')?.addEventListener('click', refreshPreview);

qsa('.clp-dev-btn').forEach(btn => {
  btn.addEventListener('click', () => setPreviewDevice(btn.dataset.device));
});

// Keyboard: Esc to close, F5 to refresh
document.addEventListener('keydown', (e) => {
  if (!_previewOpen) return;
  if (e.key === 'Escape') closePreview();
  if (e.key === 'F5') { e.preventDefault(); refreshPreview(); }
});

// ── Services ──────────────────────────────────────────────────────────────────

let _services = [];

function overviewToHtml(ov) {
  if (!ov) return '';
  if (Array.isArray(ov)) {
    return ov.map(p => {
      const s = String(p).trim();
      if (!s) return '';
      return s.startsWith('<') ? s : `<p>${escH(s)}</p>`;
    }).join('');
  }
  const s = String(ov).trim();
  if (!s) return '';
  return s.startsWith('<') ? s : `<p>${escH(s)}</p>`;
}

// Quill instance registry — cleared each time renderServices() re-renders
const _quillInstances = new Map();

function slugify(str) {
  return str
    .normalize('NFD').replace(/[̀-ͯ]/g, '')
    .replace(/đ/g,'d').replace(/Đ/g,'D')
    .toLowerCase()
    .replace(/[^a-z0-9\s-]/g,'')
    .trim().replace(/\s+/g,'-')
    .replace(/-+/g,'-');
}

function _initQuillAt(ci, ii) {
  const key = `${ci}-${ii}`;
  if (_quillInstances.has(key)) return _quillInstances.get(key);
  const el = qs(`#svc-overview-editor-${ci}-${ii}`);
  if (!el) return null;
  const quill = new Quill(el, {
    theme: 'snow',
    placeholder: 'Mô tả chi tiết dịch vụ...',
    modules: {
      toolbar: [
        [{ header: [2, 3, false] }],
        ['bold', 'italic', 'underline'],
        [{ list: 'ordered' }, { list: 'bullet' }],
        ['link', 'clean'],
      ],
    },
  });
  const html = overviewToHtml((_services[ci]?.items||[])[ii]?.overview);
  if (html) quill.root.innerHTML = html;
  _quillInstances.set(key, quill);
  return quill;
}

function renderServices() {
  const list = qs('#svc-categories-list');
  if (!list) return;
  _quillInstances.clear();
  if (!_services.length) {
    list.innerHTML = '<p class="muted">Chưa có danh mục nào.</p>';
    return;
  }
  list.innerHTML = _services.map((cat, ci) => `
    <div class="clp-svc-cat" data-ci="${ci}">
      <div class="clp-svc-cat-head">
        <div class="clp-svc-cat-title-row">
          <span class="clp-svc-cat-drag">⠿</span>
          <input type="text" class="svc-cat-title" value="${escH(cat.title||'')}" data-ci="${ci}" placeholder="Tên danh mục..." />
        </div>
        <div class="clp-svc-cat-actions">
          ${ci > 0 ? `<button type="button" class="btn clp-btn-icon svc-cat-up" data-ci="${ci}" title="Lên">↑</button>` : ''}
          ${ci < _services.length-1 ? `<button type="button" class="btn clp-btn-icon svc-cat-down" data-ci="${ci}" title="Xuống">↓</button>` : ''}
          <button type="button" class="btn clp-btn-icon clp-btn-danger svc-cat-del" data-ci="${ci}" title="Xóa danh mục">✕</button>
        </div>
      </div>

      <div class="clp-svc-items">
        ${(cat.items||[]).map((item, ii) => `
          <div class="clp-svc-item" data-ci="${ci}" data-ii="${ii}" id="svc-item-${ci}-${ii}">
            <div class="clp-svc-item-head">
              <strong class="clp-svc-item-name">${escH(item.name||'(chưa đặt tên)')}</strong>
              <span class="clp-svc-item-slug muted">${escH(item.slug||'')}</span>
              <div class="clp-svc-item-btns">
                <button type="button" class="btn clp-btn-sm svc-item-edit" data-ci="${ci}" data-ii="${ii}">Sửa</button>
                <button type="button" class="btn clp-btn-sm clp-btn-danger svc-item-del" data-ci="${ci}" data-ii="${ii}">Xóa</button>
              </div>
            </div>
            <div class="clp-svc-item-form is-hidden" id="svc-item-form-${ci}-${ii}">
              <div class="clp-form-row">
                <label class="clp-label">Tên dịch vụ (H1 hero) <span class="req">*</span>
                  <input type="text" class="svc-item-name-inp" value="${escH(item.name||'')}" data-ci="${ci}" data-ii="${ii}" placeholder="Dịch vụ chạy quảng cáo Google..." />
                </label>
                <label class="clp-label">Slug (URL) <span class="req">*</span>
                  <input type="text" class="svc-item-slug-inp" value="${escH(item.slug||'')}" data-ci="${ci}" data-ii="${ii}" placeholder="quang-cao-google" />
                </label>
              </div>

              <fieldset class="clp-fieldset clp-svc-hero-fieldset">
                <legend>Hero đầu trang</legend>
                <p class="muted" style="margin:0 0 .75rem;font-size:.85rem">Ảnh nền, dòng nhãn, mô tả và nút CTA ở đầu trang /services/${escH(item.slug||'…')}.</p>
                <label class="clp-label">Dòng nhãn trên (eyebrow)
                  <input type="text" class="svc-item-hero-eyebrow-inp" value="${escH(item.hero_eyebrow||'')}" data-ci="${ci}" data-ii="${ii}" placeholder="Dịch vụ · Quảng cáo kỹ thuật số (để trống = tự điền theo danh mục)" />
                </label>
                <div class="clp-image-field">
                  <label class="clp-label">Ảnh nền hero</label>
                  <div class="clp-img-preview-wrap" id="svc-item-img-wrap-${ci}-${ii}">
                    ${item.image_url
                      ? `<img src="${escH(item.image_url)}" class="clp-img-preview" alt="" />`
                      : `<span class="clp-img-placeholder">Chưa có ảnh — hero dùng nền mặc định</span>`}
                  </div>
                  <div class="clp-img-actions">
                    <input type="text" class="svc-item-img-inp" value="${escH(item.image_url||'')}" data-ci="${ci}" data-ii="${ii}" placeholder="Dán URL hoặc upload ảnh..." />
                    <input type="file" class="svc-item-upload-input is-hidden" data-ci="${ci}" data-ii="${ii}" accept="image/jpeg,image/png,image/webp,image/gif" />
                    <button type="button" class="btn svc-item-upload-img" data-ci="${ci}" data-ii="${ii}">⬆ Upload</button>
                    <button type="button" class="btn svc-item-pick-img" data-ci="${ci}" data-ii="${ii}">Thư viện</button>
                  </div>
                </div>
                <label class="clp-label">Tagline (dòng phụ dưới tiêu đề)
                  <input type="text" class="svc-item-tagline-inp" value="${escH(item.tagline||'')}" data-ci="${ci}" data-ii="${ii}" placeholder="Tìm kiếm, hiển thị, Performance Max..." />
                </label>
                <label class="clp-label">Mô tả ngắn (đoạn lead hero) <span class="req">*</span>
                  <textarea class="svc-item-summary-inp" rows="3" data-ci="${ci}" data-ii="${ii}" placeholder="Tìm kiếm, hiển thị, Performance Max và mạng lưới lớn...">${escH(item.summary||'')}</textarea>
                </label>
                <div class="clp-form-row">
                  <label class="clp-label">Nút CTA chính
                    <input type="text" class="svc-item-hero-cta-inp" value="${escH(item.hero_cta_primary_label||'')}" data-ci="${ci}" data-ii="${ii}" placeholder="Nhận đề xuất" />
                  </label>
                  <label class="clp-label">Nút gọi điện (nhãn hiển thị)
                    <input type="text" class="svc-item-hero-phone-inp" value="${escH(item.hero_cta_phone_label||'')}" data-ci="${ci}" data-ii="${ii}" placeholder="Để trống = SĐT trong cài đặt liên hệ" />
                  </label>
                </div>
              </fieldset>

              <div class="clp-label">
                <span class="clp-label-text">Nội dung chi tiết — mục "Tổng quan dịch vụ"</span>
                <div class="clp-quill-wrap">
                  <div id="svc-overview-editor-${ci}-${ii}" class="svc-overview-quill"></div>
                </div>
              </div>
              <label class="clp-label">Điểm nổi bật / Hạng mục bàn giao (mỗi dòng 1 điểm)
                <textarea class="svc-item-highlights-inp" rows="4" data-ci="${ci}" data-ii="${ii}" placeholder="Điểm 1&#10;Điểm 2&#10;Điểm 3">${escH((item.highlights||[]).join('\n'))}</textarea>
              </label>
              <fieldset class="clp-fieldset">
                <legend>Báo giá (sidebar)</legend>
                <div class="clp-form-row">
                  <label class="clp-label">Nhãn giá
                    <input type="text" class="svc-item-price-label-inp" value="${escH(item.price_label||'')}" data-ci="${ci}" data-ii="${ii}" placeholder="VD: Từ 15.000.000đ / tháng" />
                  </label>
                </div>
                <label class="clp-label">Ghi chú báo giá
                  <textarea class="svc-item-price-note-inp" rows="2" data-ci="${ci}" data-ii="${ii}" placeholder="Giá phụ thuộc quy mô, kênh và thời gian triển khai...">${escH(item.price_note||'')}</textarea>
                </label>
              </fieldset>
              <div class="clp-form-actions">
                <button type="button" class="btn btn-primary svc-item-save" data-ci="${ci}" data-ii="${ii}">Lưu dịch vụ này</button>
                <button type="button" class="btn clp-btn-cancel svc-item-close" data-ci="${ci}" data-ii="${ii}">Đóng</button>
              </div>
            </div>
          </div>
        `).join('')}
      </div>

      <div class="clp-svc-add-item-row">
        <button type="button" class="btn clp-btn-sm svc-add-item-btn" data-ci="${ci}">+ Thêm dịch vụ vào danh mục này</button>
      </div>
    </div>
  `).join('');

  // Category title input
  list.querySelectorAll('.svc-cat-title').forEach(inp => {
    inp.addEventListener('input', () => {
      _services[inp.dataset.ci].title = inp.value;
    });
  });

  // Category move up/down/delete
  list.querySelectorAll('.svc-cat-up').forEach(btn => {
    btn.addEventListener('click', () => {
      const i = parseInt(btn.dataset.ci,10);
      [_services[i-1],_services[i]] = [_services[i],_services[i-1]];
      renderServices();
    });
  });
  list.querySelectorAll('.svc-cat-down').forEach(btn => {
    btn.addEventListener('click', () => {
      const i = parseInt(btn.dataset.ci,10);
      [_services[i],_services[i+1]] = [_services[i+1],_services[i]];
      renderServices();
    });
  });
  list.querySelectorAll('.svc-cat-del').forEach(btn => {
    btn.addEventListener('click', () => {
      const i = parseInt(btn.dataset.ci,10);
      const cat = _services[i];
      if (!confirm(`Xóa danh mục "${cat.title}" và tất cả ${(cat.items||[]).length} dịch vụ bên trong?`)) return;
      _services.splice(i,1);
      renderServices();
    });
  });

  // Item edit toggle — initialize Quill when opening
  list.querySelectorAll('.svc-item-edit').forEach(btn => {
    btn.addEventListener('click', () => {
      const ci = parseInt(btn.dataset.ci, 10);
      const ii = parseInt(btn.dataset.ii, 10);
      const form = qs(`#svc-item-form-${ci}-${ii}`);
      const opening = form?.classList.contains('is-hidden');
      form?.classList.toggle('is-hidden');
      if (opening) _initQuillAt(ci, ii);
    });
  });
  list.querySelectorAll('.svc-item-close').forEach(btn => {
    btn.addEventListener('click', () => {
      qs(`#svc-item-form-${btn.dataset.ci}-${btn.dataset.ii}`)?.classList.add('is-hidden');
    });
  });

  // Item delete
  list.querySelectorAll('.svc-item-del').forEach(btn => {
    btn.addEventListener('click', () => {
      const ci = parseInt(btn.dataset.ci,10);
      const ii = parseInt(btn.dataset.ii,10);
      const item = _services[ci].items[ii];
      if (!confirm(`Xóa dịch vụ "${item.name}"?`)) return;
      _services[ci].items.splice(ii,1);
      renderServices();
    });
  });

  // Service image picker
  list.querySelectorAll('.svc-item-pick-img').forEach(btn => {
    btn.addEventListener('click', () => {
      const ci = parseInt(btn.dataset.ci, 10);
      const ii = parseInt(btn.dataset.ii, 10);
      openMediaPicker((url) => {
        const form = qs(`#svc-item-form-${ci}-${ii}`);
        const inp = form?.querySelector('.svc-item-img-inp');
        if (inp) { inp.value = url; inp.dispatchEvent(new Event('input')); }
      });
    });
  });
  list.querySelectorAll('.svc-item-upload-img').forEach(btn => {
    btn.addEventListener('click', () => {
      const ci = btn.dataset.ci;
      const ii = btn.dataset.ii;
      const fileInp = list.querySelector(`.svc-item-upload-input[data-ci="${ci}"][data-ii="${ii}"]`);
      fileInp?.click();
    });
  });
  list.querySelectorAll('.svc-item-upload-input').forEach(inp => {
    inp.addEventListener('change', async () => {
      if (!inp.files?.length) return;
      const ci = inp.dataset.ci;
      const ii = inp.dataset.ii;
      try {
        const j = await uploadMediaFile(inp.files[0], 'service');
        const form = qs(`#svc-item-form-${ci}-${ii}`);
        const urlInp = form?.querySelector('.svc-item-img-inp');
        if (urlInp) { urlInp.value = j.url; urlInp.dispatchEvent(new Event('input')); }
      } catch (e) {
        alert('Upload thất bại: ' + e.message);
      }
      inp.value = '';
    });
  });
  list.querySelectorAll('.svc-item-img-inp').forEach(inp => {
    inp.addEventListener('input', () => {
      const ci = parseInt(inp.dataset.ci, 10);
      const ii = parseInt(inp.dataset.ii, 10);
      const wrap = qs(`#svc-item-img-wrap-${ci}-${ii}`);
      if (!wrap) return;
      wrap.innerHTML = inp.value
        ? `<img src="${escH(inp.value)}" class="clp-img-preview" alt="" />`
        : `<span class="clp-img-placeholder">Chưa có ảnh</span>`;
    });
  });

  // Item name → auto-slug
  list.querySelectorAll('.svc-item-name-inp').forEach(inp => {
    inp.addEventListener('input', () => {
      const ci = parseInt(inp.dataset.ci,10);
      const ii = parseInt(inp.dataset.ii,10);
      const slugInp = qs(`#svc-item-form-${ci}-${ii} .svc-item-slug-inp`);
      if (slugInp && !slugInp.dataset.manual) {
        slugInp.value = slugify(inp.value);
      }
    });
  });
  list.querySelectorAll('.svc-item-slug-inp').forEach(inp => {
    inp.addEventListener('input', () => { inp.dataset.manual = '1'; });
  });

  // Item save
  list.querySelectorAll('.svc-item-save').forEach(btn => {
    btn.addEventListener('click', () => {
      const ci = parseInt(btn.dataset.ci,10);
      const ii = parseInt(btn.dataset.ii,10);
      const form = qs(`#svc-item-form-${ci}-${ii}`);
      const name = form.querySelector('.svc-item-name-inp')?.value.trim();
      const slug = form.querySelector('.svc-item-slug-inp')?.value.trim();
      const image_url = form.querySelector('.svc-item-img-inp')?.value.trim() || '';
      const hero_eyebrow = form.querySelector('.svc-item-hero-eyebrow-inp')?.value.trim() || '';
      const tagline = form.querySelector('.svc-item-tagline-inp')?.value.trim() || '';
      const summary = form.querySelector('.svc-item-summary-inp')?.value.trim() || '';
      const hero_cta_primary_label = form.querySelector('.svc-item-hero-cta-inp')?.value.trim() || '';
      const hero_cta_phone_label = form.querySelector('.svc-item-hero-phone-inp')?.value.trim() || '';
      const quill = _quillInstances.get(`${ci}-${ii}`);
      const overviewHtml = quill ? quill.root.innerHTML.trim() : '';
      const overview = (overviewHtml && overviewHtml !== '<p><br></p>') ? overviewHtml : '';
      const highlightsRaw = form.querySelector('.svc-item-highlights-inp')?.value || '';
      const highlights = highlightsRaw.split('\n').map(l=>l.trim()).filter(Boolean);
      const price_label = form.querySelector('.svc-item-price-label-inp')?.value.trim() || '';
      const price_note = form.querySelector('.svc-item-price-note-inp')?.value.trim() || '';
      if (!name || !slug) { alert('Điền tên và slug trước khi lưu.'); return; }
      _services[ci].items[ii] = {
        ...(_services[ci].items[ii]||{}),
        name, slug, image_url, hero_eyebrow, tagline, summary,
        hero_cta_primary_label, hero_cta_phone_label,
        overview: overview || (_services[ci].items[ii]?.overview || ''),
        highlights, price_label, price_note,
      };
      renderServices();
    });
  });

  // Add item to category
  list.querySelectorAll('.svc-add-item-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const ci = parseInt(btn.dataset.ci,10);
      if (!_services[ci].items) _services[ci].items = [];
      _services[ci].items.push({ name:'', slug:'', summary:'', highlights:[] });
      renderServices();
      // Auto-open form của item mới
      const ii = _services[ci].items.length - 1;
      qs(`#svc-item-form-${ci}-${ii}`)?.classList.remove('is-hidden');
      qs(`#svc-item-form-${ci}-${ii} .svc-item-name-inp`)?.focus();
    });
  });
}

async function loadServices() {
  try {
    _services = await apiFetch('/api/services');
    renderServices();
  } catch (e) {
    const list = qs('#svc-categories-list');
    if (list) list.innerHTML = `<p class="muted is-error">${escH(e.message)}</p>`;
  }
}

qs('#svc-add-cat-btn')?.addEventListener('click', () => {
  const inp = qs('#svc-new-cat-name');
  const name = inp?.value.trim();
  if (!name) { inp?.focus(); return; }
  _services.push({ title: name, items: [] });
  if (inp) inp.value = '';
  renderServices();
  // Scroll to new category
  const cats = qsa('.clp-svc-cat');
  cats[cats.length-1]?.scrollIntoView({ behavior:'smooth', block:'nearest' });
});

qs('#svc-save-btn')?.addEventListener('click', async () => {
  const msg = qs('#svc-save-msg');
  try {
    await apiFetch('/api/services', {
      method: 'PUT',
      headers: { 'Content-Type':'application/json' },
      body: JSON.stringify(_services),
    });
    showMsg(msg, '✓ Đã lưu danh sách dịch vụ');
  } catch (e) {
    showMsg(msg, '✗ ' + e.message, true);
  }
});

// ── Init ──────────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
  loadSettings();
  loadHeroSlides();
  // Set default date
  const dp = qs('#blog-published-at');
  if (dp && !dp.value) dp.value = new Date().toISOString().slice(0,10);
  // Đọc ?tab= từ URL để auto-activate tab
  const urlTab = new URLSearchParams(window.location.search).get('tab');
  if (urlTab && TABS.includes(urlTab)) activateTab(urlTab);
});
