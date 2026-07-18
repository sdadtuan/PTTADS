(function () {
  const ACTIONS = ["view", "edit", "create", "delete", "export", "configure"];

  function readBootstrap() {
    const el = document.getElementById("admin-grants-bootstrap");
    if (!el) return {};
    try {
      return JSON.parse(el.textContent || "{}");
    } catch (_e) {
      return {};
    }
  }

  const boot = readBootstrap();
  const cmsGrants = boot.cms_grants && typeof boot.cms_grants === "object" ? boot.cms_grants : {};
  const posGrants =
    boot.position_grants && typeof boot.position_grants === "object" ? boot.position_grants : {};
  const isSuper = !!boot.is_super_admin;
  const isFullAccess = !!boot.is_full_access || isSuper;
  const positionId = boot.position_id != null ? Number(boot.position_id) : null;
  const crmSectionIds = new Set(
    Array.isArray(boot.crm_section_ids) ? boot.crm_section_ids.map(String) : [],
  );
  const uiButtons =
    boot.ui_buttons && typeof boot.ui_buttons === "object" ? boot.ui_buttons : {};

  /** Portal nhân viên — không khóa UI phía client (backend vẫn kiểm tra). */
  function shouldSkipAllGating() {
    if (isFullAccess) return true;
    if (document.querySelector(".admin-app-layout--full-access")) return true;
    if (document.querySelector(".admin-app-main--staff")) return true;
    if (document.body.classList.contains("crm-app--staff-portal")) return true;
    if (document.body.classList.contains("crm-customers-page--staff")) return true;
    return false;
  }

  function cmsCan(moduleId, action) {
    const list = cmsGrants[moduleId] || [];
    return list.includes(action);
  }

  function posCan(sectionId, action) {
    const list = posGrants[sectionId] || [];
    return list.includes(action);
  }

  function btnCan(buttonId) {
    const bid = String(buttonId || "").trim();
    if (!bid) return true;
    const def = uiButtons[bid];
    if (!def) return true;
    const req = String(def.requires_action || "view").trim().toLowerCase();
    if (shouldSkipAllGating()) return true;
    if (Object.prototype.hasOwnProperty.call(posGrants, bid)) {
      return posCan(bid, req);
    }
    const parent = String(def.parent_section || "").trim();
    if (parent && crmSectionIds.has(parent)) {
      if (positionId == null || !Number.isFinite(positionId) || positionId <= 0) return true;
      return posCan(parent, req);
    }
    return true;
  }

  function can(sectionId, action) {
    if (shouldSkipAllGating()) return true;
    const sid = String(sectionId || "").trim();
    const act = String(action || "").trim().toLowerCase();
    if (!sid || !ACTIONS.includes(act)) return false;
    if (Object.prototype.hasOwnProperty.call(cmsGrants, sid)) {
      if (!cmsCan(sid, act)) return false;
    }
    if (crmSectionIds.has(sid)) {
      if (positionId == null || !Number.isFinite(positionId) || positionId <= 0) return true;
      return posCan(sid, act);
    }
    return Object.prototype.hasOwnProperty.call(cmsGrants, sid);
  }

  window.PTT_ADMIN_CAN = can;
  window.PTT_ADMIN_BTN_CAN = btnCan;
  window.PTT_ADMIN_GRANTS_BOOT = boot;
  window.PTT_ADMIN_FULL_ACCESS = isFullAccess || shouldSkipAllGating();

  function canCreateCustomer() {
    return (
      can("crm_board_customers", "create") || can("crm_board_create", "create")
    );
  }

  function isGatingExempt(el) {
    if (!(el instanceof HTMLElement)) return false;
    if (shouldSkipAllGating()) return true;
    if (el.closest(".admin-page-actions")) return true;
    if (el.closest("[data-admin-section-allow]")) return true;
    if (el.closest(".crm-modal-root")) return true;
    if (el.hasAttribute("data-admin-section-allow")) return true;
    if (el.classList.contains("crm-add-open")) return true;
    const id = el.id || "";
    if (id === "crm-cu-open-create" || id === "crm-open-create") return true;
    if (/-add$/.test(id) || /-open-/.test(id) || /^crm-open-/.test(id)) return true;
    return false;
  }

  function isInteractiveExempt(el) {
    if (!(el instanceof HTMLElement)) return false;
    if (isGatingExempt(el)) return true;
    if (el.type === "hidden") return true;
    if (el.closest(".crm-modal-root")) return true;
    if (el.closest("[data-admin-section-allow]")) return true;
    if (el.closest(".admin-page-actions")) return true;
    if (el.hasAttribute("data-admin-section-allow")) return true;
    if (el.classList.contains("crm-add-open")) return true;
    const id = el.id || "";
    if (/-add$/.test(id) || /-open-/.test(id) || /^crm-open-/.test(id)) return true;
    if (el.matches("a.btn, a.btn-secondary, .crm-wf-link-btn")) return true;
    return false;
  }

  function applySectionGating() {
    if (shouldSkipAllGating()) return;

    document.querySelectorAll("[data-admin-section]").forEach((panel) => {
      if (!(panel instanceof HTMLElement)) return;
      if (isGatingExempt(panel)) return;

      const sid = panel.getAttribute("data-admin-section");
      if (!sid) return;
      const requiredAction = panel.getAttribute("data-admin-action") || "view";
      if (!can(sid, requiredAction)) {
        panel.classList.add("admin-section-hidden");
        panel.setAttribute("hidden", "");
        return;
      }
      if (requiredAction !== "view") {
        panel.classList.remove("admin-section-hidden");
        panel.removeAttribute("hidden");
        return;
      }
      if (!can(sid, "view")) {
        panel.classList.add("admin-section-hidden");
        panel.setAttribute("hidden", "");
        return;
      }
      panel.classList.remove("admin-section-hidden");
      panel.removeAttribute("hidden");
      const editable =
        can(sid, "edit") || can(sid, "create") || can(sid, "configure");
      panel.classList.toggle("admin-section-readonly", !editable);
      if (!editable) {
        panel.querySelectorAll("button, input, select, textarea").forEach((el) => {
          if (!isInteractiveExempt(el)) {
            el.setAttribute("disabled", "disabled");
          }
        });
        panel.querySelectorAll(".crm-modal-root button, .crm-modal-root input, .crm-modal-root select, .crm-modal-root textarea").forEach((el) => {
          el.removeAttribute("disabled");
        });
      }
    });

    document.querySelectorAll("[data-admin-nav]").forEach((link) => {
      if (link.classList.contains("admin-nav-link--always")) {
        link.classList.remove("admin-nav-hidden");
        link.removeAttribute("aria-disabled");
        return;
      }
      const sid = link.getAttribute("data-admin-nav");
      if (sid === "crm_hdsd") {
        link.classList.remove("admin-nav-hidden");
        link.removeAttribute("aria-disabled");
        return;
      }
      const pageOk = !sid || can(sid, "view");
      link.classList.toggle("admin-nav-hidden", !pageOk);
      if (!pageOk && link.tagName === "A") {
        link.setAttribute("aria-disabled", "true");
        link.addEventListener("click", (ev) => {
          ev.preventDefault();
        });
      }
    });

    document.querySelectorAll("[data-cms-nav]").forEach((link) => {
      const mid = link.getAttribute("data-cms-nav");
      const pageOk = !mid || can(mid, "view");
      link.classList.toggle("cms-nav-hidden", !pageOk);
      link.classList.toggle("admin-nav-hidden", !pageOk);
      if (!pageOk && link.tagName === "A") {
        link.setAttribute("aria-disabled", "true");
        link.addEventListener("click", (ev) => {
          ev.preventDefault();
        });
      }
    });

    document.querySelectorAll(".admin-nav-group").forEach((group) => {
      if (!(group instanceof HTMLElement)) return;
      if (group.classList.contains("admin-nav-group--always")) {
        group.classList.remove("admin-nav-group--empty");
        return;
      }
      const links = group.querySelectorAll(".admin-nav-link:not(.admin-nav-hidden):not(.cms-nav-hidden)");
      group.classList.toggle("admin-nav-group--empty", links.length === 0);
    });

    document.querySelectorAll("[data-admin-btn]").forEach((el) => {
      if (!(el instanceof HTMLElement)) return;
      const bid = el.getAttribute("data-admin-btn");
      if (!bid || btnCan(bid)) {
        el.classList.remove("admin-btn-hidden");
        el.removeAttribute("hidden");
        return;
      }
      el.classList.add("admin-btn-hidden");
      el.setAttribute("hidden", "");
    });
  }

  window.PTT_ADMIN_CAN_CREATE_CUSTOMER = canCreateCustomer;

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", applySectionGating);
  } else {
    applySectionGating();
  }
})();
