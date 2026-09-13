(function () {
  "use strict";

  var header = document.querySelector("[data-odo-header]");
  var toggle = document.querySelector("[data-odo-nav-toggle]");
  var drawer = document.querySelector("[data-odo-drawer]");

  function setScrolled() {
    if (!header) return;
    header.classList.toggle("is-scrolled", window.scrollY > 8);
  }

  function setDrawer(open) {
    if (!drawer || !toggle) return;
    drawer.hidden = !open;
    toggle.setAttribute("aria-expanded", open ? "true" : "false");
    toggle.setAttribute("aria-label", open ? "Fechar menu" : "Abrir menu");
  }

  setScrolled();
  window.addEventListener("scroll", setScrolled, { passive: true });

  if (toggle && drawer) {
    toggle.addEventListener("click", function () {
      setDrawer(drawer.hidden);
    });

    drawer.querySelectorAll("a[href^='#']").forEach(function (link) {
      link.addEventListener("click", function () {
        setDrawer(false);
      });
    });
  }
})();
