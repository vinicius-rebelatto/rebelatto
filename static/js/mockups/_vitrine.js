/* Provador: troca de estilo com cortina, atalhos de teclado e avisos da demonstração. */
(function () {
  "use strict";

  var root = document.documentElement;
  var reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // 1. Chegando de outro estilo: a cortina que cobriu a página sai de cena.
  var entrada = root.getAttribute("data-vt-enter");
  if (entrada) {
    var sair = function () {
      root.setAttribute("data-vt-leave", entrada);
      setTimeout(function () {
        root.removeAttribute("data-vt-enter");
        root.removeAttribute("data-vt-leave");
        root.removeAttribute("data-vt-nome");
      }, 800);
    };
    setTimeout(sair, reduce ? 0 : 160);
  }

  // 2. Indo para outro estilo: cobre a tela com a cor do próximo site e navega.
  var indo = false;
  function ir(link) {
    if (indo) return;
    indo = true;
    var dir = link.getAttribute("data-vt-go") === "prev" ? "prev" : "next";
    var dados = {
      nome: link.getAttribute("data-vt-nome") || "",
      fundo: link.getAttribute("data-vt-fundo") || "#111",
      tema: link.getAttribute("data-vt-tema") || "light",
      dir: dir,
      t: Date.now()
    };
    if (reduce) { window.location.href = link.href; return; }
    try { sessionStorage.setItem("vt-cortina", JSON.stringify(dados)); } catch (e) {}

    var c = document.createElement("div");
    c.className = "vt-curtain";
    c.setAttribute("data-dir", dir);
    c.setAttribute("aria-hidden", "true");
    c.style.setProperty("--vt-fundo", dados.fundo);
    c.style.setProperty("--vt-tinta", dados.tema === "dark" ? "#f4efe6" : "#1c1a18");
    c.innerHTML = "<small>Rebel Tech · Vitrine</small><span></span>";
    c.querySelector("span").textContent = dados.nome;
    document.body.appendChild(c);
    setTimeout(function () { window.location.href = link.href; }, 520);
    // Se o usuário voltar pelo histórico (bfcache), a página não pode ficar coberta.
    window.addEventListener("pageshow", function (e) { if (e.persisted) { c.remove(); indo = false; } }, { once: true });
  }

  document.addEventListener("click", function (e) {
    var link = e.target.closest && e.target.closest("a[data-vt-go]");
    if (!link || e.metaKey || e.ctrlKey || e.shiftKey || e.button !== 0) return;
    if (link.getAttribute("aria-current") === "page") { e.preventDefault(); return; }
    e.preventDefault();
    var menu = link.closest("details");
    if (menu) menu.open = false;
    ir(link);
  });

  // 3. Setas do teclado trocam de estilo.
  document.addEventListener("keydown", function (e) {
    if (e.altKey || e.ctrlKey || e.metaKey || e.shiftKey) return;
    if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
    var alvo = e.target;
    if (alvo && (alvo.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(alvo.tagName))) return;
    if (alvo && alvo.closest && alvo.closest(".cards__track, .compare__scroll")) return;
    var link = document.querySelector(e.key === "ArrowLeft"
      ? ".vt-bar__arrow[data-vt-go='prev'], .rt-bar__arrow[data-vt-go='prev']"
      : ".vt-bar__arrow[data-vt-go='next'], .rt-bar__arrow[data-vt-go='next']");
    if (!link) return;
    e.preventDefault();
    ir(link);
  });

  // 4. Barra pública: dica na primeira visita, menu que fecha fora e links de demonstração.
  var bar = document.querySelector(".vt-bar");
  if (!bar) return;

  var hint = bar.querySelector("[data-vt-hint]");
  try {
    if (hint && !sessionStorage.getItem("vt-dica")) {
      sessionStorage.setItem("vt-dica", "1");
      setTimeout(function () { hint.hidden = false; }, 1400);
      setTimeout(function () { hint.hidden = true; }, 6200);
    }
  } catch (e) {}

  var toast = document.querySelector("[data-vt-toast]");
  var timer;
  document.addEventListener("click", function (e) {
    var menu = bar.querySelector(".vt-bar__menu");
    if (menu && menu.open && !e.target.closest(".vt-bar__menu")) menu.open = false;
    var link = e.target.closest && e.target.closest("a");
    if (!link || link.hasAttribute("data-rt")) return;
    var href = link.getAttribute("href") || "";
    if (href.charAt(0) === "#" || (href.charAt(0) === "/" && href.charAt(1) !== "/")) return;
    e.preventDefault();
    if (!toast) return;
    toast.textContent = "Demonstração: no site real, este botão abre o WhatsApp da clínica.";
    toast.setAttribute("data-on", "");
    clearTimeout(timer);
    timer = setTimeout(function () { toast.removeAttribute("data-on"); }, 3200);
  });
})();
