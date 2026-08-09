(function () {
  var menuBtn = document.querySelector("[data-erp-menu]");
  var sidebar = document.getElementById("erp-sidebar");
  if (menuBtn && sidebar) {
    menuBtn.addEventListener("click", function () {
      sidebar.classList.toggle("is-open");
    });
  }

  var checkAll = document.querySelector("[data-check-all]");
  if (checkAll) {
    checkAll.addEventListener("change", function () {
      document
        .querySelectorAll('input[type="checkbox"][name="ids"]')
        .forEach(function (el) {
          el.checked = checkAll.checked;
        });
    });
  }

  initProjectReorder();

  function initProjectReorder() {
    var form = document.querySelector("[data-reorder-form]");
    var body = document.querySelector("[data-sortable-body]");
    if (!form || !body) return;

    var statusEl = document.querySelector("[data-reorder-status]");
    var dragRow = null;
    var saveTimer = null;

    function rows() {
      return Array.prototype.slice.call(body.querySelectorAll("tr[data-project-id]"));
    }

    function refreshOrderIndexes() {
      rows().forEach(function (row, index) {
        var cell = row.querySelector("[data-order-index]");
        if (cell) cell.textContent = String(index);
        var input = row.querySelector('input[name="order"]');
        if (input) input.value = row.getAttribute("data-project-id");
      });
    }

    function setStatus(text, kind) {
      if (!statusEl) return;
      statusEl.hidden = !text;
      statusEl.textContent = text || "";
      statusEl.className = "erp-reorder-status" + (kind ? " erp-reorder-status--" + kind : "");
    }

    function saveOrder() {
      refreshOrderIndexes();
      setStatus("Salvando…", "pending");
      var data = new FormData(form);
      fetch(form.action, {
        method: "POST",
        body: data,
        headers: {
          "X-Requested-With": "XMLHttpRequest",
          Accept: "application/json",
        },
        credentials: "same-origin",
      })
        .then(function (res) {
          if (!res.ok) throw new Error("Falha ao salvar");
          return res.json();
        })
        .then(function () {
          setStatus("Ordem salva", "ok");
          window.setTimeout(function () {
            setStatus("");
          }, 1800);
        })
        .catch(function () {
          setStatus("Erro ao salvar ordem", "error");
        });
    }

    function scheduleSave() {
      window.clearTimeout(saveTimer);
      saveTimer = window.setTimeout(saveOrder, 200);
    }

    body.addEventListener("dragstart", function (event) {
      var row = event.target.closest("tr[data-project-id]");
      if (!row || !body.contains(row)) return;
      // Avoid dragging when interacting with links/buttons
      if (event.target.closest("a, button, input, select, textarea")) {
        event.preventDefault();
        return;
      }
      dragRow = row;
      row.classList.add("is-dragging");
      event.dataTransfer.effectAllowed = "move";
      event.dataTransfer.setData("text/plain", row.getAttribute("data-project-id"));
    });

    body.addEventListener("dragend", function () {
      if (dragRow) dragRow.classList.remove("is-dragging");
      body.querySelectorAll(".is-drag-over").forEach(function (el) {
        el.classList.remove("is-drag-over");
      });
      dragRow = null;
    });

    body.addEventListener("dragover", function (event) {
      if (!dragRow) return;
      event.preventDefault();
      event.dataTransfer.dropEffect = "move";
      var target = event.target.closest("tr[data-project-id]");
      if (!target || target === dragRow) return;

      body.querySelectorAll(".is-drag-over").forEach(function (el) {
        if (el !== target) el.classList.remove("is-drag-over");
      });
      target.classList.add("is-drag-over");

      var rect = target.getBoundingClientRect();
      var before = event.clientY < rect.top + rect.height / 2;
      if (before) {
        body.insertBefore(dragRow, target);
      } else {
        body.insertBefore(dragRow, target.nextSibling);
      }
      refreshOrderIndexes();
    });

    body.addEventListener("drop", function (event) {
      event.preventDefault();
      body.querySelectorAll(".is-drag-over").forEach(function (el) {
        el.classList.remove("is-drag-over");
      });
      if (!dragRow) return;
      refreshOrderIndexes();
      scheduleSave();
    });
  }
})();
