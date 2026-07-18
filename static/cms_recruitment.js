/* CMS Tuyển dụng — quản lý recruitment_jobs */
'use strict';

function qs(sel) { return document.querySelector(sel); }
function escH(s) { return String(s ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }
function showMsg(el, txt, err) {
  if (!el) return;
  el.textContent = txt;
  el.style.color = err ? '#dc2626' : '#166534';
  setTimeout(() => { if (el.textContent === txt) el.textContent = ''; }, 3500);
}

async function apiFetch(url, opts) {
  const r = await fetch(url, opts);
  if (!r.ok) {
    const j = await r.json().catch(() => ({}));
    throw new Error(j.error || `HTTP ${r.status}`);
  }
  return r.status === 204 ? null : r.json();
}

// ── List rendering ────────────────────────────────────────────────────────────

let _jobs = [];

function renderJobs() {
  const el = qs('#rec-jobs-list');
  if (!el) return;
  if (!_jobs.length) {
    el.innerHTML = '<p class="muted">Chưa có vị trí nào. Nhấn <strong>+ Thêm vị trí</strong> để bắt đầu.</p>';
    return;
  }
  el.innerHTML = _jobs.map((j, idx) => `
    <div class="rec-job-card">
      <div class="rec-job-card-head">
        <span class="rec-job-num">${idx + 1}</span>
        <div class="rec-job-title-wrap">
          <div>${escH(j.title)}</div>
          <div style="font-size:.78rem;color:var(--muted,#64748b);margin-top:.15rem">${escH(j.location || '')}${j.location && j.employment_type ? ' · ' : ''}${escH(j.employment_type || '')}</div>
        </div>
        <span class="rec-job-badge ${j.is_active ? 'active' : 'inactive'}">${j.is_active ? 'Hiển thị' : 'Ẩn'}</span>
        <div class="rec-list-actions">
          ${idx > 0 ? `<button class="btn clp-btn-icon" data-move-up="${j.id}" title="Lên">↑</button>` : ''}
          ${idx < _jobs.length - 1 ? `<button class="btn clp-btn-icon" data-move-down="${j.id}" title="Xuống">↓</button>` : ''}
          <button class="btn" data-edit="${j.id}">Sửa</button>
          <button class="btn clp-btn-danger" data-delete="${j.id}">Xóa</button>
        </div>
      </div>
      ${j.description ? `<p style="font-size:.82rem;color:var(--muted,#64748b);margin:0">${escH(j.description)}</p>` : ''}
    </div>
  `).join('');

  el.querySelectorAll('[data-edit]').forEach(btn =>
    btn.addEventListener('click', () => openModal(_jobs.find(j => j.id === +btn.dataset.edit)))
  );
  el.querySelectorAll('[data-delete]').forEach(btn =>
    btn.addEventListener('click', () => deleteJob(+btn.dataset.delete))
  );
  el.querySelectorAll('[data-move-up]').forEach(btn =>
    btn.addEventListener('click', () => moveJob(+btn.dataset.moveUp, -1))
  );
  el.querySelectorAll('[data-move-down]').forEach(btn =>
    btn.addEventListener('click', () => moveJob(+btn.dataset.moveDown, 1))
  );
}

async function loadJobs() {
  try {
    _jobs = await apiFetch('/api/cms/recruitment');
  } catch (e) {
    _jobs = [];
    const el = qs('#rec-jobs-list');
    if (el) el.innerHTML = `<p style="color:#dc2626">Lỗi: ${escH(e.message)}</p>`;
    return;
  }
  renderJobs();
}

// ── Move (reorder via sort_order) ─────────────────────────────────────────────

async function moveJob(id, dir) {
  const idx = _jobs.findIndex(j => j.id === id);
  const other = _jobs[idx + dir];
  if (!other) return;
  try {
    await Promise.all([
      apiFetch(`/api/cms/recruitment/${id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ sort_order: other.sort_order }),
      }),
      apiFetch(`/api/cms/recruitment/${other.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ sort_order: _jobs[idx].sort_order }),
      }),
    ]);
    await loadJobs();
  } catch (e) {
    alert('Lỗi thay đổi thứ tự: ' + e.message);
  }
}

// ── Delete ────────────────────────────────────────────────────────────────────

async function deleteJob(id) {
  const job = _jobs.find(j => j.id === id);
  if (!confirm(`Xóa vị trí "${job?.title}"?`)) return;
  try {
    await apiFetch(`/api/cms/recruitment/${id}`, { method: 'DELETE' });
    await loadJobs();
  } catch (e) {
    alert('Lỗi xóa: ' + e.message);
  }
}

// ── List editor (trách nhiệm / yêu cầu / quyền lợi) ──────────────────────────

function renderListEditor(containerId, items) {
  const el = qs(`#${containerId}`);
  if (!el) return;
  el.innerHTML = (items || []).map((item, i) => `
    <div class="rec-list-editor-row">
      <input type="text" value="${escH(item)}" data-list-idx="${i}" />
      <button type="button" class="btn clp-btn-danger clp-btn-icon" data-remove-idx="${i}">✕</button>
    </div>
  `).join('');
  el.querySelectorAll('[data-remove-idx]').forEach(btn => {
    btn.addEventListener('click', () => {
      const key = containerId.replace('rec-', '').replace('-editor', '');
      const arr = getListValues(key);
      arr.splice(+btn.dataset.removeIdx, 1);
      renderListEditor(containerId, arr);
    });
  });
}

function getListValues(key) {
  const el = qs(`#rec-${key}-editor`);
  if (!el) return [];
  return Array.from(el.querySelectorAll('input[data-list-idx]')).map(i => i.value);
}

document.addEventListener('click', e => {
  const btn = e.target.closest('.rec-list-add');
  if (!btn) return;
  const key = btn.dataset.list;
  const arr = getListValues(key);
  arr.push('');
  renderListEditor(`rec-${key}-editor`, arr);
  const inputs = qs(`#rec-${key}-editor`)?.querySelectorAll('input');
  inputs?.[inputs.length - 1]?.focus();
});

// ── Modal ─────────────────────────────────────────────────────────────────────

function openModal(job) {
  qs('#rec-modal-title').textContent = job ? 'Sửa vị trí' : 'Thêm vị trí';
  qs('#rec-edit-id').value = job?.id ?? '';
  qs('#rec-title').value = job?.title ?? '';
  qs('#rec-slug').value = job?.slug ?? '';
  qs('#rec-employment-type').value = job?.employment_type ?? 'Toàn thời gian';
  qs('#rec-location').value = job?.location ?? '';
  qs('#rec-description').value = job?.description ?? '';
  qs('#rec-intro').value = job?.intro ?? '';
  qs('#rec-is-active').checked = job ? !!job.is_active : true;
  renderListEditor('rec-responsibilities-editor', job?.responsibilities ?? []);
  renderListEditor('rec-requirements-editor', job?.requirements ?? []);
  renderListEditor('rec-benefits-editor', job?.benefits ?? []);
  qs('#rec-modal-msg').textContent = '';
  qs('#rec-modal').classList.remove('is-hidden');
  qs('#rec-title').focus();
}

function closeModal() {
  qs('#rec-modal').classList.add('is-hidden');
}

// Auto-slug from title
qs('#rec-title')?.addEventListener('input', () => {
  if (qs('#rec-edit-id').value) return; // don't change slug when editing
  const slug = qs('#rec-title').value
    .toLowerCase()
    .normalize('NFD').replace(/[̀-ͯ]/g, '')
    .replace(/đ/g, 'd').replace(/[^a-z0-9\s-]/g, '')
    .trim().replace(/\s+/g, '-');
  qs('#rec-slug').value = slug;
});

qs('#rec-modal-close')?.addEventListener('click', closeModal);
qs('#rec-modal-cancel')?.addEventListener('click', closeModal);
qs('#rec-modal-backdrop')?.addEventListener('click', closeModal);
document.addEventListener('keydown', e => { if (e.key === 'Escape') closeModal(); });

qs('#rec-modal-save')?.addEventListener('click', async () => {
  const msg = qs('#rec-modal-msg');
  const id = qs('#rec-edit-id').value;
  const title = qs('#rec-title').value.trim();
  const slug = qs('#rec-slug').value.trim();
  if (!title || !slug) { showMsg(msg, 'Vui lòng điền Tiêu đề và Slug', true); return; }
  const payload = {
    title,
    slug,
    employment_type: qs('#rec-employment-type').value.trim(),
    location: qs('#rec-location').value.trim(),
    description: qs('#rec-description').value.trim(),
    intro: qs('#rec-intro').value.trim(),
    responsibilities: getListValues('responsibilities').filter(Boolean),
    requirements: getListValues('requirements').filter(Boolean),
    benefits: getListValues('benefits').filter(Boolean),
    is_active: qs('#rec-is-active').checked,
  };
  try {
    if (id) {
      await apiFetch(`/api/cms/recruitment/${id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
    } else {
      await apiFetch('/api/cms/recruitment', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
    }
    closeModal();
    await loadJobs();
  } catch (e) {
    showMsg(msg, '✗ ' + e.message, true);
  }
});

qs('#rec-add-btn')?.addEventListener('click', () => openModal(null));

// ── Init ──────────────────────────────────────────────────────────────────────
loadJobs();
