(function () {
  const form = document.getElementById("proposta-form");
  const dados = document.getElementById("proposta-catalogo");
  if (!form || !dados) return;

  const catalogo = JSON.parse(dados.textContent);
  const pacotes = new Map(catalogo.pacotes.map((pacote) => [pacote.id, pacote]));
  const servicos = new Map(catalogo.servicos.map((servico) => [servico.id, servico]));
  const cliente = document.getElementById("id_cliente");
  const who = document.getElementById("quote-who");

  function nomeCliente() {
    if (!who) return;
    who.textContent = cliente && cliente.value ? cliente.options[cliente.selectedIndex].text : "";
  }

  function dinheiro(valor) {
    const n = Number(valor);
    if (!Number.isFinite(n)) return 0;
    const sinal = n < 0 ? -1 : 1;
    return (sinal * Math.round((Math.abs(n) + 1e-8) * 100)) / 100;
  }

  function brl(valor) {
    const n = dinheiro(valor);
    const sinal = n < 0 ? "-" : "";
    const partes = Math.abs(n).toFixed(2).split(".");
    const milhar = partes[0].replace(/\B(?=(\d{3})+(?!\d))/g, ".");
    return `${sinal}R$ ${milhar},${partes[1]}`;
  }

  function campoDinheiro(valor) {
    const n = dinheiro(valor);
    const sinal = n < 0 ? "-" : "";
    const partes = Math.abs(n).toFixed(2).split(".");
    return `${sinal}${partes[0].replace(/\B(?=(\d{3})+(?!\d))/g, ".")},${partes[1]}`;
  }

  function lerDinheiro(texto, padrao) {
    if (texto == null || String(texto).trim() === "") return dinheiro(padrao);
    let bruto = String(texto).trim().replace("R$", "").replace(/\s/g, "");
    if (bruto.includes(",")) bruto = bruto.replace(/\./g, "").replace(",", ".");
    const n = Number(bruto);
    return Number.isFinite(n) ? dinheiro(n) : dinheiro(padrao);
  }

  function lerPct(texto) {
    if (texto == null || String(texto).trim() === "") return 0;
    const n = Number(String(texto).trim().replace(",", "."));
    if (!Number.isFinite(n)) return 0;
    return Math.round(n * 100) / 10000;
  }

  function pctTexto(fracao) {
    const pontos = Math.round(Number(fracao) * 10000) / 100;
    return pontos.toFixed(2).replace(".", ",").replace(/0+$/, "").replace(/,$/, "") || "0";
  }

  function sugerido(valor) {
    const n = Number(valor);
    const lista = catalogo.faixas;
    if (!lista.length) return 0;
    for (const faixa of lista) {
      if (faixa.ate === null || n <= Number(faixa.ate)) return Number(faixa.pct);
    }
    return Number(lista[lista.length - 1].pct);
  }

  function comDesconto(valor, percentual) {
    const base = Math.round(dinheiro(valor) * 100);
    const fator = Math.round((1 - Number(percentual || 0)) * 10000);
    return Math.round((base * fator) / 10000) / 100;
  }

  function pacoteAtual() {
    const escolhido = form.querySelector('input[name="pacote"]:checked');
    return escolhido ? pacotes.get(Number(escolhido.value)) : null;
  }

  function textoTabela(item) {
    const piso = item.piso ? "a partir de " : "";
    return `Tabela ${piso}${brl(item.preco)} · ${item.cobranca_label}`;
  }

  function prefixo(piso) {
    return piso ? "a partir de " : "";
  }

  function criarLinha(item) {
    const article = document.createElement("article");
    article.className = "linha";
    article.dataset.tipo = item.tipo;
    article.dataset.id = item.id || "";
    article.dataset.tabela = item.preco;
    article.dataset.piso = item.piso ? "1" : "0";

    const nome = document.createElement("div");
    nome.className = "linha__nome";
    const strong = document.createElement("strong");
    strong.textContent = item.nome;
    const small = document.createElement("small");
    small.textContent = textoTabela(item);
    nome.append(strong, small);

    const campoPreco = document.createElement("label");
    campoPreco.className = "linha__campo";
    const rotuloPreco = document.createElement("span");
    rotuloPreco.textContent = "Na proposta";
    const preco = document.createElement("input");
    preco.type = "text";
    preco.inputMode = "decimal";
    preco.name = item.tipo === "pacote" ? "preco_pacote" : `preco_extra_${item.id}`;
    preco.value = campoDinheiro(item.negociado);
    campoPreco.append(rotuloPreco, preco);

    const campoPct = document.createElement("div");
    campoPct.className = "linha__campo";
    const rotuloPct = document.createElement("span");
    rotuloPct.textContent = "Desconto desta linha";
    const choice = document.createElement("div");
    choice.className = "pct-choice";
    [["0", "Sem"], ["5", "5%"], ["10", "10%"]].forEach(([valor, rotulo]) => {
      const botao = document.createElement("button");
      botao.type = "button";
      botao.dataset.pct = valor;
      botao.textContent = rotulo;
      choice.append(botao);
    });
    const custom = document.createElement("label");
    custom.className = "pct-choice__custom";
    const pct = document.createElement("input");
    pct.type = "text";
    pct.inputMode = "decimal";
    pct.name = item.tipo === "pacote" ? "pct_pacote" : `pct_extra_${item.id}`;
    pct.value = pctTexto(item.pct);
    const em = document.createElement("em");
    em.textContent = "%";
    custom.append(pct, em);
    choice.append(custom);
    campoPct.append(rotuloPct, choice);

    const fica = document.createElement("div");
    fica.className = "linha__fica";
    const rotuloFica = document.createElement("span");
    rotuloFica.textContent = "Fica";
    fica.append(rotuloFica, document.createElement("strong"));

    article.append(nome, campoPreco, campoPct, fica);
    return article;
  }

  function preencherLinha(article, item) {
    article.dataset.tabela = item.preco;
    article.dataset.piso = item.piso ? "1" : "0";
    article.querySelector(".linha__nome strong").textContent = item.nome;
    article.querySelector(".linha__nome small").textContent = textoTabela(item);
    article.querySelector('input[name^="preco_"]').value = campoDinheiro(item.preco);
    article.querySelector('input[name^="pct_"]').value = pctTexto(sugerido(item.preco));
  }

  function lerLinha(article) {
    const tabela = Number(article.dataset.tabela);
    const negociado = lerDinheiro(article.querySelector('input[name^="preco_"]').value, tabela);
    const desconto = lerPct(article.querySelector('input[name^="pct_"]').value);
    return {
      nome: article.querySelector(".linha__nome strong").textContent,
      tabela,
      negociado,
      desconto,
      total: comDesconto(negociado, desconto),
      piso: article.dataset.piso === "1",
    };
  }

  function marcarChips(article, desconto) {
    const pontos = Math.round(Number(desconto) * 10000) / 100;
    article.querySelectorAll(".pct-choice button").forEach((botao) => {
      botao.classList.toggle("is-on", Math.abs(Number(botao.dataset.pct) - pontos) < 0.001);
    });
  }

  function atualizarEscopo() {
    const lista = document.getElementById("quote-scope");
    const rotulo = document.getElementById("quote-scope-label");
    if (!lista) return;
    lista.replaceChildren();
    form.querySelectorAll('input[name="escopo"]:checked').forEach((input) => {
      const item = document.createElement("li");
      item.textContent = input.closest(".pick").querySelector("strong").textContent;
      lista.append(item);
    });
    if (rotulo) rotulo.hidden = lista.children.length === 0;
  }

  function atualizarTudo() {
    const destino = document.getElementById("quote-lines");
    if (destino) destino.replaceChildren();
    form.querySelectorAll(".linha").forEach((article) => {
      const linha = lerLinha(article);
      const forte = article.querySelector(".linha__fica strong");
      if (forte) forte.textContent = prefixo(linha.piso) + brl(linha.total);
      marcarChips(article, linha.desconto);
      if (!destino) return;
      const card = document.createElement("div");
      card.className = "quote-line quote-line--item";
      const info = document.createElement("div");
      const nome = document.createElement("strong");
      nome.textContent = linha.nome;
      const off = document.createElement("span");
      off.textContent = linha.desconto ? `− ${pctTexto(linha.desconto)}%` : "sem desconto";
      info.append(nome, off);
      const money = document.createElement("div");
      money.className = "quote-line__money";
      if (Math.round(linha.negociado * 100) !== Math.round(linha.tabela * 100) || linha.desconto) {
        const anterior = document.createElement("s");
        anterior.textContent = prefixo(linha.piso) + brl(linha.tabela);
        money.append(anterior);
      }
      const total = document.createElement("b");
      total.textContent = prefixo(linha.piso) + brl(linha.total);
      money.append(total);
      card.append(info, money);
      destino.append(card);
    });
    atualizarEscopo();
  }

  function montarEscopo(pacote) {
    const lista = form.querySelector(".scope-list");
    if (!lista) return;
    lista.replaceChildren();
    pacote.escopo.forEach((servico) => {
      const label = document.createElement("label");
      label.className = "pick pick--check is-on";
      const input = document.createElement("input");
      input.type = "checkbox";
      input.name = "escopo";
      input.value = String(servico.id);
      input.checked = true;
      const mark = document.createElement("span");
      mark.className = "pick__mark";
      mark.setAttribute("aria-hidden", "true");
      const body = document.createElement("span");
      body.className = "pick__body";
      const strong = document.createElement("strong");
      strong.textContent = servico.nome;
      body.append(strong);
      label.append(input, mark, body);
      lista.append(label);
    });
  }

  function sincronizarExtras(reset) {
    const pacote = pacoteAtual();
    if (!pacote) return;
    const escopoIds = new Set(pacote.escopo.map((servico) => servico.id));
    const opcionais = new Set(pacote.opcionais);
    let visiveis = 0;
    form.querySelectorAll('#extras-grid input[name="extras"]').forEach((input) => {
      const id = Number(input.value);
      const servico = servicos.get(id);
      const disponivel = Boolean(servico) && (servico.complemento || opcionais.has(id)) && !escopoIds.has(id);
      const card = input.closest(".pick");
      card.hidden = !disponivel;
      if (!disponivel) {
        input.checked = false;
        card.classList.remove("is-on");
      } else {
        visiveis += 1;
      }
    });
    const vazio = document.getElementById("extras-vazio");
    if (vazio) vazio.hidden = visiveis > 0;

    form.querySelectorAll('.linha[data-tipo="avulso"]').forEach((linha) => {
      const input = form.querySelector(`#extras-grid input[name="extras"][value="${linha.dataset.id}"]`);
      if (!input || !input.checked) linha.remove();
      else if (reset) preencherLinha(linha, servicos.get(Number(linha.dataset.id)));
    });
    const lista = form.querySelector(".linha-list");
    form.querySelectorAll('#extras-grid input[name="extras"]:checked').forEach((input) => {
      if (form.querySelector(`.linha[data-tipo="avulso"][data-id="${input.value}"]`)) return;
      const servico = servicos.get(Number(input.value));
      lista.append(criarLinha({
        tipo: "avulso",
        id: servico.id,
        nome: servico.nome,
        preco: servico.preco,
        cobranca_label: servico.cobranca_label,
        piso: false,
        negociado: servico.preco,
        pct: sugerido(servico.preco),
      }));
    });
  }

  function aplicarPacote(pacote) {
    form.querySelectorAll('input[name="pacote"]').forEach((radio) => {
      radio.closest(".pick").classList.toggle("is-on", radio.checked);
    });
    const titulo = form.querySelector(".quote-card h2");
    if (titulo) titulo.textContent = pacote.nome;
    const base = form.querySelector('input[name="pacote_base"]');
    if (base) base.value = pacote.id;
    montarEscopo(pacote);
    const linha = form.querySelector('.linha[data-tipo="pacote"]');
    if (linha) preencherLinha(linha, pacote);
    sincronizarExtras(true);
    atualizarTudo();
  }

  nomeCliente();
  cliente?.addEventListener("change", nomeCliente);

  form.addEventListener("change", (event) => {
    const el = event.target;
    if (el.name === "pacote") {
      const pacote = pacotes.get(Number(el.value));
      if (pacote) aplicarPacote(pacote);
      return;
    }
    if (el.name === "escopo") {
      el.closest(".pick")?.classList.toggle("is-on", el.checked);
      atualizarEscopo();
      return;
    }
    if (el.name === "extras") {
      el.closest(".pick")?.classList.toggle("is-on", el.checked);
      sincronizarExtras(false);
      atualizarTudo();
    }
  });

  form.addEventListener("input", (event) => {
    if (event.target.closest(".linha")) atualizarTudo();
  });

  form.addEventListener("click", (event) => {
    const botao = event.target.closest(".pct-choice button");
    if (!botao || !form.contains(botao)) return;
    const campo = botao.parentElement.querySelector("input");
    if (!campo) return;
    campo.value = botao.dataset.pct;
    atualizarTudo();
  });
})();
