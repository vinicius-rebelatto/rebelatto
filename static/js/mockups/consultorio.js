(function () {
  "use strict";

  var bar = document.querySelector("[data-bar]");
  var menu = document.querySelector("[data-menu]");
  var drawer = document.querySelector("[data-drawer]");

  function onScroll() {
    if (!bar) return;
    bar.classList.toggle("is-scrolled", window.scrollY > 8);
  }

  function setOpen(open) {
    if (!drawer || !menu) return;
    drawer.hidden = !open;
    menu.setAttribute("aria-expanded", open ? "true" : "false");
    menu.setAttribute("aria-label", open ? "Fechar menu" : "Abrir menu");
  }

  onScroll();
  window.addEventListener("scroll", onScroll, { passive: true });

  if (menu && drawer) {
    menu.addEventListener("click", function () {
      setOpen(drawer.hidden);
    });
    drawer.querySelectorAll("a").forEach(function (link) {
      link.addEventListener("click", function () {
        setOpen(false);
      });
    });
  }
})();
