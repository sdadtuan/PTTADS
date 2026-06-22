window.addEventListener("pageshow", (ev) => {
  if (ev.persisted) window.location.reload();
});

const settingsForm = document.getElementById("settings-form");
const saveStatus = document.getElementById("save-status");
const servicesForm = document.getElementById("services-form");
const servicesJson = document.getElementById("services-json");
const servicesStatus = document.getElementById("services-status");
const categoryList = document.getElementById("category-list");
const categoryEditor = document.getElementById("category-editor");
const itemEditor = document.getElementById("item-editor");
const addCategoryBtn = document.getElementById("add-category-btn");
const deleteCategoryBtn = document.getElementById("delete-category-btn");
const addItemBtn = document.getElementById("add-item-btn");
const deleteItemBtn = document.getElementById("delete-item-btn");
const duplicateItemBtn = document.getElementById("duplicate-item-btn");
const moveCategoryUpBtn = document.getElementById("move-category-up-btn");
const moveCategoryDownBtn = document.getElementById("move-category-down-btn");
const moveItemUpBtn = document.getElementById("move-item-up-btn");
const moveItemDownBtn = document.getElementById("move-item-down-btn");
const categoryTitleInput = document.getElementById("category-title");
const itemNameInput = document.getElementById("item-name");
const itemSlugInput = document.getElementById("item-slug");
const itemSummaryInput = document.getElementById("item-summary");
const itemHighlightsInput = document.getElementById("item-highlights");
const itemPreviewLink = document.getElementById("item-preview-link");
const servicesDirtyBadge = document.getElementById("services-dirty-badge");
const mkChatSettingsForm = document.getElementById("mk-chat-settings-form");
const mkChatSettingsStatus = document.getElementById("mk-chat-settings-status");

let serviceState = [];
let selectedCategoryIndex = -1;
let selectedItemIndex = -1;
let servicesDirty = false;

async function requestJson(url, options = {}) {
  const response = await fetch(url, {
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    ...options,
  });

  if (response.status === 401) {
    const body = await response.json().catch(() => ({}));
    if (typeof body.login === "string") {
      window.location.href = body.login;
    }
    throw new Error(body.error || "Unauthorized");
  }

  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.error || "Request failed");
  }

  return response.json();
}

function slugify(text) {
  return text
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/(^-|-$)/g, "");
}

function markServicesDirty() {
  servicesDirty = true;
  servicesDirtyBadge.classList.remove("hidden");
}

function markServicesClean() {
  servicesDirty = false;
  servicesDirtyBadge.classList.add("hidden");
}

function ensureSelectionInRange() {
  if (serviceState.length === 0) {
    selectedCategoryIndex = -1;
    selectedItemIndex = -1;
    return;
  }

  if (selectedCategoryIndex < 0 || selectedCategoryIndex >= serviceState.length) {
    selectedCategoryIndex = 0;
  }

  const items = serviceState[selectedCategoryIndex].items || [];
  if (items.length === 0) {
    selectedItemIndex = -1;
  } else if (selectedItemIndex < 0 || selectedItemIndex >= items.length) {
    selectedItemIndex = 0;
  }
}

function syncJsonFromState() {
  servicesJson.value = JSON.stringify(serviceState, null, 2);
}

function renderCategoryList() {
  categoryList.innerHTML = "";

  serviceState.forEach((category, cIndex) => {
    const wrapper = document.createElement("div");
    wrapper.className = "category-block";

    const button = document.createElement("button");
    button.type = "button";
    button.className = `category-btn ${cIndex === selectedCategoryIndex ? "active" : ""}`;
    button.textContent = category.title || `Category ${cIndex + 1}`;
    button.addEventListener("click", () => {
      selectedCategoryIndex = cIndex;
      selectedItemIndex = (category.items || []).length > 0 ? 0 : -1;
      renderServiceBuilder();
    });
    wrapper.appendChild(button);

    const itemsWrap = document.createElement("div");
    itemsWrap.className = "item-chip-list";

    (category.items || []).forEach((item, iIndex) => {
      const chip = document.createElement("button");
      chip.type = "button";
      chip.className = `item-chip ${cIndex === selectedCategoryIndex && iIndex === selectedItemIndex ? "active" : ""}`;
      chip.textContent = item.name || "Item";
      chip.addEventListener("click", () => {
        selectedCategoryIndex = cIndex;
        selectedItemIndex = iIndex;
        renderServiceBuilder();
      });
      itemsWrap.appendChild(chip);
    });

    wrapper.appendChild(itemsWrap);
    categoryList.appendChild(wrapper);
  });
}

function renderEditors() {
  if (selectedCategoryIndex < 0 || !serviceState[selectedCategoryIndex]) {
    categoryEditor.classList.add("hidden");
    itemEditor.classList.add("hidden");
    return;
  }

  const category = serviceState[selectedCategoryIndex];
  categoryEditor.classList.remove("hidden");
  categoryTitleInput.value = category.title || "";

  if (selectedItemIndex < 0 || !category.items || !category.items[selectedItemIndex]) {
    itemEditor.classList.add("hidden");
    return;
  }

  const item = category.items[selectedItemIndex];
  itemEditor.classList.remove("hidden");
  itemNameInput.value = item.name || "";
  itemSlugInput.value = item.slug || "";
  itemSummaryInput.value = item.summary || "";
  itemHighlightsInput.value = (item.highlights || []).join("\n");
  itemPreviewLink.href = item.slug ? `/services/${item.slug}` : "#";
  itemPreviewLink.textContent = item.slug
    ? `Mở preview: /services/${item.slug}`
    : "Mở preview trang chi tiết";
}

function renderServiceBuilder() {
  ensureSelectionInRange();
  renderCategoryList();
  renderEditors();
  syncJsonFromState();
}

async function loadSettings() {
  const settings = await requestJson("/api/settings");
  Object.entries(settings).forEach(([key, value]) => {
    const input = settingsForm.querySelector(`[name="${key}"]`);
    if (input) {
      input.value = value;
    }
  });
  if (mkChatSettingsForm) {
    Object.entries(settings).forEach(([key, value]) => {
      const input = mkChatSettingsForm.querySelector(`[name="${key}"]`);
      if (!input) return;
      if (input.type === "checkbox") {
        const off = ["0", "false", "no", "off", ""];
        input.checked = !off.includes(String(value).trim().toLowerCase());
      } else {
        input.value = value;
      }
    });
  }
}

async function loadServices() {
  const services = await requestJson("/api/services");
  serviceState = Array.isArray(services) ? services : [];
  if (serviceState.length > 0) {
    selectedCategoryIndex = 0;
    selectedItemIndex = (serviceState[0].items || []).length > 0 ? 0 : -1;
  }
  renderServiceBuilder();
  markServicesClean();
}

if (settingsForm) {
  settingsForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const data = Object.fromEntries(new FormData(settingsForm).entries());
    await requestJson("/api/settings", {
      method: "PUT",
      body: JSON.stringify(data),
    });
    if (saveStatus) saveStatus.textContent = "Da luu cài đặt thành công.";
    setTimeout(() => {
      if (saveStatus) saveStatus.textContent = "";
    }, 2500);
  });
}

if (mkChatSettingsForm) {
  mkChatSettingsForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const data = {};
    new FormData(mkChatSettingsForm).forEach((value, key) => {
      data[key] = value;
    });
    const enabledCb = mkChatSettingsForm.querySelector('[name="cms_mk_chat_enabled"]');
    data.cms_mk_chat_enabled = enabledCb && enabledCb.checked ? "1" : "0";
    try {
      await requestJson("/api/settings", {
        method: "PUT",
        body: JSON.stringify(data),
      });
      if (mkChatSettingsStatus) {
        mkChatSettingsStatus.textContent = "Đã lưu cấu hình chatbox marketing.";
      }
    } catch (error) {
      if (mkChatSettingsStatus) {
        mkChatSettingsStatus.textContent = `Lỗi: ${error.message}`;
      }
    }
    setTimeout(() => {
      if (mkChatSettingsStatus) mkChatSettingsStatus.textContent = "";
    }, 3000);
  });
}

if (servicesForm) {
  servicesForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      const parsed = JSON.parse(servicesJson.value);
      await requestJson("/api/services", {
        method: "PUT",
        body: JSON.stringify(parsed),
      });
      serviceState = parsed;
      renderServiceBuilder();
      markServicesClean();
      if (servicesStatus) servicesStatus.textContent = "Da luu dịch vụ thành công.";
    } catch (error) {
      if (servicesStatus) servicesStatus.textContent = `Lỗi: ${error.message}`;
    }

    setTimeout(() => {
      if (servicesStatus) servicesStatus.textContent = "";
    }, 3000);
  });
}

if (servicesJson) {
  servicesJson.addEventListener("blur", () => {
    try {
      const parsed = JSON.parse(servicesJson.value);
      if (Array.isArray(parsed)) {
        serviceState = parsed;
        renderServiceBuilder();
        markServicesDirty();
      }
    } catch (_error) {
      // keep invalid json for user to fix
    }
  });
}

if (addCategoryBtn) {
  addCategoryBtn.addEventListener("click", () => {
    serviceState.push({
      title: "Category mới",
      items: [],
    });
    selectedCategoryIndex = serviceState.length - 1;
    selectedItemIndex = -1;
    renderServiceBuilder();
    markServicesDirty();
  });

  deleteCategoryBtn?.addEventListener("click", () => {
    if (selectedCategoryIndex < 0) return;
    serviceState.splice(selectedCategoryIndex, 1);
    selectedCategoryIndex = Math.min(selectedCategoryIndex, serviceState.length - 1);
    selectedItemIndex = 0;
    renderServiceBuilder();
    markServicesDirty();
  });

  moveCategoryUpBtn?.addEventListener("click", () => {
    if (selectedCategoryIndex <= 0) return;
    const current = serviceState[selectedCategoryIndex];
    serviceState[selectedCategoryIndex] = serviceState[selectedCategoryIndex - 1];
    serviceState[selectedCategoryIndex - 1] = current;
    selectedCategoryIndex -= 1;
    renderServiceBuilder();
    markServicesDirty();
  });

  moveCategoryDownBtn?.addEventListener("click", () => {
    if (selectedCategoryIndex < 0 || selectedCategoryIndex >= serviceState.length - 1) return;
    const current = serviceState[selectedCategoryIndex];
    serviceState[selectedCategoryIndex] = serviceState[selectedCategoryIndex + 1];
    serviceState[selectedCategoryIndex + 1] = current;
    selectedCategoryIndex += 1;
    renderServiceBuilder();
    markServicesDirty();
  });

  addItemBtn?.addEventListener("click", () => {
    if (selectedCategoryIndex < 0) return;
    const items = serviceState[selectedCategoryIndex].items || [];
    serviceState[selectedCategoryIndex].items = items;
    items.push({
      slug: `service-${Date.now()}`,
      name: "Dịch vụ mới",
      summary: "",
      highlights: [],
    });
    selectedItemIndex = items.length - 1;
    renderServiceBuilder();
    markServicesDirty();
  });

  deleteItemBtn?.addEventListener("click", () => {
    if (selectedCategoryIndex < 0 || selectedItemIndex < 0) return;
    const items = serviceState[selectedCategoryIndex].items || [];
    items.splice(selectedItemIndex, 1);
    selectedItemIndex = Math.min(selectedItemIndex, items.length - 1);
    renderServiceBuilder();
    markServicesDirty();
  });

  duplicateItemBtn?.addEventListener("click", () => {
    if (selectedCategoryIndex < 0 || selectedItemIndex < 0) return;
    const items = serviceState[selectedCategoryIndex].items || [];
    const source = items[selectedItemIndex];
    if (!source) return;
    const duplicated = {
      ...source,
      slug: `${source.slug || "service"}-${Date.now()}`,
      name: `${source.name || "Dịch vụ"} (copy)`,
      highlights: [...(source.highlights || [])],
    };
    items.splice(selectedItemIndex + 1, 0, duplicated);
    selectedItemIndex += 1;
    renderServiceBuilder();
    markServicesDirty();
  });

  moveItemUpBtn?.addEventListener("click", () => {
    if (selectedCategoryIndex < 0 || selectedItemIndex <= 0) return;
    const items = serviceState[selectedCategoryIndex].items || [];
    const current = items[selectedItemIndex];
    items[selectedItemIndex] = items[selectedItemIndex - 1];
    items[selectedItemIndex - 1] = current;
    selectedItemIndex -= 1;
    renderServiceBuilder();
    markServicesDirty();
  });

  moveItemDownBtn?.addEventListener("click", () => {
    if (selectedCategoryIndex < 0 || selectedItemIndex < 0) return;
    const items = serviceState[selectedCategoryIndex].items || [];
    if (selectedItemIndex >= items.length - 1) return;
    const current = items[selectedItemIndex];
    items[selectedItemIndex] = items[selectedItemIndex + 1];
    items[selectedItemIndex + 1] = current;
    selectedItemIndex += 1;
    renderServiceBuilder();
    markServicesDirty();
  });

  categoryTitleInput?.addEventListener("input", () => {
    if (selectedCategoryIndex < 0) return;
    serviceState[selectedCategoryIndex].title = categoryTitleInput.value;
    renderCategoryList();
    syncJsonFromState();
    markServicesDirty();
  });

  itemNameInput?.addEventListener("input", () => {
    if (selectedCategoryIndex < 0 || selectedItemIndex < 0) return;
    const item = serviceState[selectedCategoryIndex].items[selectedItemIndex];
    item.name = itemNameInput.value;
    if (!item.slug || item.slug.startsWith("service-")) {
      item.slug = slugify(itemNameInput.value) || `service-${Date.now()}`;
    }
    itemSlugInput.value = item.slug;
    renderCategoryList();
    syncJsonFromState();
    itemPreviewLink.href = `/services/${item.slug}`;
    markServicesDirty();
  });

  itemSlugInput?.addEventListener("input", () => {
    if (selectedCategoryIndex < 0 || selectedItemIndex < 0) return;
    const slug = slugify(itemSlugInput.value);
    serviceState[selectedCategoryIndex].items[selectedItemIndex].slug = slug;
    itemPreviewLink.href = slug ? `/services/${slug}` : "#";
    itemPreviewLink.textContent = slug ? `Mở preview: /services/${slug}` : "Mở preview trang chi tiết";
    syncJsonFromState();
    markServicesDirty();
  });

  itemSummaryInput?.addEventListener("input", () => {
    if (selectedCategoryIndex < 0 || selectedItemIndex < 0) return;
    serviceState[selectedCategoryIndex].items[selectedItemIndex].summary = itemSummaryInput.value;
    syncJsonFromState();
    markServicesDirty();
  });

  itemHighlightsInput?.addEventListener("input", () => {
    if (selectedCategoryIndex < 0 || selectedItemIndex < 0) return;
    serviceState[selectedCategoryIndex].items[selectedItemIndex].highlights = itemHighlightsInput.value
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean);
    syncJsonFromState();
    markServicesDirty();
  });
}

window.addEventListener("beforeunload", (event) => {
  if (!servicesDirty) return;
  event.preventDefault();
  event.returnValue = "";
});

Promise.all([loadSettings(), loadServices()]).catch((error) => {
  const message = `Lỗi tải dữ liệu CMS: ${error.message}`;
  if (saveStatus) saveStatus.textContent = message;
  if (servicesStatus) servicesStatus.textContent = message;
});
