(function () {
  "use strict";

  var PERSONAS = {
    rebel_tech: {
      title: "Assistente Rebel Tech",
      greeting:
        "Olá! Sou o assistente da Rebel Tech. Posso ajudar com dúvidas sobre desenvolvimento de software, orçamentos e como contratar. Como posso ajudar?",
      suggestions: [
        "Quais serviços vocês oferecem?",
        "Como funciona um orçamento?",
        "Quais tecnologias vocês usam?",
        "Como posso entrar em contato?",
      ],
      avatar: "R",
    },
    odontologia: {
      title: "Assistente Aurora",
      greeting:
        "Olá! Sou a assistente da Aurora Odontologia. Posso falar sobre tratamentos, horários e como agendar uma avaliação. Em que posso ajudar?",
      suggestions: [
        "Quais tratamentos vocês fazem?",
        "Qual o horário de atendimento?",
        "Onde fica a clínica?",
        "Como agendar uma avaliação?",
      ],
      avatar: "A",
    },
  };

  function ready(fn) {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", fn);
    } else {
      fn();
    }
  }

  function getCookie(name) {
    var match = document.cookie.match(new RegExp("(^|;\\s*)" + name + "=([^;]*)"));
    return match ? decodeURIComponent(match[2]) : "";
  }

  ready(function () {
    var root = document.querySelector("[data-chat-root]");
    if (!root) return;

    var personaId = root.getAttribute("data-chat-persona") || "rebel_tech";
    var persona = PERSONAS[personaId] || PERSONAS.rebel_tech;
    var endpoint = root.getAttribute("data-chat-endpoint") || "/chat/";
    var csrfInput = root.querySelector("[name=csrfmiddlewaretoken]");
    var toggle = root.querySelector("[data-chat-toggle]");
    var closeBtn = root.querySelector("[data-chat-close]");
    var panel = root.querySelector("[data-chat-panel]");
    var messagesEl = root.querySelector("[data-chat-messages]");
    var suggestionsEl = root.querySelector("[data-chat-suggestions]");
    var form = root.querySelector("[data-chat-form]");
    var input = root.querySelector("[data-chat-input]");
    var sendBtn = root.querySelector("[data-chat-send]");
    var titleEl = root.querySelector("[data-chat-title]");
    var avatarEl = root.querySelector(".rt-chat__avatar");

    var history = [];
    var busy = false;
    var bootstrapped = false;

    if (titleEl) titleEl.textContent = persona.title;
    if (avatarEl) avatarEl.textContent = persona.avatar;

    // Ensure closed on load (panel must stay hidden until user opens)
    if (panel) {
      panel.hidden = true;
      panel.setAttribute("hidden", "");
    }
    root.classList.remove("is-open");
    document.body.classList.remove("rt-chat-open");

    function getCsrf() {
      return (csrfInput && csrfInput.value) || getCookie("csrftoken") || "";
    }

    function isOpen() {
      return root.classList.contains("is-open");
    }

    function scrollToBottom() {
      if (!messagesEl) return;
      messagesEl.scrollTop = messagesEl.scrollHeight;
    }

    function appendBubble(role, text, extraClass) {
      var bubble = document.createElement("div");
      bubble.className =
        "rt-chat__bubble rt-chat__bubble--" +
        (role === "user" ? "user" : "bot") +
        (extraClass ? " " + extraClass : "");
      bubble.textContent = text;
      messagesEl.appendChild(bubble);
      scrollToBottom();
      return bubble;
    }

    function setTyping(on) {
      var existing = messagesEl.querySelector("[data-chat-typing]");
      if (existing) existing.remove();
      if (!on) return;
      var el = document.createElement("div");
      el.className = "rt-chat__typing";
      el.setAttribute("data-chat-typing", "");
      el.setAttribute("aria-label", "Digitando");
      el.innerHTML = "<span></span><span></span><span></span>";
      messagesEl.appendChild(el);
      scrollToBottom();
    }

    function renderSuggestions() {
      if (!suggestionsEl) return;
      suggestionsEl.innerHTML = "";
      persona.suggestions.forEach(function (label) {
        var chip = document.createElement("button");
        chip.type = "button";
        chip.className = "rt-chat__chip";
        chip.textContent = label;
        chip.addEventListener("click", function () {
          suggestionsEl.hidden = true;
          sendMessage(label);
        });
        suggestionsEl.appendChild(chip);
      });
      suggestionsEl.hidden = false;
    }

    function resizeInput() {
      if (!input) return;
      input.style.height = "auto";
      input.style.height = Math.min(input.scrollHeight, 112) + "px";
      if (sendBtn) sendBtn.disabled = busy || !input.value.trim();
    }

    function setOpen(open) {
      open = !!open;
      root.classList.toggle("is-open", open);
      document.body.classList.toggle("rt-chat-open", open);

      if (panel) {
        panel.hidden = !open;
        if (open) {
          panel.removeAttribute("hidden");
        } else {
          panel.setAttribute("hidden", "");
        }
      }

      if (toggle) {
        toggle.setAttribute("aria-expanded", open ? "true" : "false");
        toggle.setAttribute("aria-label", "Abrir chat");
        toggle.hidden = open;
      }

      if (open) {
        if (!bootstrapped) {
          bootstrapped = true;
          appendBubble("bot", persona.greeting);
          renderSuggestions();
        }
        window.setTimeout(function () {
          if (input) input.focus();
        }, 40);
      }
    }

    function sendMessage(text) {
      var message = (text || "").trim();
      if (!message || busy) return;

      busy = true;
      if (suggestionsEl) suggestionsEl.hidden = true;
      appendBubble("user", message);
      if (input) {
        input.value = "";
        resizeInput();
      }
      setTyping(true);
      if (sendBtn) sendBtn.disabled = true;

      fetch(endpoint, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "application/json",
          "X-CSRFToken": getCsrf(),
        },
        credentials: "same-origin",
        body: JSON.stringify({
          persona: personaId,
          message: message,
          history: history,
        }),
      })
        .then(function (response) {
          return response.json().then(function (data) {
            return { ok: response.ok, status: response.status, data: data };
          });
        })
        .then(function (result) {
          setTyping(false);
          if (!result.ok || !result.data || !result.data.ok) {
            var err =
              (result.data && result.data.error) ||
              "Não consegui responder agora. Tente novamente.";
            appendBubble("bot", err, "rt-chat__bubble--error");
            return;
          }
          var reply = result.data.reply || "";
          history.push({ role: "user", content: message });
          history.push({ role: "model", content: reply });
          if (history.length > 16) history = history.slice(-16);
          appendBubble("bot", reply);
        })
        .catch(function () {
          setTyping(false);
          appendBubble(
            "bot",
            "Falha de conexão. Verifique a internet e tente de novo.",
            "rt-chat__bubble--error"
          );
        })
        .finally(function () {
          busy = false;
          resizeInput();
          if (input && isOpen()) input.focus();
        });
    }

    if (toggle) {
      toggle.addEventListener("click", function (event) {
        event.preventDefault();
        event.stopPropagation();
        setOpen(!isOpen());
      });
    }

    if (closeBtn) {
      closeBtn.addEventListener("click", function (event) {
        event.preventDefault();
        event.stopPropagation();
        setOpen(false);
      });
    }

    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape" && isOpen()) {
        setOpen(false);
      }
    });

    if (input) {
      input.addEventListener("input", resizeInput);
      input.addEventListener("keydown", function (event) {
        if (event.key === "Enter" && !event.shiftKey) {
          event.preventDefault();
          if (form && typeof form.requestSubmit === "function") {
            form.requestSubmit();
          } else {
            sendMessage(input.value);
          }
        }
      });
    }

    if (form) {
      form.addEventListener("submit", function (event) {
        event.preventDefault();
        sendMessage(input ? input.value : "");
      });
    }

    resizeInput();
  });
})();
