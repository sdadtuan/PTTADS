(function () {
  "use strict";

  const metaEl = document.getElementById("crm-catalog-meta");
  let meta = {};
  try {
    meta = JSON.parse(metaEl?.textContent || "{}");
  } catch {
    meta = {};
  }
  const canConfigure = !!meta.can_configure;
  let services = Array.isArray(meta.services) ? meta.services : [];
  let industries = Array.isArray(meta.industries) ? meta.industries : [];
  let assignScopes = Array.isArray(meta.assign_scopes) ? meta.assign_scopes : [];
  let staffList = Array.isArray(meta.staff) ? meta.staff : [];

  function $(id) {
    return document.getElementById(id);
  }

  function esc(s) {
    return String(s ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  async function reqJson(url, opts) {
    const r = await fetch(url, {
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      credentials: "same-origin",
      ...opts,
    });
    const d = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(d.error || r.statusText || "Lỗi");
    return d;
  }

  function showModal(id) {
    const el = $(id);
    if (el) el.hidden = false;
  }

  function hideModal(id) {
    const el = $(id);
    if (el) el.hidden = true;
  }

  function renderServices() {
    const tbody = $("crm-catalog-services-table")?.querySelector("tbody");
    if (!tbody) return;
    tbody.innerHTML = services
      .map((s) => {
        const editBtn = canConfigure
          ? `<button type="button" class="btn-link" data-edit-service="${s.id}">Sửa</button>`
          : "";
        return `<tr>
          <td><code>${esc(s.slug)}</code></td>
          <td>${esc(s.name)}</td>
          <td>${esc(s.sort_order)}</td>
          <td><span class="crm-catalog-badge ${s.active ? "is-active" : "is-inactive"}">${s.active ? "Hoạt động" : "Vô hiệu"}</span></td>
          <td>${editBtn}</td>
        </tr>`;
      })
      .join("");
  }

  function addonFieldCount(item) {
    const traits = item?.traits;
    if (!traits || typeof traits !== "object") return 0;
    return Array.isArray(traits.fields) ? traits.fields.length : 0;
  }

  function renderIndustries() {
    const tbody = $("crm-catalog-industries-table")?.querySelector("tbody");
    if (!tbody) return;
    tbody.innerHTML = industries
      .map((i) => {
        const fc = addonFieldCount(i);
        const editBtn = canConfigure
          ? `<button type="button" class="btn-link" data-edit-industry="${i.id}">Sửa</button>`
          : "";
        return `<tr>
          <td><code>${esc(i.slug)}</code></td>
          <td>${esc(i.name)}</td>
          <td>${fc ? `<span class="crm-catalog-addon-count">${fc} field</span>` : '<span class="muted">—</span>'}</td>
          <td>${esc(i.sort_order)}</td>
          <td><span class="crm-catalog-badge ${i.active ? "is-active" : "is-inactive"}">${i.active ? "Hoạt động" : "Vô hiệu"}</span></td>
          <td>${editBtn}</td>
        </tr>`;
      })
      .join("");
  }

  function renderAssignScopes() {
    const tbody = $("crm-assign-scopes-table")?.querySelector("tbody");
    if (!tbody) return;
    tbody.innerHTML = assignScopes
      .map((sc) => {
        const delBtn = canConfigure
          ? `<button type="button" class="btn-link" data-delete-scope="${sc.id}">Xóa</button>`
          : "";
        const toggleBtn = canConfigure
          ? `<button type="button" class="btn-link" data-toggle-scope="${sc.id}" data-active="${sc.active ? "0" : "1"}">${sc.active ? "Tắt" : "Bật"}</button>`
          : "";
        return `<tr>
          <td>${esc(sc.staff_name || sc.staff_id)}</td>
          <td><code>${esc(sc.industry_slug)}</code></td>
          <td><code>${esc(sc.service_slug)}</code></td>
          <td><span class="crm-catalog-badge ${sc.active ? "is-active" : "is-inactive"}">${sc.active ? "Hoạt động" : "Vô hiệu"}</span></td>
          <td>${toggleBtn} ${delBtn}</td>
        </tr>`;
      })
      .join("");
  }

  function fillAssignScopeSelects() {
    const staffEl = $("crm-assign-f-staff");
    if (staffEl) {
      staffEl.innerHTML = staffList
        .map((s) => `<option value="${s.id}">${esc(s.name)}</option>`)
        .join("");
    }
    const indEl = $("crm-assign-f-industry");
    if (indEl) {
      indEl.innerHTML =
        `<option value="*">* — mọi ngành</option>` +
        industries.map((i) => `<option value="${esc(i.slug)}">${esc(i.name)}</option>`).join("");
    }
    const svcEl = $("crm-assign-f-service");
    if (svcEl) {
      svcEl.innerHTML =
        `<option value="*">* — mọi dịch vụ</option>` +
        services.map((s) => `<option value="${esc(s.slug)}">${esc(s.name)}</option>`).join("");
    }
  }

  function openForm(kind, item) {
    const isEdit = !!item?.id;
    $("crm-catalog-form-kind").value = kind;
    $("crm-catalog-form-id").value = isEdit ? String(item.id) : "";
    $("crm-catalog-modal-title").textContent = isEdit
      ? kind === "service"
        ? "Sửa dịch vụ"
        : "Sửa ngành"
      : kind === "service"
        ? "Thêm dịch vụ"
        : "Thêm ngành";
    $("crm-catalog-slug-wrap").hidden = isEdit;
    $("crm-catalog-f-slug").value = item?.slug || "";
    $("crm-catalog-f-slug").disabled = isEdit;
    $("crm-catalog-f-name").value = item?.name || "";
    $("crm-catalog-f-desc").value = item?.description || "";
    $("crm-catalog-f-order").value = String(item?.sort_order ?? 0);
    $("crm-catalog-f-active").checked = item?.active !== false;
    const traitsWrap = $("crm-catalog-traits-wrap");
    const traitsEl = $("crm-catalog-f-traits");
    if (traitsWrap) traitsWrap.hidden = kind !== "industry";
    if (traitsEl) {
      const traits = item?.traits && typeof item.traits === "object" ? item.traits : {};
      traitsEl.value = Object.keys(traits).length ? JSON.stringify(traits, null, 2) : "";
    }
    $("crm-catalog-form-err").hidden = true;
    showModal("crm-catalog-modal");
  }

  async function reloadCatalog() {
    const [svc, ind] = await Promise.all([
      reqJson("/api/crm/catalog/services"),
      reqJson("/api/crm/catalog/industries"),
    ]);
    services = svc.services || [];
    industries = ind.industries || [];
    renderServices();
    renderIndustries();
    fillAssignScopeSelects();
  }

  async function reloadAssignScopes() {
    const data = await reqJson("/api/crm/assign-scopes");
    assignScopes = data.scopes || [];
    if (Array.isArray(data.staff) && data.staff.length) {
      staffList = data.staff;
    }
    renderAssignScopes();
    fillAssignScopeSelects();
  }

  $("crm-catalog-add-service")?.addEventListener("click", () => openForm("service", null));
  $("crm-catalog-add-industry")?.addEventListener("click", () => openForm("industry", null));
  $("crm-assign-add-scope")?.addEventListener("click", () => {
    fillAssignScopeSelects();
    $("crm-assign-scope-form-err").hidden = true;
    showModal("crm-assign-scope-modal");
  });

  $("crm-catalog-services-table")?.addEventListener("click", (ev) => {
    const id = ev.target.closest("[data-edit-service]")?.dataset.editService;
    if (!id) return;
    const item = services.find((s) => String(s.id) === String(id));
    if (item) openForm("service", item);
  });

  $("crm-catalog-industries-table")?.addEventListener("click", (ev) => {
    const id = ev.target.closest("[data-edit-industry]")?.dataset.editIndustry;
    if (!id) return;
    const item = industries.find((i) => String(i.id) === String(id));
    if (item) openForm("industry", item);
  });

  $("crm-assign-scopes-table")?.addEventListener("click", async (ev) => {
    const delId = ev.target.closest("[data-delete-scope]")?.dataset.deleteScope;
    const toggleEl = ev.target.closest("[data-toggle-scope]");
    try {
      if (delId) {
        await reqJson(`/api/crm/assign-scopes/${delId}`, { method: "DELETE" });
        await reloadAssignScopes();
      } else if (toggleEl) {
        const sid = toggleEl.dataset.toggleScope;
        const active = toggleEl.dataset.active === "1";
        await reqJson(`/api/crm/assign-scopes/${sid}`, {
          method: "PATCH",
          body: JSON.stringify({ active }),
        });
        await reloadAssignScopes();
      }
    } catch (e) {
      alert(e instanceof Error ? e.message : String(e));
    }
  });

  document.querySelectorAll("[data-close-catalog-modal]").forEach((el) => {
    el.addEventListener("click", () => hideModal("crm-catalog-modal"));
  });
  document.querySelectorAll("[data-close-assign-modal]").forEach((el) => {
    el.addEventListener("click", () => hideModal("crm-assign-scope-modal"));
  });

  $("crm-catalog-form")?.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const errEl = $("crm-catalog-form-err");
    errEl.hidden = true;
    const kind = $("crm-catalog-form-kind").value;
    const id = ($("crm-catalog-form-id").value || "").trim();
    const payload = {
      name: $("crm-catalog-f-name").value.trim(),
      description: $("crm-catalog-f-desc").value.trim(),
      sort_order: Number($("crm-catalog-f-order").value || 0),
      active: $("crm-catalog-f-active").checked,
    };
    if (kind === "industry") {
      const rawTraits = ($("crm-catalog-f-traits")?.value || "").trim();
      if (rawTraits) {
        try {
          payload.traits = JSON.parse(rawTraits);
        } catch {
          errEl.textContent = "Add-on pack JSON không hợp lệ.";
          errEl.hidden = false;
          return;
        }
      } else if (id) {
        payload.traits = {};
      }
    }
    try {
      if (id) {
        const url =
          kind === "service"
            ? `/api/crm/catalog/services/${id}`
            : `/api/crm/catalog/industries/${id}`;
        await reqJson(url, { method: "PATCH", body: JSON.stringify(payload) });
      } else {
        payload.slug = $("crm-catalog-f-slug").value.trim();
        const url =
          kind === "service" ? "/api/crm/catalog/services" : "/api/crm/catalog/industries";
        await reqJson(url, { method: "POST", body: JSON.stringify(payload) });
      }
      hideModal("crm-catalog-modal");
      await reloadCatalog();
    } catch (e) {
      errEl.textContent = e instanceof Error ? e.message : String(e);
      errEl.hidden = false;
    }
  });

  $("crm-assign-scope-form")?.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const errEl = $("crm-assign-scope-form-err");
    errEl.hidden = true;
    try {
      await reqJson("/api/crm/assign-scopes", {
        method: "POST",
        body: JSON.stringify({
          staff_id: Number($("crm-assign-f-staff").value),
          industry_slug: $("crm-assign-f-industry").value,
          service_slug: $("crm-assign-f-service").value,
        }),
      });
      hideModal("crm-assign-scope-modal");
      await reloadAssignScopes();
    } catch (e) {
      errEl.textContent = e instanceof Error ? e.message : String(e);
      errEl.hidden = false;
    }
  });

  renderServices();
  renderIndustries();
  renderAssignScopes();
  fillAssignScopeSelects();
})();
