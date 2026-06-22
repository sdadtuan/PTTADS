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

function imgOrPlaceholder(url) {
  return url ? `<img src="${escH(url)}" class="clp-thumb" alt="" loading="lazy" />` : '<span class="clp-no-img">—</span>';
}

function escH(s) {
  return String(s || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
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
  if (name === 'projects') loadProjects();
  if (name === 'blog') loadBlog();
  if (name === 'services') loadServices();
}

qsa('.clp-tab').forEach(btn => {
  btn.addEventListener('click', () => activateTab(btn.dataset.tab));
});

// ── Settings loader ───────────────────────────────────────────────────────────

let _settings = {};

async function loadSettings() {
  try {
    _settings = await apiFetch('/api/settings');
    const form = qs('#content-form');
    if (!form) return;
    form.querySelectorAll('[name]').forEach(el => {
      const v = _settings[el.name];
      if (v !== undefined) el.value = v;
    });
  } catch (e) {
    console.warn('loadSettings:', e);
  }
}

qs('#content-form')?.addEventListener('submit', async (e) => {
  e.preventDefault();
  const msg = qs('#content-save-msg');
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

// ── Hero Slides ───────────────────────────────────────────────────────────────

let _slides = [];

function renderSlides() {
  const list = qs('#hero-slides-list');
  if (!list) return;
  if (!_slides.length) {
    list.innerHTML = '<p class="muted">Chưa có slide nào.</p>';
    return;
  }
  list.innerHTML = _slides.map((s, i) => `
    <div class="clp-slide-card" data-idx="${i}">
      <div class="clp-slide-num">${i + 1}</div>
      <div class="clp-slide-image-col">
        <div class="clp-img-preview-wrap">
          ${s.image_url
            ? `<img src="${escH(s.image_url)}" class="clp-img-preview" alt="" />`
            : `<span class="clp-img-placeholder">Chưa có ảnh</span>`}
        </div>
        <div class="clp-img-actions">
          <input type="text" class="slide-image-url" value="${escH(s.image_url || '')}" placeholder="URL ảnh..." data-idx="${i}" />
          <button type="button" class="btn clp-pick-btn" data-slide-idx="${i}">Media</button>
        </div>
      </div>
      <div class="clp-slide-fields">
        <label class="clp-label">Kicker (nhỏ trên heading)
          <input type="text" class="slide-kicker" value="${escH(s.kicker||'')}" placeholder="Creative Martech Platform..." data-idx="${i}" />
        </label>
        <label class="clp-label">Heading <span class="req">*</span>
          <input type="text" class="slide-heading" value="${escH(s.heading||'')}" placeholder="Tiêu đề lớn..." data-idx="${i}" />
        </label>
        <label class="clp-label">Mô tả ngắn
          <textarea class="slide-lead" rows="2" data-idx="${i}" placeholder="Mô tả dưới heading...">${escH(s.lead||'')}</textarea>
        </label>
        <div class="clp-form-row">
          <label class="clp-label">Nút chính — nhãn
            <input type="text" class="slide-cta-p-label" value="${escH(s.cta_primary_label||'')}" placeholder="Nhận tư vấn..." data-idx="${i}" />
          </label>
          <label class="clp-label">Nút chính — href
            <input type="text" class="slide-cta-p-href" value="${escH(s.cta_primary_href||'#contact')}" placeholder="#contact" data-idx="${i}" />
          </label>
        </div>
        <div class="clp-form-row">
          <label class="clp-label">Nút phụ — nhãn (tùy chọn)
            <input type="text" class="slide-cta-g-label" value="${escH(s.cta_ghost_label||'')}" placeholder="Xem case study" data-idx="${i}" />
          </label>
          <label class="clp-label">Nút phụ — href
            <input type="text" class="slide-cta-g-href" value="${escH(s.cta_ghost_href||'')}" placeholder="#projects" data-idx="${i}" />
          </label>
        </div>
      </div>
      <div class="clp-slide-actions">
        ${i > 0 ? `<button type="button" class="btn clp-btn-icon slide-move-up" data-idx="${i}" title="Lên">↑</button>` : ''}
        ${i < _slides.length - 1 ? `<button type="button" class="btn clp-btn-icon slide-move-down" data-idx="${i}" title="Xuống">↓</button>` : ''}
        <button type="button" class="btn clp-btn-danger slide-delete" data-idx="${i}" title="Xóa slide này">✕</button>
      </div>
    </div>
  `).join('');

  // Bind input changes → _slides
  list.querySelectorAll('input[data-idx], textarea[data-idx]').forEach(inp => {
    inp.addEventListener('input', () => {
      const idx = parseInt(inp.dataset.idx, 10);
      const field = inp.className.replace('slide-','').replace(/-(\w)/g, (_,c) => c.toUpperCase());
      const map = {
        'imageUrl': 'image_url',
        'kicker': 'kicker',
        'heading': 'heading',
        'lead': 'lead',
        'ctaPLabel': 'cta_primary_label',
        'ctaPHref': 'cta_primary_href',
        'ctaGLabel': 'cta_ghost_label',
        'ctaGHref': 'cta_ghost_href',
      };
      const key = inp.className.split(' ').find(c => c.startsWith('slide-'));
      const fieldMap = {
        'slide-image-url': 'image_url',
        'slide-kicker': 'kicker',
        'slide-heading': 'heading',
        'slide-lead': 'lead',
        'slide-cta-p-label': 'cta_primary_label',
        'slide-cta-p-href': 'cta_primary_href',
        'slide-cta-g-label': 'cta_ghost_label',
        'slide-cta-g-href': 'cta_ghost_href',
      };
      const sk = fieldMap[key];
      if (sk) _slides[idx][sk] = inp.value;
      // Update image preview inline
      if (sk === 'image_url') {
        const card = inp.closest('.clp-slide-card');
        const wrap = card?.querySelector('.clp-img-preview-wrap');
        if (wrap) {
          wrap.innerHTML = inp.value
            ? `<img src="${escH(inp.value)}" class="clp-img-preview" alt="" />`
            : `<span class="clp-img-placeholder">Chưa có ảnh</span>`;
        }
      }
    });
  });

  list.querySelectorAll('.slide-move-up').forEach(btn => {
    btn.addEventListener('click', () => {
      const i = parseInt(btn.dataset.idx, 10);
      [_slides[i-1], _slides[i]] = [_slides[i], _slides[i-1]];
      renderSlides();
    });
  });
  list.querySelectorAll('.slide-move-down').forEach(btn => {
    btn.addEventListener('click', () => {
      const i = parseInt(btn.dataset.idx, 10);
      [_slides[i], _slides[i+1]] = [_slides[i+1], _slides[i]];
      renderSlides();
    });
  });
  list.querySelectorAll('.slide-delete').forEach(btn => {
    btn.addEventListener('click', () => {
      if (!confirm('Xóa slide này?')) return;
      _slides.splice(parseInt(btn.dataset.idx, 10), 1);
      renderSlides();
    });
  });
  list.querySelectorAll('.clp-pick-btn[data-slide-idx]').forEach(btn => {
    btn.addEventListener('click', () => {
      openMediaPicker((url) => {
        const idx = parseInt(btn.dataset.slideIdx, 10);
        _slides[idx].image_url = url;
        renderSlides();
      });
    });
  });
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

qs('#hero-add-slide')?.addEventListener('click', () => {
  _slides.push({
    image_url: '',
    kicker: '',
    heading: '',
    lead: '',
    cta_primary_label: 'Liên hệ ngay',
    cta_primary_href: '#contact',
    cta_ghost_label: '',
    cta_ghost_href: '',
  });
  renderSlides();
});

qs('#hero-save')?.addEventListener('click', async () => {
  const msg = qs('#hero-save-msg');
  try {
    await apiFetch('/api/settings', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ hero_slides_json: JSON.stringify(_slides) }),
    });
    showMsg(msg, '✓ Đã lưu slides');
  } catch (err) {
    showMsg(msg, '✗ ' + err.message, true);
  }
});

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

function resetProjectForm() {
  _editProjectId = null;
  qs('#project-form-title').textContent = 'Thêm dự án mới';
  qs('#project-submit').textContent = 'Thêm dự án';
  qs('#project-cancel').classList.add('is-hidden');
  ['project-edit-id','project-image-url','project-title','project-category','project-description'].forEach(id => {
    const el = qs(`#${id}`);
    if (el) el.value = '';
  });
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
    list.innerHTML = items.map(p => `
      <div class="clp-item-card" data-id="${p.id}">
        <div class="clp-item-thumb">${imgOrPlaceholder(p.image_url)}</div>
        <div class="clp-item-info">
          <strong>${escH(p.title)}</strong>
          <span class="clp-item-sub">${escH(p.category)}</span>
          <p class="clp-item-desc">${escH(p.description)}</p>
        </div>
        <div class="clp-item-actions">
          <button class="btn clp-btn-sm project-edit" data-id="${p.id}">Sửa</button>
          <button class="btn clp-btn-sm clp-btn-danger project-delete" data-id="${p.id}">Xóa</button>
        </div>
      </div>
    `).join('');

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
  qs('#project-description').value = p.description || '';
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
  const description = qs('#project-description')?.value.trim();
  if (!title || !category) { showMsg(msg,'✗ Điền đủ tên và danh mục', true); return; }
  const body = { title, category, image_url: image_url || '', description: description || '' };
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

let _editBlogId = null;

function resetBlogForm() {
  _editBlogId = null;
  qs('#blog-form-title').textContent = 'Thêm bài viết mới';
  qs('#blog-submit').textContent = 'Thêm bài viết';
  qs('#blog-cancel').classList.add('is-hidden');
  ['blog-edit-id','blog-image-url','blog-title','blog-summary','blog-url'].forEach(id => {
    const el = qs(`#${id}`);
    if (el) el.value = '';
  });
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
    list.innerHTML = items.map(n => `
      <div class="clp-item-card" data-id="${n.id}">
        <div class="clp-item-thumb">${imgOrPlaceholder(n.image_url)}</div>
        <div class="clp-item-info">
          <strong>${escH(n.title)}</strong>
          <span class="clp-item-sub">${escH(n.published_at || '')}</span>
          <p class="clp-item-desc">${escH(n.summary)}</p>
        </div>
        <div class="clp-item-actions">
          <button class="btn clp-btn-sm blog-edit" data-id="${n.id}">Sửa</button>
          <button class="btn clp-btn-sm clp-btn-danger blog-delete" data-id="${n.id}">Xóa</button>
        </div>
      </div>
    `).join('');

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
  qs('#blog-summary').value = n.summary || '';
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
  const summary = qs('#blog-summary')?.value.trim();
  const url = qs('#blog-url')?.value.trim();
  const image_url = qs('#blog-image-url')?.value.trim();
  const published_at = qs('#blog-published-at')?.value || new Date().toISOString().slice(0,10);
  if (!title || !summary) { showMsg(msg,'✗ Điền đủ tiêu đề và tóm tắt', true); return; }
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

async function uploadFiles(files, onDone) {
  const prog = qs('#media-upload-progress');
  const fill = qs('#media-progress-fill');
  const status = qs('#media-upload-status');
  if (prog) prog.classList.remove('is-hidden');
  let done = 0;
  for (const file of files) {
    const fd = new FormData();
    fd.append('file', file);
    try {
      if (status) status.textContent = `Đang tải: ${file.name}`;
      await apiFetch('/api/cms/media/upload', { method: 'POST', body: fd });
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

function openMediaPicker(cb) {
  _pickerCallback = cb;
  const modal = qs('#media-picker-modal');
  if (modal) modal.classList.remove('is-hidden');
  loadPickerMedia();
}

function closeMediaPicker() {
  qs('#media-picker-modal')?.classList.add('is-hidden');
  _pickerCallback = null;
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
  await uploadFiles(Array.from(modalFileInput.files), loadPickerMedia);
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
    });
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
                <label class="clp-label">Tên dịch vụ <span class="req">*</span>
                  <input type="text" class="svc-item-name-inp" value="${escH(item.name||'')}" data-ci="${ci}" data-ii="${ii}" placeholder="Dịch vụ quảng cáo Facebook..." />
                </label>
                <label class="clp-label">Slug (URL) <span class="req">*</span>
                  <input type="text" class="svc-item-slug-inp" value="${escH(item.slug||'')}" data-ci="${ci}" data-ii="${ii}" placeholder="quang-cao-facebook" />
                </label>
              </div>
              <div class="clp-image-field">
                <label class="clp-label">Ảnh banner dịch vụ</label>
                <div class="clp-img-preview-wrap" id="svc-item-img-wrap-${ci}-${ii}">
                  ${item.image_url
                    ? `<img src="${escH(item.image_url)}" class="clp-img-preview" alt="" />`
                    : `<span class="clp-img-placeholder">Chưa có ảnh</span>`}
                </div>
                <div class="clp-img-actions">
                  <input type="text" class="svc-item-img-inp" value="${escH(item.image_url||'')}" data-ci="${ci}" data-ii="${ii}" placeholder="URL ảnh banner..." />
                  <button type="button" class="btn svc-item-pick-img" data-ci="${ci}" data-ii="${ii}">Chọn từ Media</button>
                </div>
              </div>
              <label class="clp-label">Tagline (hiển thị dưới tên, tùy chọn)
                <input type="text" class="svc-item-tagline-inp" value="${escH(item.tagline||'')}" data-ci="${ci}" data-ii="${ii}" placeholder="Tối ưu ngân sách · Đo lường minh bạch · Tăng trưởng bền vững" />
              </label>
              <label class="clp-label">Mô tả ngắn (summary) <span class="req">*</span>
                <textarea class="svc-item-summary-inp" rows="2" data-ci="${ci}" data-ii="${ii}" placeholder="Giải pháp giúp...">${escH(item.summary||'')}</textarea>
              </label>
              <div class="clp-label">
                <span class="clp-label-text">Mô tả chi tiết — hiển thị mục "Tổng quan dịch vụ"</span>
                <div class="clp-quill-wrap">
                  <div id="svc-overview-editor-${ci}-${ii}" class="svc-overview-quill"></div>
                </div>
              </div>
              <label class="clp-label">Điểm nổi bật / Hạng mục bàn giao (mỗi dòng 1 điểm)
                <textarea class="svc-item-highlights-inp" rows="4" data-ci="${ci}" data-ii="${ii}" placeholder="Điểm 1&#10;Điểm 2&#10;Điểm 3">${escH((item.highlights||[]).join('\n'))}</textarea>
              </label>
              <fieldset class="clp-fieldset">
                <legend>Báo giá</legend>
                <div class="clp-form-row">
                  <label class="clp-label">Nhãn giá (hiển thị trong sidebar trang dịch vụ)
                    <input type="text" class="svc-item-price-label-inp" value="${escH(item.price_label||'')}" data-ci="${ci}" data-ii="${ii}" placeholder="VD: Từ 15.000.000đ / tháng · hoặc Liên hệ theo dự án" />
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
      const tagline = form.querySelector('.svc-item-tagline-inp')?.value.trim() || '';
      const summary = form.querySelector('.svc-item-summary-inp')?.value.trim() || '';
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
        name, slug, image_url, tagline, summary,
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
