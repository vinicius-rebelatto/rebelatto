/* Vitrine da home: troca o estilo na prévia com uma cortina na cor do site,
   rola a captura ao passar o mouse e avança sozinha enquanto ninguém mexe. */
(function () {
  "use strict";

  var stage = document.querySelector("[data-vitrine]");
  if (!stage) return;

  var reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var items = Array.prototype.slice.call(stage.querySelectorAll("[data-vt-item]"));
  if (!items.length) return;

  var desk = stage.querySelector("[data-vt-desktop]");
  var mob = stage.querySelector("[data-vt-mobile]");
  var wipe = stage.querySelector("[data-vt-wipe]");
  var wipeNome = stage.querySelector("[data-vt-wipe-nome]");
  var info = stage.querySelector(".vitrine-info");
  var opens = Array.prototype.slice.call(stage.querySelectorAll("[data-vt-open]"));
  var campos = {
    url: stage.querySelector("[data-vt-url]"),
    n: stage.querySelector("[data-vt-n]"),
    tipo: stage.querySelector("[data-vt-tipo]"),
    nome: stage.querySelector("[data-vt-nome]"),
    chamada: stage.querySelector("[data-vt-chamada]")
  };
  var atual = 0;
  var trocando = false;
  var AUTO = 5000;

  // Quanto a captura precisa subir para mostrar a página inteira no hover.
  function medir() {
    [[desk, "d"], [mob, "m"]].forEach(function (par) {
      var img = par[0];
      if (!img || !img.complete || !img.naturalWidth) return;
      var tela = img.parentElement.clientHeight;
      var alto = img.clientHeight;
      var shift = Math.min(0, tela - alto);
      stage.style.setProperty("--vt-shift-" + par[1], shift + "px");
      stage.style.setProperty("--vt-dur-" + par[1], Math.max(2, Math.abs(shift) / 260).toFixed(1) + "s");
    });
  }
  [desk, mob].forEach(function (img) { if (img) img.addEventListener("load", medir); });
  window.addEventListener("resize", medir);
  medir();

  function carregar(src) {
    return new Promise(function (ok) {
      var im = new Image();
      im.onload = im.onerror = function () { ok(); };
      im.src = src;
      if (im.decode) im.decode().then(ok, ok);
    });
  }

  function aplicar(i) {
    var b = items[i];
    items.forEach(function (el, k) { el.setAttribute("aria-pressed", k === i ? "true" : "false"); });
    desk.src = b.dataset.desktop;
    mob.src = b.dataset.mobile;
    desk.alt = "Prévia do estilo " + b.dataset.nome + " no computador";
    stage.style.setProperty("--vt-cor", b.dataset.fundo);
    campos.url.textContent = "rebelatto.tech/mockups/" + b.dataset.slug;
    campos.n.textContent = String(i + 1).padStart(2, "0");
    campos.tipo.textContent = b.dataset.tipo;
    campos.nome.textContent = b.dataset.nome;
    campos.chamada.textContent = b.dataset.chamada;
    opens.forEach(function (a) {
      a.href = b.dataset.url;
      if (a.hasAttribute("aria-label")) a.setAttribute("aria-label", "Abrir o estilo " + b.dataset.nome);
    });
    info.classList.remove("is-changing");
    void info.offsetWidth;
    info.classList.add("is-changing");
    atual = i;
    medir();
  }

  function ir(i, dir) {
    i = (i + items.length) % items.length;
    if (i === atual || trocando) return;
    var b = items[i];
    var pronto = Promise.all([carregar(b.dataset.desktop), carregar(b.dataset.mobile)]);
    if (reduce) { pronto.then(function () { aplicar(i); }); return; }

    trocando = true;
    wipe.setAttribute("data-dir", dir || (i > atual ? "next" : "prev"));
    wipe.style.setProperty("--vt-wipe", b.dataset.fundo);
    wipe.style.setProperty("--vt-wipe-tinta", b.dataset.tema === "dark" ? "#f4efe6" : "#1c1a18");
    wipeNome.textContent = b.dataset.nome;
    wipe.classList.remove("is-out");
    wipe.classList.add("is-in");
    Promise.all([pronto, new Promise(function (ok) { setTimeout(ok, 480); })]).then(function () {
      aplicar(i);
      setTimeout(function () {
        wipe.classList.remove("is-in");
        wipe.classList.add("is-out");
        setTimeout(function () { wipe.classList.remove("is-out"); trocando = false; }, 560);
      }, 140);
    });
  }

  // Avanço automático: só enquanto a vitrine está na tela e ninguém interagiu.
  var timer = null;
  var parado = reduce;
  var visivel = false;
  function agendar() {
    clearTimeout(timer);
    stage.classList.remove("is-auto");
    if (parado || !visivel) return;
    void stage.offsetWidth;
    stage.style.setProperty("--vt-auto", AUTO + "ms");
    stage.classList.add("is-auto");
    timer = setTimeout(function () { ir(atual + 1, "next"); setTimeout(agendar, 700); }, AUTO);
  }
  function parar() { parado = true; clearTimeout(timer); stage.classList.remove("is-auto"); }

  if ("IntersectionObserver" in window) {
    new IntersectionObserver(function (es) {
      visivel = es[0].isIntersecting;
      if (visivel) agendar(); else { clearTimeout(timer); stage.classList.remove("is-auto"); }
    }, { threshold: 0.45 }).observe(stage);
  }
  stage.addEventListener("pointerenter", function () { clearTimeout(timer); stage.classList.remove("is-auto"); });
  stage.addEventListener("pointerleave", agendar);

  items.forEach(function (b, i) {
    b.addEventListener("click", function () { parar(); ir(i); });
  });
  var prev = document.querySelector("[data-vt-prev]");
  var next = document.querySelector("[data-vt-next]");
  if (prev) prev.addEventListener("click", function () { parar(); ir(atual - 1, "prev"); });
  if (next) next.addEventListener("click", function () { parar(); ir(atual + 1, "next"); });

  // Pré-carrega as capturas depois que a página assentou.
  window.addEventListener("load", function () {
    setTimeout(function () {
      items.forEach(function (b) { carregar(b.dataset.desktop); carregar(b.dataset.mobile); });
    }, 1500);
  });
})();
