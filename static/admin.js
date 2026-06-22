window.addEventListener("pageshow", (ev) => {
  if (ev.persisted) window.location.reload();
});

const projectsTable = document.getElementById("projects-table");
const newsTable = document.getElementById("news-table");
const projectForm = document.getElementById("project-form");
const newsForm = document.getElementById("news-form");
const crmChannelForm = document.getElementById("crm-channel-form");
const crmChannelsTable = document.getElementById("crm-channels-table");
const crmChannelErr = document.getElementById("crm-channel-msg-error");

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

  if (response.status === 204) {
    return null;
  }
  return response.json();
}

function esc(s) {
  const d = document.createElement("div");
  d.textContent = s ?? "";
  return d.innerHTML;
}

function renderCrmChannels(items) {
  if (!crmChannelsTable) return;
  crmChannelsTable.innerHTML = (items || [])
    .map(
      (item) => `
      <tr data-channel-id="${item.id}">
        <td><code>${esc(item.code)}</code></td>
        <td>${esc(item.name)}</td>
        <td>${esc(item.description || "—")}</td>
        <td>${Number(item.sort_order || 0)}</td>
        <td>${Number(item.active) === 1 ? "Đang dùng" : "Đã tắt"}</td>
        <td>
          ${
            Number(item.active) === 1
              ? `<button type="button" class="delete-btn" data-channel-disable="${item.id}">Tắt</button>`
              : `<button type="button" class="btn-secondary btn-sm" data-channel-enable="${item.id}">Bật lại</button>`
          }
        </td>
      </tr>
    `
    )
    .join("");
}

async function loadCrmChannels() {
  if (!crmChannelsTable) return;
  const data = await requestJson("/api/crm/channels?include_inactive=1");
  renderCrmChannels(data.channels || []);
}

function renderProjects(items) {
  projectsTable.innerHTML = items
    .map(
      (item) => `
      <tr>
        <td>${item.title}</td>
        <td>${item.category}</td>
        <td>${item.description}</td>
        <td><button class="delete-btn" data-project-id="${item.id}">Xóa</button></td>
      </tr>
    `
    )
    .join("");
}

function renderNews(items) {
  newsTable.innerHTML = items
    .map(
      (item) => `
      <tr>
        <td>${item.title}</td>
        <td>${item.summary}</td>
        <td><a href="${item.url}" target="_blank" rel="noopener noreferrer">Mở</a></td>
        <td><button class="delete-btn" data-news-id="${item.id}">Xóa</button></td>
      </tr>
    `
    )
    .join("");
}

async function loadData() {
  const tasks = [requestJson("/api/projects"), requestJson("/api/news")];
  if (crmChannelsTable) tasks.push(loadCrmChannels());
  const [projects, news] = await Promise.all(tasks.slice(0, 2));
  renderProjects(projects);
  renderNews(news);
  if (crmChannelsTable) await loadCrmChannels();
}

crmChannelForm?.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (crmChannelErr) crmChannelErr.hidden = true;
  const data = Object.fromEntries(new FormData(crmChannelForm).entries());
  try {
    await requestJson("/api/crm/channels", {
      method: "POST",
      body: JSON.stringify({
        name: data.name,
        code: data.code || "",
        description: data.description || "",
        sort_order: data.sort_order ? Number(data.sort_order) : 0,
      }),
    });
    crmChannelForm.reset();
    await loadCrmChannels();
  } catch (err) {
    if (crmChannelErr) {
      crmChannelErr.textContent =
        err instanceof Error ? err.message : "Không tạo được kênh";
      crmChannelErr.hidden = false;
    }
  }
});

crmChannelsTable?.addEventListener("click", async (event) => {
  const target = event.target;
  if (!(target instanceof HTMLElement)) return;
  const disableId = target.getAttribute("data-channel-disable");
  const enableId = target.getAttribute("data-channel-enable");
  const id = disableId || enableId;
  if (!id) return;
  await requestJson(`/api/crm/channels/${id}`, {
    method: "PATCH",
    body: JSON.stringify({ active: enableId ? 1 : 0 }),
  });
  await loadCrmChannels();
});

projectForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const data = Object.fromEntries(new FormData(projectForm).entries());
  await requestJson("/api/projects", {
    method: "POST",
    body: JSON.stringify(data),
  });
  projectForm.reset();
  loadData();
});

newsForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const data = Object.fromEntries(new FormData(newsForm).entries());
  await requestJson("/api/news", {
    method: "POST",
    body: JSON.stringify(data),
  });
  newsForm.reset();
  loadData();
});

projectsTable.addEventListener("click", async (event) => {
  const target = event.target;
  if (!(target instanceof HTMLElement)) return;
  const id = target.getAttribute("data-project-id");
  if (!id) return;
  await requestJson(`/api/projects/${id}`, { method: "DELETE" });
  loadData();
});

newsTable.addEventListener("click", async (event) => {
  const target = event.target;
  if (!(target instanceof HTMLElement)) return;
  const id = target.getAttribute("data-news-id");
  if (!id) return;
  await requestJson(`/api/news/${id}`, { method: "DELETE" });
  loadData();
});

loadData();
