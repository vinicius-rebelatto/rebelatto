(() => {
  const header = document.querySelector(".site-header");
  const drawer = document.querySelector("#nav-drawer");
  const toggle = document.querySelector(".nav-toggle");
  const form = document.querySelector("#contact-form");
  const statusEl = document.querySelector("#contact-status");
  const themeToggle = document.querySelector("[data-theme-toggle]");
  const THEME_KEY = "rebel-theme";

  function getTheme() {
    return document.documentElement.getAttribute("data-theme") === "dark"
      ? "dark"
      : "light";
  }

  function setTheme(theme) {
    const next = theme === "dark" ? "dark" : "light";
    document.documentElement.setAttribute("data-theme", next);
    try {
      localStorage.setItem(THEME_KEY, next);
    } catch (_err) {
      /* ignore */
    }
    if (themeToggle) {
      themeToggle.setAttribute(
        "aria-label",
        next === "dark" ? "Ativar tema claro" : "Ativar tema escuro"
      );
    }
  }

  themeToggle?.addEventListener("click", () => {
    setTheme(getTheme() === "dark" ? "light" : "dark");
  });
  setTheme(getTheme());

  function closeDrawer() {
    if (!drawer) return;
    drawer.hidden = true;
    document.body.classList.remove("nav-open");
    toggle?.setAttribute("aria-expanded", "false");
    toggle?.setAttribute("aria-label", "Abrir menu");
  }

  function openDrawer() {
    if (!drawer) return;
    drawer.hidden = false;
    document.body.classList.add("nav-open");
    toggle?.setAttribute("aria-expanded", "true");
    toggle?.setAttribute("aria-label", "Fechar menu");
  }

  function getCsrf() {
    const input = form?.querySelector("[name=csrfmiddlewaretoken]");
    return input ? input.value : "";
  }

  toggle?.addEventListener("click", () => {
    if (!drawer) return;
    if (drawer.hidden) openDrawer();
    else closeDrawer();
  });

  drawer?.querySelectorAll("a").forEach((el) => {
    el.addEventListener("click", () => {
      closeDrawer();
    });
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && drawer && !drawer.hidden) {
      closeDrawer();
    }
  });

  form?.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!form) return;

    form.querySelectorAll("[data-error-for]").forEach((el) => {
      el.textContent = "";
    });
    if (statusEl) statusEl.textContent = "Enviando...";

    try {
      const response = await fetch(form.action, {
        method: "POST",
        headers: {
          "X-CSRFToken": getCsrf(),
          Accept: "application/json",
        },
        body: new FormData(form),
      });

      const data = await response.json();

      if (!response.ok || !data.ok) {
        const errors = data.errors || {};
        Object.entries(errors).forEach(([field, message]) => {
          const target = form.querySelector(`[data-error-for="${field}"]`);
          if (target) target.textContent = message;
        });
        if (statusEl) statusEl.textContent = "Confira os campos e tente de novo.";
        return;
      }

      form.reset();
      if (statusEl) statusEl.textContent = data.message || "Enviado!";
    } catch (_err) {
      if (statusEl) statusEl.textContent = "Falha de conexão. Tente novamente.";
    }
  });

  const reveals = document.querySelectorAll(".reveal");
  if ("IntersectionObserver" in window) {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add("is-visible");
            observer.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.14 }
    );
    reveals.forEach((el) => observer.observe(el));
  } else {
    reveals.forEach((el) => el.classList.add("is-visible"));
  }

  const onScroll = () => {
    if (!header) return;
    header.style.boxShadow = window.scrollY > 8 ? "var(--scroll-shadow)" : "none";
  };
  window.addEventListener("scroll", onScroll, { passive: true });
  onScroll();

  function initProjectCarousel() {
    const root = document.querySelector("[data-project-carousel]");
    if (!root) return;

    const track = root.querySelector("[data-carousel-track]");
    const viewport = root.querySelector("[data-carousel-viewport]");
    const dotsRoot = root.querySelector("[data-carousel-dots]");
    const statusEl = root.querySelector("[data-carousel-status]");
    const prevBtn = document.querySelector("[data-carousel-prev]");
    const nextBtn = document.querySelector("[data-carousel-next]");
    const cards = Array.from(track?.querySelectorAll(".project-card") || []);

    if (!track || !viewport || cards.length === 0) return;

    let page = 0;
    let pageCount = 1;

    function perPage() {
      const raw = getComputedStyle(root).getPropertyValue("--project-per-page");
      const value = Number.parseInt(raw, 10);
      return Number.isFinite(value) && value > 0 ? value : 1;
    }

    function updatePageCount() {
      pageCount = Math.max(1, Math.ceil(cards.length / perPage()));
      page = Math.min(page, pageCount - 1);
    }

    function renderDots() {
      if (!dotsRoot) return;
      dotsRoot.innerHTML = "";
      for (let index = 0; index < pageCount; index += 1) {
        const dot = document.createElement("button");
        dot.type = "button";
        dot.className = "project-carousel-dot";
        dot.setAttribute("aria-label", `Ir para página ${index + 1}`);
        if (index === page) dot.setAttribute("aria-current", "true");
        dot.addEventListener("click", () => goTo(index));
        dotsRoot.appendChild(dot);
      }
    }

    function updateControls() {
      if (prevBtn) prevBtn.disabled = page <= 0;
      if (nextBtn) nextBtn.disabled = page >= pageCount - 1;
      if (statusEl) {
        statusEl.textContent =
          pageCount > 1
            ? `Página ${page + 1} de ${pageCount}`
            : `${cards.length} projeto${cards.length === 1 ? "" : "s"}`;
      }
      dotsRoot?.querySelectorAll(".project-carousel-dot").forEach((dot, index) => {
        if (index === page) dot.setAttribute("aria-current", "true");
        else dot.removeAttribute("aria-current");
      });
    }

    function goTo(nextPage) {
      updatePageCount();
      page = Math.max(0, Math.min(nextPage, pageCount - 1));
      const maxOffset = Math.max(0, track.scrollWidth - viewport.clientWidth);
      const offset = Math.min(page * viewport.clientWidth, maxOffset);
      track.style.transform = `translateX(-${offset}px)`;
      updateControls();
    }

    function refresh() {
      const previousCount = pageCount;
      updatePageCount();
      if (previousCount !== pageCount) renderDots();
      goTo(page);
    }

    prevBtn?.addEventListener("click", () => goTo(page - 1));
    nextBtn?.addEventListener("click", () => goTo(page + 1));

    viewport.addEventListener("keydown", (event) => {
      if (event.key === "ArrowLeft") {
        event.preventDefault();
        goTo(page - 1);
      }
      if (event.key === "ArrowRight") {
        event.preventDefault();
        goTo(page + 1);
      }
    });

    let touchStartX = 0;
    viewport.addEventListener(
      "touchstart",
      (event) => {
        touchStartX = event.changedTouches[0]?.clientX || 0;
      },
      { passive: true }
    );
    viewport.addEventListener(
      "touchend",
      (event) => {
        const delta = (event.changedTouches[0]?.clientX || 0) - touchStartX;
        if (Math.abs(delta) < 40) return;
        if (delta < 0) goTo(page + 1);
        else goTo(page - 1);
      },
      { passive: true }
    );

    window.addEventListener("resize", refresh);
    updatePageCount();
    renderDots();
    goTo(0);
  }

  initProjectCarousel();
})();
