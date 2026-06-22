(function () {
  const toggle = document.getElementById("admin-sidebar-toggle");
  const backdrop = document.getElementById("admin-sidebar-backdrop");
  const sidebar = document.getElementById("admin-sidebar");

  function setOpen(open) {
    document.body.classList.toggle("admin-sidebar-open", open);
    if (toggle) toggle.setAttribute("aria-expanded", open ? "true" : "false");
    if (backdrop) backdrop.hidden = !open;
  }

  toggle?.addEventListener("click", () => {
    setOpen(!document.body.classList.contains("admin-sidebar-open"));
  });

  backdrop?.addEventListener("click", () => setOpen(false));

  sidebar?.querySelectorAll(".admin-nav-link").forEach((link) => {
    link.addEventListener("click", () => {
      if (window.matchMedia("(max-width: 960px)").matches) setOpen(false);
    });
  });

  document.addEventListener("keydown", (ev) => {
    if (ev.key === "Escape") setOpen(false);
  });
})();
