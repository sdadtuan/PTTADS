/** @file Add-on ngành trên lead (R6). */
(function (global) {
  "use strict";

  function createCrmLeadAddon(ctx) {
    const { $, esc, reqJson, getSelectedLead, setSelectedLead, onSaved } = ctx;

    function renderIndustryAddon(lead) {
      const panel = $("crm-leads-industry-addon-panel");
      const fieldsEl = $("crm-leads-industry-addon-fields");
      const titleEl = $("crm-leads-industry-addon-title");
      const hintEl = $("crm-leads-industry-addon-hint");
      const saveBtn = $("crm-leads-industry-addon-save");
      const errEl = $("crm-leads-industry-addon-err");
      if (!panel || !fieldsEl) return;
      if (errEl) {
        errEl.hidden = true;
        errEl.textContent = "";
      }
      const addon = lead?.industry_addon;
      if (!addon || !addon.has_pack || !addon.pack) {
        panel.hidden = false;
        if (titleEl) titleEl.textContent = "Add-on ngành";
        if (hintEl) {
          hintEl.textContent = addon?.industry_slug
            ? `Ngành ${esc(lead.industry_label || addon.industry_slug)} chưa có add-on.`
            : "Chọn ngành trên form Sửa lead để bật trường mở rộng.";
        }
        fieldsEl.innerHTML = "";
        if (saveBtn) saveBtn.hidden = true;
        return;
      }
      panel.hidden = false;
      const pack = addon.pack;
      if (titleEl) titleEl.textContent = pack.addon_label || "Add-on ngành";
      if (hintEl) {
        hintEl.textContent = `Ngành: ${esc(lead.industry_label || addon.industry_slug || "—")}`;
      }
      const data = addon.data || {};
      fieldsEl.innerHTML = (pack.fields || [])
        .map((f) => {
          const val = data[f.key] || "";
          if (f.type === "select") {
            const opts = (f.options || [])
              .map(
                (o) =>
                  `<option value="${esc(o.value)}"${val === o.value ? " selected" : ""}>${esc(o.label || o.value)}</option>`,
              )
              .join("");
            return `<label style="display:block;font-size:.8rem;margin:.35rem 0">${esc(f.label)}
            <select class="crm-leads-addon-field" data-addon-key="${esc(f.key)}" style="width:100%;margin-top:.2rem;">
              <option value="">—</option>${opts}
            </select></label>`;
          }
          return `<label style="display:block;font-size:.8rem;margin:.35rem 0">${esc(f.label)}
          <input type="text" class="crm-leads-addon-field" data-addon-key="${esc(f.key)}"
            value="${esc(val)}" style="width:100%;margin-top:.2rem;" /></label>`;
        })
        .join("");
      if (saveBtn) {
        saveBtn.hidden = false;
        saveBtn.onclick = () => saveIndustryAddon(lead.id).catch((e) => {
          if (errEl) {
            errEl.textContent = e.message;
            errEl.hidden = false;
          }
        });
      }
    }

    async function saveIndustryAddon(leadId) {
      const body = { data: {} };
      document.querySelectorAll(".crm-leads-addon-field").forEach((el) => {
        body.data[el.dataset.addonKey] = el.value;
      });
      const data = await reqJson(`/api/crm/leads/${leadId}/industry-addon`, {
        method: "PATCH",
        body: JSON.stringify(body),
      });
      const selectedLead = getSelectedLead();
      if (selectedLead && Number(selectedLead.id) === Number(leadId)) {
        setSelectedLead({ ...selectedLead, industry_addon: data });
        renderIndustryAddon(getSelectedLead());
        if (typeof onSaved === "function") onSaved(getSelectedLead());
      }
    }

    return { renderIndustryAddon, saveIndustryAddon };
  }

  global.createCrmLeadAddon = createCrmLeadAddon;
})(window);
