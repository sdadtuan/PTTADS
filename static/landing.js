const toggleButton = document.querySelector("[data-menu-toggle]");
const mobileMenu = document.querySelector("[data-mobile-menu]");
const sectionLinks = document.querySelectorAll(
  '.landing-nav a[href^="#"], [data-mobile-menu] a[href^="#"]'
);
const sections = [...document.querySelectorAll("main[id], section[id]")];
const navMegaOpener = document.querySelector("[data-nav-mega-opener]");
const navMegaHover = document.querySelector("[data-nav-mega-hover]");
const navMegaPanel = document.querySelector("[data-nav-mega-panel]");
const navMegaBackdrop = document.querySelector("[data-nav-mega-backdrop]");
let navMegaCloseTimer = 0;
/** Hover mega: tọa độ từ elementFromPoint, không từ pointerenter/leave (tránh bắn lặp dù con trừt đứng yên). */
let megaLastInZone = null;
let megaHoverDismissed = false;
let megaPointerTrackRaf = 0;
let lastPointerX = 0;
let lastPointerY = 0;
let hasLastPointer = false;

function isDesktopNavMega() {
  return window.matchMedia("(min-width: 901px)").matches;
}

function syncLandingTopbarRowHeight() {
  const bar = document.querySelector(".landing-topbar");
  if (!bar) return;
  const row = bar.querySelector(".nav-wrap");
  if (row) {
    document.documentElement.style.setProperty(
      "--landing-topbar-row-h",
      `${Math.round(row.getBoundingClientRect().height)}px`
    );
  }
}

if (document.body.classList.contains("landing-body")) {
  document.documentElement.classList.add("landing-pad");

  function syncLandingTopbarHeight() {
    const bar = document.querySelector(".landing-topbar");
    if (!bar) return;
    const h = Math.round(bar.getBoundingClientRect().height);
    document.documentElement.style.setProperty("--landing-topbar-h", `${h}px`);
    syncLandingTopbarRowHeight();
  }

  syncLandingTopbarHeight();
  window.addEventListener("resize", syncLandingTopbarHeight, { passive: true });
  window.addEventListener("orientationchange", syncLandingTopbarHeight, { passive: true });
} else if (document.querySelector(".landing-topbar")) {
  syncLandingTopbarRowHeight();
  window.addEventListener("resize", syncLandingTopbarRowHeight, { passive: true });
  window.addEventListener("orientationchange", syncLandingTopbarRowHeight, { passive: true });
}

function elementFromClickEvent(e) {
  const t = e.target;
  if (!t) return null;
  if (t.nodeType === Node.ELEMENT_NODE) return t;
  if (t.nodeType === Node.TEXT_NODE) return t.parentElement;
  return null;
}

function getStickyHeaderOffset() {
  const bar = document.querySelector(".landing-topbar");
  if (!bar) return 110;
  return Math.round(bar.getBoundingClientRect().height) + 8;
}

function scrollToLandingHash(href, behavior) {
  if (!href || !href.startsWith("#") || href.length < 2) return false;
  const id = href.slice(1);
  const el = document.getElementById(id);
  if (!el) return false;
  const prefersReduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const beh = prefersReduce ? "auto" : behavior || "smooth";
  const top = el.getBoundingClientRect().top + window.scrollY - getStickyHeaderOffset();
  window.scrollTo({ top: Math.max(0, top), behavior: beh });
  return true;
}

function isNodeInside(needle, haystack) {
  if (!needle || !haystack) return false;
  if (needle === haystack) return true;
  return typeof haystack.contains === "function" && haystack.contains(needle);
}

/**
 * Có trong vùng toàn bộ mega = pill "Dịch vụ" + panel (data-nav-mega-hover).
 * Dùng elementsFromPoint: phần tử trên cùng có thể là khe/lớp mờ nhưng vẫn còn trong stack.
 */
function isClientInNavMega(clientX, clientY) {
  if (!navMegaHover) return false;
  if (typeof document.elementsFromPoint === "function") {
    const list = document.elementsFromPoint(clientX, clientY);
    for (let i = 0; i < list.length; i++) {
      const el = list[i];
      if (el === navMegaHover || navMegaHover.contains(el)) {
        return true;
      }
    }
    return false;
  }
  const el = document.elementFromPoint(clientX, clientY);
  return Boolean(el && (el === navMegaHover || navMegaHover.contains(el)));
}

function markNavMegaHoverExplicitClose() {
  if (!isDesktopNavMega() || !navMegaHover) return;
  megaHoverDismissed = true;
  if (hasLastPointer) {
    megaLastInZone = isClientInNavMega(lastPointerX, lastPointerY);
  } else {
    try {
      megaLastInZone = navMegaHover.matches(":hover");
    } catch {
      megaLastInZone = true;
    }
  }
}

function setNavMegaOpen(open, options = {}) {
  if (navMegaCloseTimer) {
    clearTimeout(navMegaCloseTimer);
    navMegaCloseTimer = 0;
  }
  if (!navMegaOpener || !navMegaPanel) return;
  const show = Boolean(open);
  const explicitClose = Boolean(options.explicitClose);
  /* Đã mở mà lại bật true → bỏ qua (rê chuột / gọi lặp không làm gì) */
  if (show && !navMegaPanel.hidden) {
    return;
  }
  if (!show && navMegaPanel.hidden) {
    return;
  }
  if (!show && explicitClose) {
    markNavMegaHoverExplicitClose();
  }
  navMegaPanel.hidden = !show;
  navMegaOpener.setAttribute("aria-expanded", show ? "true" : "false");
  if (navMegaBackdrop) {
    navMegaBackdrop.hidden = !show;
  }
  document.body.classList.toggle("nav-mega-open", show);
  if (show) {
    megaHoverDismissed = false;
    megaLastInZone = true;
    syncNavMegaPanelTop();
  }
}

/** Chỉ mở khi submenu đang đóng. Đã bật rồi thì rê chuột lại sẽ không gọi lại setNavMegaOpen(true). */
function openNavMegaIfClosed() {
  if (!navMegaOpener || !navMegaPanel) return;
  if (!navMegaPanel.hidden) return;
  setNavMegaOpen(true);
}

function scheduleNavMegaClose() {
  if (navMegaCloseTimer) clearTimeout(navMegaCloseTimer);
  navMegaCloseTimer = window.setTimeout(() => {
    navMegaCloseTimer = 0;
    setNavMegaOpen(false);
  }, 520);
}

function syncNavMegaPanelTop() {
  if (!navMegaPanel) return;
  /* Chỉ cần khi mega mở — tránh cập nhật liên tục khi đóng (giảm reflow, ít tác dụng phụ) */
  if (navMegaPanel.hidden) return;
  const bar = document.querySelector(".landing-topbar");
  if (!bar) return;
  const bottom = Math.max(0, Math.round(bar.getBoundingClientRect().bottom));
  document.documentElement.style.setProperty("--nav-mega-panel-top", `${bottom}px`);
}

/**
 * Mở khi vừa vào vùng; khi còn di trong vùng: không gọi lại mở, chỉ hủy hẹn đóng nếu có;
 * đóng (sau trễ) chỉ khi tọa độ xác định đã ra khỏi vùng.
 */
function applyMegaPointerZone(clientX, clientY) {
  if (!isDesktopNavMega() || !navMegaHover || !navMegaPanel) {
    if (!isDesktopNavMega()) {
      megaLastInZone = null;
    }
    return;
  }
  const inZone = isClientInNavMega(clientX, clientY);
  /* Vẫn trong vùng: luôn hủy hẹn đóng (tránh 1 lần "ra" giả) — không thay đổi gì tới mở menu */
  if (inZone && navMegaCloseTimer) {
    clearTimeout(navMegaCloseTimer);
    navMegaCloseTimer = 0;
  }
  if (inZone === megaLastInZone) {
    return;
  }
  const wasUnknown = megaLastInZone === null;
  megaLastInZone = inZone;
  if (inZone) {
    if (megaHoverDismissed) {
      return;
    }
    if (navMegaCloseTimer) {
      clearTimeout(navMegaCloseTimer);
      navMegaCloseTimer = 0;
    }
    if (navMegaPanel.hidden) {
      setNavMegaOpen(true);
    }
  } else {
    if (wasUnknown) {
      return;
    }
    megaHoverDismissed = false;
    scheduleNavMegaClose();
  }
}

function onDocumentPointerMove(e) {
  if (e.pointerType === "touch") {
    return;
  }
  if (!isDesktopNavMega() || !navMegaHover) {
    return;
  }
  hasLastPointer = true;
  lastPointerX = e.clientX;
  lastPointerY = e.clientY;
  if (megaPointerTrackRaf) {
    return;
  }
  megaPointerTrackRaf = requestAnimationFrame(() => {
    megaPointerTrackRaf = 0;
    if (!isDesktopNavMega() || !navMegaHover) {
      return;
    }
    applyMegaPointerZone(lastPointerX, lastPointerY);
  });
}

if (navMegaOpener && navMegaPanel) {
  navMegaOpener.addEventListener("click", (e) => {
    e.preventDefault();
    e.stopPropagation();
    setNavMegaOpen(navMegaPanel.hidden, { explicitClose: !navMegaPanel.hidden });
  });
  document.addEventListener("click", (e) => {
    const t = e.target;
    if (!(t instanceof Element)) return;
    if (navMegaPanel.hidden) return;
    if (t.closest("[data-nav-mega-hover]")) return;
    setNavMegaOpen(false, { explicitClose: true });
  });
  navMegaPanel.addEventListener("click", (e) => {
    const a = e.target instanceof Element ? e.target.closest("a[href]") : null;
    if (a) {
      setNavMegaOpen(false, { explicitClose: true });
    }
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !navMegaPanel.hidden) {
      setNavMegaOpen(false, { explicitClose: true });
    }
  });
  window.addEventListener(
    "resize",
    () => {
      if (window.matchMedia("(max-width: 900px)").matches) {
        setNavMegaOpen(false);
        megaLastInZone = null;
        megaHoverDismissed = false;
      } else {
        syncNavMegaPanelTop();
      }
    },
    { passive: true }
  );
}

if (navMegaOpener && navMegaPanel && navMegaHover) {
  document.addEventListener("pointermove", onDocumentPointerMove, { passive: true, capture: true });
}

/* Link #… trong header landing: bắt ở document (capture) + scrollTo — ổn định hơn bubble trên header */
document.addEventListener(
  "click",
  (e) => {
    const start = elementFromClickEvent(e);
    if (!start) return;
    const a = start.closest("a[href]");
    if (!a) return;
    if (!a.closest("header.landing-topbar")) return;
    if (a.classList.contains("nav-mega-dv-link") && isDesktopNavMega()) {
      e.preventDefault();
      e.stopPropagation();
      if (navMegaPanel.hidden) {
        openNavMegaIfClosed();
      } else {
        setNavMegaOpen(false, { explicitClose: true });
      }
      return;
    }
    const href = a.getAttribute("href");
    if (!href || !href.startsWith("#") || href.length < 2) return;
    if (!document.getElementById(href.slice(1))) return;
    e.preventDefault();
    scrollToLandingHash(href, "smooth");
    try {
      if (window.history && window.history.replaceState) {
        window.history.replaceState(null, "", href);
      } else {
        window.location.hash = href;
      }
    } catch (_) {
      window.location.hash = href;
    }
    setNavMegaOpen(false, { explicitClose: true });
    mobileMenu?.classList.remove("open");
  },
  true
);

/* Link #… trong <main> landing — neo dự án (#project-…) và các mục trên trang */
document.addEventListener(
  "click",
  (e) => {
    const start = elementFromClickEvent(e);
    if (!start) return;
    const a = start.closest("a[href]");
    if (!a) return;
    if (!a.closest("main.landing-main")) return;
    const href = a.getAttribute("href");
    if (!href || !href.startsWith("#") || href.length < 2) return;
    if (!document.getElementById(href.slice(1))) return;
    e.preventDefault();
    scrollToLandingHash(href, "smooth");
    try {
      if (window.history && window.history.replaceState) {
        window.history.replaceState(null, "", href);
      } else {
        window.location.hash = href;
      }
    } catch (_) {
      window.location.hash = href;
    }
    mobileMenu?.classList.remove("open");
  },
  true
);

const sagaWorkGrid = document.querySelector(".saga-work-grid.saga-work-grid--collapsible");
const sagaWorkMoreBtn = document.querySelector("[data-saga-work-more]");
function setSagaWorkExpanded(expanded) {
  if (!sagaWorkGrid) return;
  sagaWorkGrid.classList.toggle("is-expanded", expanded);
  if (sagaWorkMoreBtn) {
    sagaWorkMoreBtn.setAttribute("aria-expanded", expanded ? "true" : "false");
    sagaWorkMoreBtn.textContent = expanded ? "Thu gọn" : "Xem thêm dự án";
  }
}
if (sagaWorkGrid && sagaWorkMoreBtn) {
  sagaWorkMoreBtn.addEventListener("click", () => {
    setSagaWorkExpanded(!sagaWorkGrid.classList.contains("is-expanded"));
  });
}
function expandSagaIfHashTargetsHiddenCard() {
  if (!sagaWorkGrid) return;
  const raw = window.location.hash;
  if (!raw || !raw.startsWith("#project-")) return;
  const el = document.getElementById(raw.slice(1));
  if (el && el.classList.contains("saga-work-card--extra")) {
    setSagaWorkExpanded(true);
  }
}
expandSagaIfHashTargetsHiddenCard();
window.addEventListener("hashchange", expandSagaIfHashTargetsHiddenCard);

const servicesAccordion = document.querySelector("[data-services-accordion]");

if (toggleButton && mobileMenu) {
  function setMobileMenuOpen(open) {
    mobileMenu.classList.toggle("open", open);
    toggleButton.setAttribute("aria-expanded", open ? "true" : "false");
    document.body.classList.toggle("mobile-menu-open", open);
    document.body.style.overflow = open ? "hidden" : "";
    syncLandingTopbarRowHeight();
  }

  toggleButton.addEventListener("click", () => {
    setMobileMenuOpen(!mobileMenu.classList.contains("open"));
  });

  mobileMenu.querySelectorAll("a").forEach((link) => {
    link.addEventListener("click", () => {
      setMobileMenuOpen(false);
    });
  });

  document.addEventListener("click", (event) => {
    const target = event.target;
    if (!(target instanceof HTMLElement)) return;
    if (!target.closest("[data-mobile-menu]") && !target.closest("[data-menu-toggle]")) {
      setMobileMenuOpen(false);
    }
  });
}

if (sectionLinks.length > 0 && sections.length > 0) {
  const activeClass = "is-active";

  /** Tọa độ top của phần tử tính theo tài liệu (offsetTop hay sai nếu offsetParent # khác) */
  function getDocumentOffsetTop(el) {
    return el.getBoundingClientRect().top + window.scrollY;
  }

  const setActiveLink = () => {
    const viewLine = window.scrollY + getStickyHeaderOffset();
    /* section cuối cùng mà user đã cuộn tới/qua — khớp với vạch “đang xem” dưới thanh */
    let currentId = "";
    for (let i = sections.length - 1; i >= 0; i -= 1) {
      const sec = sections[i];
      const top = getDocumentOffsetTop(sec);
      if (viewLine + 0.5 >= top) {
        currentId = sec.id;
        break;
      }
    }
    /* currentId === "" ở vùng hero (phía trên section [id] đầu) — không tô mục menu */

    sectionLinks.forEach((link) => {
      const href = link.getAttribute("href");
      const isCurrent = currentId && href === `#${currentId}`;
      link.classList.toggle(activeClass, isCurrent);
    });
    if (navMegaOpener) {
      navMegaOpener.classList.toggle(activeClass, currentId === "main");
    }
  };

  let scrollSpyRaf = 0;
  const onScrollOrResize = () => {
    if (scrollSpyRaf) return;
    scrollSpyRaf = window.requestAnimationFrame(() => {
      scrollSpyRaf = 0;
      setActiveLink();
    });
  };

  setActiveLink();
  window.addEventListener("scroll", onScrollOrResize, { passive: true });
  window.addEventListener("resize", onScrollOrResize, { passive: true });
  window.addEventListener("popstate", setActiveLink);

  /* Vào trang kèm hash (#main, #contact, …) — neo đúng mục */
  const scrollToHashFromLocation = () => {
    const raw = window.location.hash;
    if (!raw || raw.length < 2) return;
    window.setTimeout(() => {
      scrollToLandingHash(raw, "auto");
      setActiveLink();
    }, 0);
  };
  if (document.readyState === "complete") {
    scrollToHashFromLocation();
  } else {
    window.addEventListener("load", scrollToHashFromLocation, { once: true });
  }
}

if (servicesAccordion) {
  const items = [...servicesAccordion.querySelectorAll("[data-service-acc-item]")];
  const triggers = [...servicesAccordion.querySelectorAll("[data-service-acc-trigger]")];
  const jumpWrap = document.querySelector("[data-service-jump]");
  const jumpButtons = jumpWrap ? [...jumpWrap.querySelectorAll("[data-service-jump-target]")] : [];

  const setOpenItem = (targetItem, options = { updateHash: true, scrollIntoView: false }) => {
    let openedId = "";
    items.forEach((item) => {
      const isOpen = item === targetItem;
      item.classList.toggle("is-open", isOpen);
      if (isOpen) {
        openedId = item.id || "";
      }
      const trigger = item.querySelector("[data-service-acc-trigger]");
      if (trigger) {
        trigger.setAttribute("aria-expanded", isOpen ? "true" : "false");
      }
    });

    jumpButtons.forEach((button) => {
      const targetId = button.getAttribute("data-service-jump-target");
      button.classList.toggle("active", Boolean(targetId && targetId === openedId));
      button.setAttribute("aria-selected", targetId && targetId === openedId ? "true" : "false");
    });

    if (options.updateHash && openedId) {
      history.replaceState(null, "", `#${openedId}`);
    }

    if (options.scrollIntoView && targetItem) {
      targetItem.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  };

  triggers.forEach((trigger) => {
    trigger.addEventListener("click", () => {
      const item = trigger.closest("[data-service-acc-item]");
      if (!item) return;
      setOpenItem(item);
    });
  });

  jumpButtons.forEach((button) => {
    button.addEventListener("click", () => {
      const targetId = button.getAttribute("data-service-jump-target");
      if (!targetId) return;
      const targetItem = items.find((item) => item.id === targetId);
      if (!targetItem) return;
      setOpenItem(targetItem, { updateHash: true, scrollIntoView: true });
    });
  });

  if (jumpButtons.length > 1) {
    jumpButtons.forEach((button, index) => {
      button.addEventListener("keydown", (event) => {
        const key = event.key;
        if (!["ArrowRight", "ArrowLeft", "Home", "End"].includes(key)) return;
        event.preventDefault();
        let targetIndex = index;
        if (key === "ArrowRight") {
          targetIndex = (index + 1) % jumpButtons.length;
        } else if (key === "ArrowLeft") {
          targetIndex = (index - 1 + jumpButtons.length) % jumpButtons.length;
        } else if (key === "Home") {
          targetIndex = 0;
        } else if (key === "End") {
          targetIndex = jumpButtons.length - 1;
        }
        const targetButton = jumpButtons[targetIndex];
        if (!targetButton) return;
        targetButton.focus();
        targetButton.click();
      });
    });
  }

  const openItemByHash = (scrollIntoView = false) => {
    const hashId = window.location.hash ? window.location.hash.replace("#", "") : "";
    const hashItem = hashId ? items.find((item) => item.id === hashId) : null;
    if (!hashItem) return false;
    setOpenItem(hashItem, { updateHash: false, scrollIntoView });
    return true;
  };

  window.addEventListener("hashchange", () => {
    openItemByHash(false);
  });

  if (!openItemByHash(false) && items.length > 0) {
    const openItem = items.find((item) => item.classList.contains("is-open")) || items[0];
    setOpenItem(openItem, { updateHash: false, scrollIntoView: false });
  }
}

/** Slide trang chủ — chuyển slide, autoplay, dừng khi hover */
function initHomeHeroSlider() {
  const root = document.querySelector("[data-home-slider]");
  const track = root?.querySelector("[data-home-slider-track]");
  const dotsRoot = root?.querySelector("[data-home-slider-dots]");
  const prevBtn = root?.querySelector("[data-home-slider-prev]");
  const nextBtn = root?.querySelector("[data-home-slider-next]");
  if (!root || !track || !dotsRoot || !prevBtn || !nextBtn) return;
  const slides = [...track.querySelectorAll(".home-slider-slide")];
  if (slides.length === 0) return;

  let idx = 0;
  let timer = 0;
  const AUTO_MS = 5000;
  const prefersReduce = window.matchMedia("(prefers-reduced-motion: reduce)");
  /** @type {HTMLButtonElement[]} */
  const dotButtons = [];

  function ensureHeroVideoLoaded(video) {
    if (!video?.hasAttribute("data-lazy-video")) return;
    const source = video.querySelector("source[data-src]");
    if (!source || source.getAttribute("src")) return;
    source.src = source.getAttribute("data-src") || "";
    source.removeAttribute("data-src");
    video.load();
  }

  function syncHeroVideos(activeIdx) {
    slides.forEach((slide, i) => {
      const video = slide.querySelector(".home-slide-video");
      if (!video) return;
      if (i === activeIdx && !prefersReduce.matches) {
        ensureHeroVideoLoaded(video);
        const playPromise = video.play();
        if (playPromise?.catch) playPromise.catch(() => {});
      } else {
        video.pause();
      }
    });
  }

  function goTo(nextIdx) {
    const n = slides.length;
    idx = ((nextIdx % n) + n) % n;
    track.style.transform = `translate3d(-${idx * 100}%, 0, 0)`;
    slides.forEach((slide, i) => {
      slide.classList.toggle("is-active", i === idx);
      slide.setAttribute("aria-hidden", i === idx ? "false" : "true");
    });
    dotButtons.forEach((btn, i) => {
      const sel = i === idx;
      btn.classList.toggle("is-active", sel);
      btn.setAttribute("aria-selected", sel ? "true" : "false");
      btn.tabIndex = sel ? 0 : -1;
    });
    syncHeroVideos(idx);
  }

  slides.forEach((_, i) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "home-slider-dot";
    btn.setAttribute("role", "tab");
    btn.setAttribute("aria-label", `Slide ${i + 1} trong ${slides.length}`);
    btn.addEventListener("click", () => {
      goTo(i);
      scheduleAuto();
    });
    dotsRoot.appendChild(btn);
    dotButtons.push(btn);
  });

  function scheduleAuto() {
    window.clearInterval(timer);
    timer = 0;
    if (prefersReduce.matches || slides.length <= 1) return;
    timer = window.setInterval(() => goTo(idx + 1), AUTO_MS);
  }

  prevBtn.addEventListener("click", () => {
    goTo(idx - 1);
    scheduleAuto();
  });
  nextBtn.addEventListener("click", () => {
    goTo(idx + 1);
    scheduleAuto();
  });

  root.addEventListener("mouseenter", () => window.clearInterval(timer));
  root.addEventListener("mouseleave", () => scheduleAuto());

  root.addEventListener("keydown", (e) => {
    if (e.key === "ArrowLeft") {
      e.preventDefault();
      goTo(idx - 1);
      scheduleAuto();
    } else if (e.key === "ArrowRight") {
      e.preventDefault();
      goTo(idx + 1);
      scheduleAuto();
    }
  });

  track.style.transition = prefersReduce.matches ? "none" : "";
  slides.forEach((slide, i) => {
    slide.setAttribute("aria-hidden", i === 0 ? "false" : "true");
  });
  goTo(0);
  scheduleAuto();
}

initHomeHeroSlider();

function initPartnerLogoMarquee() {
  const partnerSlider = document.querySelector(".partner-slider");
  const partnerTrack = document.querySelector(".partner-slider-track");
  if (!partnerSlider || !partnerTrack) return;

  const prefersReduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (!prefersReduce) {
    const slides = [...partnerTrack.querySelectorAll(".partner-slide")];
    if (slides.length) {
      slides.forEach((slide) => {
        const clone = slide.cloneNode(true);
        clone.setAttribute("aria-hidden", "true");
        clone.setAttribute("tabindex", "-1");
        partnerTrack.appendChild(clone);
      });
    }
  }

  partnerSlider.addEventListener("focusin", () => {
    partnerTrack.classList.add("is-paused");
  });
  partnerSlider.addEventListener("focusout", (event) => {
    const next = event.relatedTarget;
    if (next instanceof Node && partnerSlider.contains(next)) return;
    partnerTrack.classList.remove("is-paused");
  });
}

initPartnerLogoMarquee();

const contactForm = document.getElementById("contact-form");
if (contactForm) {
  const submitBtn = document.getElementById("contact-submit");
  const labelEl = submitBtn?.querySelector(".contact-submit-label");
  const defaultLabel = labelEl ? labelEl.textContent : "Gửi tới PTT Advertising Solutions";
  const endpoint = contactForm.getAttribute("data-landing-contact");
  const toastEl = document.getElementById("landing-toast");

  function setToast(message, isError) {
    if (!toastEl) {
      if (isError) window.alert(message);
      return;
    }
    toastEl.textContent = message;
    toastEl.hidden = false;
    toastEl.classList.remove("is-error");
    if (isError) toastEl.classList.add("is-error");
    toastEl.classList.add("is-visible");
    window.clearTimeout(setToast._t);
    setToast._t = window.setTimeout(() => {
      toastEl.classList.remove("is-visible");
      window.setTimeout(() => {
        toastEl.hidden = true;
      }, 220);
    }, 5200);
  }

  function setLoading(loading) {
    if (!submitBtn) return;
    submitBtn.disabled = loading;
    if (labelEl) labelEl.textContent = loading ? "Đang gửi…" : defaultLabel;
  }

  contactForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (!endpoint) {
      setToast("Thiếu cấu hình gửi form. Vui lòng tải lại trang.", true);
      return;
    }
    const elName = document.getElementById("contact-name");
    const elEmail = document.getElementById("contact-email");
    const elPhone = document.getElementById("contact-tel");
    const elBudget = document.getElementById("contact-budget");
    const elCompany = document.getElementById("contact-company");
    const elGoal = document.getElementById("contact-goal");
    const elHelp = document.getElementById("contact-help");
    const elAdditional = document.getElementById("contact-additional");
    const name = elName && "value" in elName ? String(elName.value).trim() : "";
    const email = elEmail && "value" in elEmail ? String(elEmail.value).trim() : "";
    const phone = elPhone && "value" in elPhone ? String(elPhone.value).trim() : "";
    const budget = elBudget && "value" in elBudget ? String(elBudget.value).trim() : "";
    const company = elCompany && "value" in elCompany ? String(elCompany.value).trim() : "";
    if (!name || !email || !phone || !budget || !company) {
      setToast("Vui lòng điền đủ các trường bắt buộc (*).", true);
      return;
    }
    const goal = elGoal && "value" in elGoal ? String(elGoal.value).trim() : "";
    const helpRequest = elHelp && "value" in elHelp ? String(elHelp.value).trim() : "";
    const additionalInfo =
      elAdditional && "value" in elAdditional ? String(elAdditional.value).trim() : "";
    setLoading(true);
    try {
      const res = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({
          form_type: "full",
          name,
          email,
          phone,
          budget,
          company,
          goal,
          help_request: helpRequest,
          additional_info: additionalInfo,
        }),
        credentials: "same-origin",
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        setToast((data && data.error) || "Không gửi được. Vui lòng thử lại.", true);
        return;
      }
      if (data && data.ok) {
        if (data.emailed === false && data.message) {
          setToast(data.message, false);
        } else {
          setToast("Cảm ơn bạn! Chúng tôi đã nhận thông tin và sẽ phản hồi sớm.", false);
        }
        contactForm.reset();
      } else {
        setToast((data && data.error) || "Có lỗi xảy ra. Vui lòng thử lại.", true);
      }
    } catch (err) {
      setToast("Lỗi mạng hoặc máy chủ. Kiểm tra kết nối và thử lại.", true);
    } finally {
      setLoading(false);
    }
  });
}
