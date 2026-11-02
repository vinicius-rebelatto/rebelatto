/* Animações dos templates de estética: revelar ao rolar, cursor, ímã, brilho,
   parallax e um efeito-assinatura por template. Tudo respeita
   prefers-reduced-motion e só liga efeitos de mouse em ponteiro fino. */
(function () {
  "use strict";

  var root = document.documentElement;
  var slug = root.getAttribute("data-motion") || "";
  var reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var finePointer = window.matchMedia("(hover: hover) and (pointer: fine)").matches;

  function done() { root.classList.remove("mo-preload"); }
  if (reduce || !("IntersectionObserver" in window)) { done(); return; }

  /* ------------------------------------------------------------------ */
  /* Personalidade de cada template                                       */
  /* ------------------------------------------------------------------ */
  var CFG = {
    consultorio: {
      reveal: "blur", cursor: "glow", split: "h1, .block__head h2, .visit h2",
      tilt: ".steps article, .window",
      spot: ".list > li, .strip__row p, .pg-card, .pg-valores li, .pg-steps li",
      layers: [
        { s: ".panel__light", mx: 46, my: 32, sy: -0.06 },
        { s: ".panel__arch", mx: -16, my: -10, sy: 0.04 },
        { s: ".window__glow", mx: 70, my: 40 },
        { s: ".window__mullion", mx: -8, my: -4 }
      ]
    },
    luxo: {
      reveal: "mask", cursor: "ring", split: "h1, h2",
      spot: ".list > li, .rules article, .pg-card, .pg-valores li, .facts > div",
      layers: [
        { s: ".void__ring", mx: 34, my: 26, rot: 0.06 },
        { s: ".hero__aside", sy: -0.18 },
        { s: ".hero h1", sy: 0.08 }
      ]
    },
    harmonizacao: {
      reveal: "up", cursor: "ring", cross: ".hero", split: "h1, .block h2, .rail h2, .visit h2",
      tilt: ".contour",
      spot: ".points > div, .split__copy p, .pg-card, .pg-valores li, .pg-exp__item",
      fill: { list: ".stages", items: ".stages li" },
      draw: ".contour path",
      layers: [{ s: ".hero__copy", sy: 0.06 }]
    },
    agenda: {
      reveal: "up", cursor: "glow", split: "h1, .visit h2, .prep h2",
      tilt: ".chat, .prep__card, .visit__card",
      spot: ".steps__row li, .pg-valores li, .pg-exp__item, .prep__cta",
      chat: true,
      layers: [{ s: ".chat", sy: -0.05 }]
    },
    cartao: {
      reveal: "scale", cursor: "ring", split: ".pg h2",
      tilt: ".card", tiltMax: 9,
      spot: ".pg-exp__item, .pg-steps li",
      layers: [
        { s: ".card--front", mx: -14, my: -10 },
        { s: ".card--back", mx: 16, my: 12, sy: 0.05 }
      ]
    },
    revista: {
      reveal: "clip", cursor: "ring", split: "h1, .story h2, .proc h2, .service h2",
      tilt: ".cover__art",
      spot: ".proc__item, .index li, .facts > div",
      scrub: ".pull",
      layers: [
        { s: ".masthead__name", sx: -0.35 },
        { s: ".issue", sx: 0.12 },
        { s: ".art__sun", mx: 22, my: 18, sy: -0.08 },
        { s: ".art__type", mx: -26, my: -16 },
        { s: ".art__line--a", mx: 10, my: 0 },
        { s: ".art__line--b", mx: 18, my: 0 }
      ]
    },
    retrato: {
      reveal: "blur", cursor: "glow", split: "h1, .section__head h2, .contact h2",
      spot: ".pcard, .facts > div, .pg-card, .pg-faq details",
      drag: ".cards__track",
      fill: { list: ".timeline", items: ".timeline li" },
    },
    minima: {
      reveal: "up", cursor: "ring", chars: ".one__name", split: ".index h2",
      spot: ".manifesto > div, .pg-card",
      layers: [{ s: ".one__line", mx: -10, my: -6 }]
    },
    acolhedora: {
      reveal: "pop", cursor: "glow", split: "h1, .block__head h2, .contact h2",
      tilt: ".care__item, .contact__card", tiltMax: 6,
      spot: ".journey li, .faq details, .pg-card, .pg-valores li",
      layers: [
        { s: ".blob--a", mx: 44, my: 30, sy: -0.12 },
        { s: ".blob--b", mx: -34, my: -22, sy: 0.08 },
        { s: ".blob--c", mx: 22, my: -36, sy: -0.04 },
        { s: ".blobs__word", mx: -16, my: -10 }
      ]
    },
    clinica: {
      reveal: "up", cursor: "", split: "h1, .block h2",
      tilt: ".info", tiltMax: 5,
      spot: ".grid > li, .compare, .pg-card, .pg-valores li, .pg-exp__item",
      map: true,
      layers: [{ s: ".info", mx: -10, my: -8 }]
    }
  };
  var cfg = CFG[slug] || { reveal: "up", split: "h1" };
  root.setAttribute("data-mo-style", cfg.reveal);

  function $$(sel, ctx) { return sel ? Array.prototype.slice.call((ctx || document).querySelectorAll(sel)) : []; }
  function clamp(v, a, b) { return Math.max(a, Math.min(b, v)); }
  function lerp(a, b, t) { return a + (b - a) * t; }

  var main = document.querySelector("main") || document.body;
  var vh = window.innerHeight;
  var mouse = { x: window.innerWidth / 2, y: vh / 2, nx: 0, ny: 0, active: false };

  /* ------------------------------------------------------------------ */
  /* Títulos: palavra a palavra (ou letra a letra)                        */
  /* ------------------------------------------------------------------ */
  function split(el, chars) {
    var i = 0;
    var c = 0;
    (function walk(node) {
      Array.prototype.slice.call(node.childNodes).forEach(function (child) {
        if (child.nodeType === 1) {
          if (child.classList.contains("exemplo")) return;
          walk(child);
          return;
        }
        if (child.nodeType !== 3 || !child.nodeValue.trim()) return;
        var frag = document.createDocumentFragment();
        child.nodeValue.split(/(\s+)/).forEach(function (part) {
          if (!part) return;
          if (/^\s+$/.test(part)) { frag.appendChild(document.createTextNode(" ")); return; }
          var w = document.createElement("span");
          w.className = "mo-w";
          var wi = document.createElement("span");
          wi.className = "mo-wi";
          wi.style.setProperty("--i", i++);
          if (chars) {
            w.style.overflow = "visible";
            part.split("").forEach(function (ch) {
              var s = document.createElement("span");
              s.className = "mo-c";
              s.style.setProperty("--i", c++);
              s.textContent = ch;
              wi.appendChild(s);
            });
          } else {
            wi.textContent = part;
          }
          w.appendChild(wi);
          frag.appendChild(w);
        });
        child.parentNode.replaceChild(frag, child);
      });
    })(el);
    if (!el.hasAttribute("aria-label") && el.textContent) el.setAttribute("aria-label", el.textContent.replace(/\s+/g, " ").trim());
    el.classList.add("mo-split");
    if (chars) el.classList.add("mo-chars");
    el.setAttribute("data-mo", "");
  }

  $$(cfg.chars, main).forEach(function (el) { split(el, true); });
  $$(cfg.split, main).forEach(function (el) {
    if (el.closest(".mo-split") || el.closest(".pg-exp__item")) return;
    split(el, false);
  });

  /* ------------------------------------------------------------------ */
  /* Revelar ao rolar                                                     */
  /* ------------------------------------------------------------------ */
  var CANDIDATES = [
    "[class*='__actions']", "[class*='__head']", ".pg-trilha", ".cards__track",
    "h1", "h2", "h3", "h4", "p", "li", "article", "figure", "blockquote", "details",
    "dl > div", "tr", "aside", ".btn", "img", ".manifesto > div", ".points > div"
  ].join(",");
  var SKIP = ".chat, .visually-hidden, .skip, .bar, .one__top, [hidden]";

  var targets = [];
  $$(CANDIDATES, main).forEach(function (el) {
    if (el.hasAttribute("data-mo") && !el.classList.contains("mo-split")) return;
    if (el.closest(SKIP)) return;
    var parent = el.parentElement && el.parentElement.closest("[data-mo]");
    if (parent) return;
    if (el.classList.contains("mo-split")) { targets.push(el); return; }
    if (el.matches("[class*='__head']") && el.querySelector(".mo-split")) return;
    el.setAttribute("data-mo", "");
    targets.push(el);
  });
  // Cabeçalhos com título dividido: revela os irmãos individualmente
  $$("[class*='__head'] > *:not([data-mo]), .pg-ls__head > div > *", main).forEach(function (el) {
    if (el.closest("[data-mo]") || el.closest(SKIP)) return;
    el.setAttribute("data-mo", "");
    targets.push(el);
  });

  // Títulos divididos dentro de um bloco que já revela: também precisam entrar
  $$(".mo-split", main).forEach(function (el) { if (targets.indexOf(el) < 0) targets.push(el); });

  // Alternância esquerda/direita em listas de etapas (dá ritmo)
  $$(".steps article, .journey li, .rules article, .stages li, .timeline li", main).forEach(function (el, i) {
    if (cfg.reveal === "up" || cfg.reveal === "blur") { if (i % 2 === 0) el.classList.add("mo-from-left"); }
  });

  var pending = [];
  var flushQueued = false;
  function flush() {
    flushQueued = false;
    pending.sort(function (a, b) {
      var ra = a.getBoundingClientRect(), rb = b.getBoundingClientRect();
      return (ra.top - rb.top) || (ra.left - rb.left);
    });
    pending.forEach(function (el, i) {
      el.style.setProperty("--mo-d", Math.min(i * 90, 720) + "ms");
      el.classList.add("is-in");
    });
    pending = [];
  }
  var io = new IntersectionObserver(function (entries) {
    entries.forEach(function (e) {
      if (!e.isIntersecting) return;
      io.unobserve(e.target);
      pending.push(e.target);
    });
    if (pending.length && !flushQueued) { flushQueued = true; requestAnimationFrame(flush); }
  }, { rootMargin: "0px 0px -8% 0px", threshold: 0 });

  targets.forEach(function (el) {
    io.observe(el);
    if (el.classList.contains("mo-split")) return;
    el.addEventListener("animationend", function end(e) {
      if (e.target !== el) return;
      el.classList.add("is-done");
      el.classList.remove("is-in");
      el.removeEventListener("animationend", end);
    });
  });

  /* ------------------------------------------------------------------ */
  /* Números que contam ao aparecer                                       */
  /* ------------------------------------------------------------------ */
  var COUNT = ".list__n, .index__n, .proc__num, .pg-valores__n, .pg-steps__n, .steps__row li > span, .journey li > span, .rules article > span, .steps article > span, .stages span";
  var counters = $$(COUNT, main).filter(function (el) {
    var t = el.textContent.trim();
    return /^\d{1,3}$/.test(t) && parseInt(t, 10) > 0;
  });
  var romans = $$(".rules article > span, .steps article > span", main).filter(function (el) {
    return /^[IVX]+$/.test(el.textContent.trim());
  });
  var cio = new IntersectionObserver(function (entries) {
    entries.forEach(function (e) {
      if (!e.isIntersecting) return;
      cio.unobserve(e.target);
      var el = e.target;
      var txt = el.textContent.trim();
      if (/^[IVX]+$/.test(txt)) {
        el.textContent = "";
        setTimeout(function () {
          txt.split("").forEach(function (ch, i) { setTimeout(function () { el.textContent += ch; }, i * 160); });
        }, 300);
        return;
      }
      var to = parseInt(txt, 10);
      var pad = txt.length;
      var t0 = performance.now() + 250;
      var dur = 700 + to * 60;
      el.classList.add("mo-count");
      (function tick(now) {
        var p = clamp((now - t0) / dur, 0, 1);
        var v = Math.round(to * (1 - Math.pow(1 - p, 3)));
        el.textContent = String(v).padStart(pad, "0");
        if (p < 1) requestAnimationFrame(tick);
      })(performance.now());
    });
  }, { threshold: 0.6 });
  counters.concat(romans).forEach(function (el) { if (el.offsetParent) cio.observe(el); });

  /* ------------------------------------------------------------------ */
  /* Barra de progresso                                                   */
  /* ------------------------------------------------------------------ */
  var bar = document.createElement("div");
  bar.className = "mo-progress";
  bar.setAttribute("aria-hidden", "true");
  document.body.appendChild(bar);

  /* ------------------------------------------------------------------ */
  /* Camadas de parallax (rolagem + mouse)                                */
  /* ------------------------------------------------------------------ */
  var layers = [];
  (cfg.layers || []).forEach(function (L) {
    $$(L.s).forEach(function (el) {
      if (L.mx && !finePointer && !L.sy && !L.sx && !L.rot) return;
      layers.push({ el: el, L: L, x: 0, y: 0, r: 0 });
    });
  });

  /* ------------------------------------------------------------------ */
  /* Brilho que segue o mouse e cartões em 3D                             */
  /* ------------------------------------------------------------------ */
  var tilts = [];
  function addGlare(el) {
    if (el.querySelector(":scope > .mo-glare")) return;
    if (getComputedStyle(el).position === "static") el.style.position = "relative";
    var g = document.createElement("span");
    g.className = "mo-glare";
    g.setAttribute("aria-hidden", "true");
    el.appendChild(g);
  }
  if (finePointer) {
    var max = cfg.tiltMax || 8;
    $$(cfg.tilt).forEach(function (el) {
      el.setAttribute("data-mo-tilt", "");
      addGlare(el);
      var t = { el: el, rx: 0, ry: 0, tx: 0, ty: 0 };
      tilts.push(t);
      el.addEventListener("pointermove", function (e) {
        var r = el.getBoundingClientRect();
        var px = (e.clientX - r.left) / r.width;
        var py = (e.clientY - r.top) / r.height;
        t.ty = (px - 0.5) * 2 * max;
        t.tx = (0.5 - py) * 2 * max;
        el.style.setProperty("--mx", px * 100 + "%");
        el.style.setProperty("--my", py * 100 + "%");
        el.style.setProperty("--go", "1");
        kick();
      });
      el.addEventListener("pointerleave", function () {
        t.tx = 0; t.ty = 0;
        el.style.setProperty("--go", "0");
        kick();
      });
    });
    $$(cfg.spot).forEach(function (el) {
      if (el.closest("[data-mo-tilt]")) return;
      el.setAttribute("data-mo-spot", "");
      addGlare(el);
      el.addEventListener("pointermove", function (e) {
        var r = el.getBoundingClientRect();
        el.style.setProperty("--mx", (e.clientX - r.left) + "px");
        el.style.setProperty("--my", (e.clientY - r.top) + "px");
        el.style.setProperty("--go", "1");
      });
      el.addEventListener("pointerleave", function () { el.style.setProperty("--go", "0"); });
    });

  }

  /* ------------------------------------------------------------------ */
  /* Botões: brilho, ímã e ondinha no clique                              */
  /* ------------------------------------------------------------------ */
  $$(".btn").forEach(function (btn) {
    if (btn.closest(".rt-bar")) return;
    var s = document.createElement("span");
    s.className = "mo-shine";
    s.setAttribute("aria-hidden", "true");
    btn.insertBefore(s, btn.firstChild);
    btn.addEventListener("pointerdown", function (e) {
      var r = btn.getBoundingClientRect();
      var rp = document.createElement("span");
      rp.className = "mo-ripple";
      rp.style.left = (e.clientX - r.left) + "px";
      rp.style.top = (e.clientY - r.top) + "px";
      btn.appendChild(rp);
      setTimeout(function () { rp.remove(); }, 750);
    });
    if (!finePointer) return;
    btn.addEventListener("pointermove", function (e) {
      var r = btn.getBoundingClientRect();
      var dx = e.clientX - (r.left + r.width / 2);
      var dy = e.clientY - (r.top + r.height / 2);
      btn.classList.add("mo-mag");
      btn.style.translate = (dx * 0.28).toFixed(1) + "px " + (dy * 0.38).toFixed(1) + "px";
    });
    btn.addEventListener("pointerleave", function () { btn.style.translate = ""; });
  });

  /* ------------------------------------------------------------------ */
  /* Cursores                                                             */
  /* ------------------------------------------------------------------ */
  var cursor = null;
  var cur = { x: mouse.x, y: mouse.y };
  var cross = null;
  var crossZone = cfg.cross ? document.querySelector(cfg.cross) : null;
  if (finePointer && cfg.cursor) {
    cursor = document.createElement("div");
    cursor.className = cfg.cursor === "glow" ? "mo-glow" : "mo-cursor";
    cursor.setAttribute("aria-hidden", "true");
    document.body.appendChild(cursor);
    if (cfg.cursor === "ring") {
      document.addEventListener("pointerover", function (e) {
        var hit = e.target.closest && e.target.closest("a, button, summary, [data-mo-tilt], [data-mo-spot], .cards__track");
        cursor.classList.toggle("is-hover", !!hit);
      });
      document.addEventListener("pointerdown", function () { cursor.classList.add("is-down"); });
      document.addEventListener("pointerup", function () { cursor.classList.remove("is-down"); });
    }
  }
  if (finePointer && crossZone) {
    cross = document.createElement("div");
    cross.className = "mo-cross";
    cross.setAttribute("aria-hidden", "true");
    cross.innerHTML = '<i class="h"></i><i class="v"></i><b></b>';
    document.body.appendChild(cross);
    crossZone.addEventListener("pointerenter", function () { cross.classList.add("is-on"); });
    crossZone.addEventListener("pointerleave", function () { cross.classList.remove("is-on"); });
  }

  /* ------------------------------------------------------------------ */
  /* Assinaturas por template                                             */
  /* ------------------------------------------------------------------ */

  // Harmonização: o contorno do rosto se desenha
  $$(cfg.draw).forEach(function (p, i) {
    var len = Math.ceil(p.getTotalLength ? p.getTotalLength() : 400);
    p.style.setProperty("--len", len);
    p.style.setProperty("--i", i);
  });
  if (cfg.draw) {
    var fig = document.querySelector(".contour");
    if (fig) setTimeout(function () { fig.classList.add("is-drawn"); }, 250);
  }

  // Linha que preenche com a rolagem (Harmonização e Retrato)
  var fill = null;
  if (cfg.fill) {
    var list = document.querySelector(cfg.fill.list);
    if (list) {
      var f = document.createElement("span");
      f.className = "mo-fill";
      f.setAttribute("aria-hidden", "true");
      list.appendChild(f);
      fill = { list: list, el: f, items: $$(cfg.fill.items, list) };
    }
  }

  // Revista: citação acende palavra por palavra
  var scrubs = [];
  $$(cfg.scrub).forEach(function (el) {
    var words = el.textContent.trim().split(/\s+/);
    el.setAttribute("aria-label", el.textContent.trim());
    el.innerHTML = words.map(function (w) { return '<span class="mo-sw" aria-hidden="true">' + w.replace(/</g, "&lt;") + "</span>"; }).join(" ");
    el.classList.add("mo-scrub");
    scrubs.push({ el: el, words: $$(".mo-sw", el) });
  });

  // Agenda: a conversa acontece na tela
  if (cfg.chat) {
    var chat = document.querySelector(".chat");
    var body = chat && chat.querySelector(".chat__body");
    if (body) {
      var msgs = $$(".msg", body);
      if (getComputedStyle(body).position === "static") body.style.position = "relative";
      msgs.forEach(function (m) { m.classList.add("mo-wait"); });
      var played = false;
      var chatIo = new IntersectionObserver(function (es) {
        if (!es[0].isIntersecting || played) return;
        played = true;
        chatIo.disconnect();
        var t = 400;
        msgs.forEach(function (m) {
          var incoming = m.classList.contains("msg--in");
          if (incoming) {
            (function (at) {
              setTimeout(function () {
                var typing = document.createElement("p");
                typing.className = "msg msg--in mo-typing";
                typing.setAttribute("aria-hidden", "true");
                typing.innerHTML = "<i></i><i></i><i></i>";
                typing.style.top = m.offsetTop + "px";
                typing.style.left = m.offsetLeft + "px";
                body.appendChild(typing);
                setTimeout(function () { typing.remove(); }, 1100);
              }, at);
            })(t);
            t += 1100;
          } else {
            t += 500;
          }
          (function (at) {
            setTimeout(function () { m.classList.remove("mo-wait"); m.classList.add("mo-show"); }, at);
          })(t);
          t += 650;
        });
      }, { threshold: 0.4 });
      chatIo.observe(chat);
    }
  }

  // Retrato: arrastar o carrossel com o mouse
  $$(cfg.drag).forEach(function (track) {
    if (!finePointer) return;
    var down = false, moved = false, sx = 0, sl = 0, v = 0, lastX = 0;
    track.addEventListener("pointerdown", function (e) {
      if (e.pointerType !== "mouse") return;
      down = true; moved = false; sx = lastX = e.clientX; sl = track.scrollLeft; v = 0;
    });
    window.addEventListener("pointermove", function (e) {
      if (!down) return;
      var dx = e.clientX - sx;
      if (Math.abs(dx) > 4) { moved = true; track.classList.add("is-drag"); }
      v = e.clientX - lastX; lastX = e.clientX;
      track.scrollLeft = sl - dx;
    });
    window.addEventListener("pointerup", function () {
      if (!down) return;
      down = false;
      (function glide() {
        v *= 0.92;
        track.scrollLeft -= v;
        if (Math.abs(v) > 0.5) requestAnimationFrame(glide);
        else track.classList.remove("is-drag");
      })();
    });
    track.addEventListener("click", function (e) { if (moved) { e.preventDefault(); moved = false; } }, true);
  });

  // Clínica: mapa se desenha e o pino cai
  if (cfg.map) {
    var map = document.querySelector(".map");
    if (map) {
      var mio = new IntersectionObserver(function (es) {
        if (es[0].isIntersecting) { map.classList.add("is-in"); mio.disconnect(); }
      }, { threshold: 0.3 });
      mio.observe(map);
    }
  }

  // Mínima: letras do nome reagem à proximidade do cursor
  var letters = finePointer ? $$(".mo-chars .mo-c") : [];

  /* ------------------------------------------------------------------ */
  /* Laço de animação (só roda enquanto há movimento)                     */
  /* ------------------------------------------------------------------ */
  var running = false;
  var smooth = { nx: 0, ny: 0 };
  function kick() { if (!running) { running = true; requestAnimationFrame(frame); } }

  function frame() {
    var busy = false;
    var sy = window.scrollY;
    var docH = document.documentElement.scrollHeight - vh;
    bar.style.transform = "scaleX(" + (docH > 0 ? clamp(sy / docH, 0, 1) : 0) + ")";
    if (sy >= docH - 4) {
      // fim da página: o que ainda estiver na tela aparece
      targets.forEach(function (el) {
        if (el.classList.contains("is-in") || el.classList.contains("is-done")) return;
        if (el.getBoundingClientRect().top < vh) { io.unobserve(el); pending.push(el); }
      });
      if (pending.length && !flushQueued) { flushQueued = true; requestAnimationFrame(flush); }
    }

    smooth.nx = lerp(smooth.nx, mouse.nx, 0.08);
    smooth.ny = lerp(smooth.ny, mouse.ny, 0.08);
    if (Math.abs(smooth.nx - mouse.nx) > 0.001 || Math.abs(smooth.ny - mouse.ny) > 0.001) busy = true;

    layers.forEach(function (o) {
      var L = o.L;
      var r = o.el.getBoundingClientRect();
      var center = r.top + r.height / 2 - vh / 2 - o.y;
      var x = (L.mx || 0) * smooth.nx + (L.sx ? sy * L.sx : 0);
      var y = (L.my || 0) * smooth.ny + (L.sy ? center * L.sy : 0);
      if (L.sx) x = clamp(x, -window.innerWidth * 0.5, window.innerWidth * 0.5);
      o.y = y;
      o.el.style.translate = x.toFixed(1) + "px " + y.toFixed(1) + "px";
      if (L.rot) o.el.style.rotate = (sy * L.rot).toFixed(1) + "deg";
    });

    tilts.forEach(function (t) {
      t.rx = lerp(t.rx, t.tx, 0.12);
      t.ry = lerp(t.ry, t.ty, 0.12);
      if (Math.abs(t.rx - t.tx) > 0.02 || Math.abs(t.ry - t.ty) > 0.02) busy = true;
      if (slug === "cartao") {
        t.el.style.setProperty("--rx", t.rx.toFixed(2) + "deg");
        t.el.style.setProperty("--ry", t.ry.toFixed(2) + "deg");
      } else {
        t.el.style.transform = "perspective(1000px) rotateX(" + t.rx.toFixed(2) + "deg) rotateY(" + t.ry.toFixed(2) + "deg)";
      }
    });

    if (cursor) {
      var k = cursor.classList.contains("mo-glow") ? 0.09 : 0.2;
      cur.x = lerp(cur.x, mouse.x, k);
      cur.y = lerp(cur.y, mouse.y, k);
      if (Math.abs(cur.x - mouse.x) > 0.3 || Math.abs(cur.y - mouse.y) > 0.3) busy = true;
      cursor.style.transform = "translate3d(" + cur.x.toFixed(1) + "px," + cur.y.toFixed(1) + "px,0)";
    }
    if (cross && cross.classList.contains("is-on")) {
      cross.children[0].style.top = mouse.y + "px";
      cross.children[1].style.left = mouse.x + "px";
      var b = cross.children[2];
      b.style.left = mouse.x + "px";
      b.style.top = mouse.y + "px";
      b.textContent = "x " + Math.round(mouse.x / window.innerWidth * 100) + " · y " + Math.round(mouse.y / vh * 100);
    }

    if (fill) {
      var fr = fill.list.getBoundingClientRect();
      var p = clamp((vh * 0.75 - fr.top) / (fr.height || 1), 0, 1);
      fill.list.style.setProperty("--p", p.toFixed(3));
      fill.items.forEach(function (li) {
        li.classList.toggle("is-reached", li.getBoundingClientRect().top < vh * 0.75);
      });
    }

    scrubs.forEach(function (s) {
      var r = s.el.getBoundingClientRect();
      var p = clamp((vh * 0.85 - r.top) / (vh * 0.5), 0, 1);
      var n = Math.round(p * s.words.length);
      s.words.forEach(function (w, i) { w.classList.toggle("is-lit", i < n); });
    });

    if (letters.length && mouse.active) {
      letters.forEach(function (l) {
        var r = l.getBoundingClientRect();
        var dx = mouse.x - (r.left + r.width / 2);
        var dy = mouse.y - (r.top + r.height / 2);
        var d = Math.sqrt(dx * dx + dy * dy);
        var f = clamp(1 - d / 260, 0, 1);
        f = f * f;
        l.style.translate = "0 " + (-f * 0.16).toFixed(3) + "em";
        l.style.color = f > 0.35 ? "var(--muted)" : "";
      });
    }

    if (busy) requestAnimationFrame(frame);
    else running = false;
  }

  window.addEventListener("scroll", kick, { passive: true });
  window.addEventListener("resize", function () { vh = window.innerHeight; kick(); });
  if (finePointer) {
    window.addEventListener("pointermove", function (e) {
      mouse.x = e.clientX;
      mouse.y = e.clientY;
      mouse.nx = e.clientX / window.innerWidth - 0.5;
      mouse.ny = e.clientY / vh - 0.5;
      mouse.active = true;
      if (cursor) cursor.classList.add("is-on");
      kick();
    }, { passive: true });
    document.addEventListener("pointerleave", function () {
      if (cursor) cursor.classList.remove("is-on");
      mouse.active = false;
      letters.forEach(function (l) { l.style.translate = ""; l.style.color = ""; });
    });
  }

  kick();
  done();
})();
