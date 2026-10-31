"use strict";
(function () {
  var $ = function (id) { return document.getElementById(id); };
  var estado = { vivo: false, dados: null, token: "", ocupado: false };
  var REDUZIR = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var NOMES = { atraso: "Atraso", item_faltando: "Item faltando", item_errado: "Item errado", cobranca: "Cobrança", qualidade: "Qualidade",
    cancelamento: "Cancelamento", elogio: "Elogio", fora_de_escopo: "Fora de escopo" };

  function el(tag, cls, texto) { var e = document.createElement(tag); if (cls) e.className = cls; if (texto != null) e.textContent = texto; return e; }
  function selo(texto, tipo) { return el("span", "selo" + (tipo ? " selo--" + tipo : ""), texto); }
  function json(o) { return JSON.stringify(o, null, 2); }
  function dormir(ms) { return new Promise(function (r) { setTimeout(r, REDUZIR ? 0 : ms); }); }

  function passo(titulo, cls) {
    var li = el("li", "passo" + (cls ? " passo--" + cls : ""));
    li.appendChild(el("h3", null, titulo));
    return li;
  }

  function montarPassos(r) {
    var lista = [];
    var g = passo("1 · Guardrails", r.flags.length ? "alerta" : "");
    var selos = el("div", "selos");
    if (!r.flags.length) selos.appendChild(selo("nenhum alerta", "ok"));
    r.flags.forEach(function (f) { selos.appendChild(selo(f.replace("_", " ").replace(":", ": "), "warn")); });
    g.appendChild(selos);
    g.appendChild(el("p", null, "Texto que chega ao modelo, já sem dados pessoais:"));
    g.appendChild(el("pre", null, r.entrada_segura));
    lista.push(g);

    var n = 2;
    r.passos.forEach(function (p) {
      if (p.etapa === "triagem") {
        var t = passo(n++ + " · Agente de triagem");
        var s = el("div", "selos");
        s.appendChild(selo(NOMES[p.saida.categoria] || p.saida.categoria));
        s.appendChild(selo("urgência " + (p.saida.urgencia === "media" ? "média" : p.saida.urgencia), p.saida.urgencia === "alta" ? "bad" : ""));
        s.appendChild(selo(p.saida.sentimento));
        s.appendChild(selo("confiança " + Math.round(p.saida.confianca * 100) + "%"));
        t.appendChild(s);
        lista.push(t);
      } else if (p.etapa === "politicas") {
        var pol = passo(n++ + " · Políticas recuperadas");
        var s2 = el("div", "selos");
        if (!p.ids.length) s2.appendChild(selo("nenhuma", "warn"));
        p.ids.forEach(function (id) { s2.appendChild(selo(id)); });
        pol.appendChild(s2);
        lista.push(pol);
      } else if (p.etapa === "ferramenta") {
        var f = passo(n++ + " · Ferramenta: " + p.ferramenta, "ferramenta");
        f.appendChild(el("p", null, "Pedido do agente:"));
        f.appendChild(el("pre", null, json(p.args)));
        var erro = p.resultado && p.resultado.erro;
        var rs = el("div", "selos"); rs.appendChild(selo(erro ? "recusada pela ferramenta" : "executada", erro ? "bad" : "ok"));
        f.appendChild(rs);
        f.appendChild(el("pre", null, json(p.resultado)));
        lista.push(f);
      } else if (p.etapa === "revisao") {
        var rv = passo(n++ + " · Agente revisor", p.saida.aprovado ? "" : "alerta");
        var sr = el("div", "selos");
        sr.appendChild(selo(p.saida.aprovado ? "resposta aprovada" : "resposta reprovada", p.saida.aprovado ? "ok" : "bad"));
        rv.appendChild(sr);
        p.saida.problemas.forEach(function (x) { rv.appendChild(el("p", null, "• " + x)); });
        lista.push(rv);
      }
    });
    var fim = passo("Resposta ao cliente", "final");
    var sf = el("div", "selos"); sf.appendChild(selo("decisão: " + r.decisao, r.decisao === "escalar" ? "warn" : "ok"));
    fim.appendChild(sf);
    fim.appendChild(el("p", "resposta", r.resposta));
    lista.push(fim);
    return lista;
  }

  async function mostrar(r, aoFinal) {
    var ol = $("rastro"); ol.textContent = ""; $("vazio").hidden = true; $("resumo").hidden = true;
    var itens = montarPassos(r);
    for (var i = 0; i < itens.length; i++) {
      if (i === itens.length - 1 && aoFinal) aoFinal();
      ol.appendChild(itens[i]); await dormir(380);
    }
    var m = r.metricas, res = $("resumo");
    res.textContent = "";
    [["Chamadas ao modelo", m.chamadas_llm], ["Latência", m.latencia_ms + " ms"], ["Tokens estimados", m.tokens_estimados]].forEach(function (x) {
      var s = el("span"); s.appendChild(document.createTextNode(x[0] + ": ")); s.appendChild(el("b", null, String(x[1]))); res.appendChild(s);
    });
    res.hidden = false;
  }

  var pendente = null; // ticket que ficou esperando o número do pedido

  function bolha(tipo, texto) {
    var m = $("msgs"), b = el("div", "bolha bolha--" + tipo, texto);
    m.appendChild(b); m.scrollTop = m.scrollHeight; return b;
  }
  function digitando() {
    var b = el("div", "bolha bolha--bot"), d = el("span", "digitando");
    d.setAttribute("aria-label", "O assistente está digitando");
    for (var i = 0; i < 3; i++) d.appendChild(el("i"));
    b.appendChild(d); $("msgs").appendChild(b); $("msgs").scrollTop = $("msgs").scrollHeight; return b;
  }
  function saudacao() {
    $("msgs").textContent = ""; pendente = null;
    bolha("bot", "Olá! Eu sou o assistente da Comanda. Como posso ajudar com o seu pedido?");
  }
  function respostaNoChat(typing, r) {
    typing.remove();
    bolha("bot", r.resposta);
    if (r.decisao === "credito") bolha("credito", "Crédito aplicado na sua conta");
    if (r.decisao === "cancelar") bolha("credito", "Pedido cancelado");
    if (r.decisao === "escalar") bolha("sistema", "Conversa transferida para um atendente humano");
  }

  async function tratar(texto, pedido, gravado) {
    if (estado.ocupado) return;
    estado.ocupado = true; $("enviar").disabled = true;
    var enviado = texto;
    if (!gravado && pendente && /^\s*#?\d{4}\s*$/.test(texto)) enviado = pendente + " (pedido " + texto.trim().replace("#", "") + ")";
    bolha("eu", texto);
    var typing = digitando();
    try {
      var r = gravado;
      if (!r) {
        var cab = { "Content-Type": "application/json" };
        if (estado.token) cab.Authorization = "Bearer " + estado.token;
        var resp = await fetch("/tickets", { method: "POST", headers: cab, body: JSON.stringify({ ticket: enviado, pedido_id: pedido || undefined }) });
        var corpo = await resp.json();
        if (resp.status === 401) { $("bloco-token").hidden = false; throw new Error("A API pede token. Informe-o abaixo do chat."); }
        if (!resp.ok) throw new Error(corpo.erro || "Erro " + resp.status);
        r = corpo;
      }
      pendente = r.decisao === "pedir_info" ? enviado : null;
      await mostrar(r, function () { respostaNoChat(typing, r); });
      typing.isConnected && respostaNoChat(typing, r);
    } catch (e) {
      typing.remove(); bolha("sistema", e.message);
      var ol = $("rastro"); ol.textContent = ""; $("vazio").hidden = true;
      var p = passo("Erro", "alerta"); p.appendChild(el("p", null, e.message)); ol.appendChild(p);
    } finally { estado.ocupado = false; $("enviar").disabled = false; $("texto").focus({ preventScroll: true }); }
  }

  function saudacaoSeVazio() { if (!$("msgs").children.length) saudacao(); }

  function montarExemplos() {
    var ul = $("exemplos");
    var escolhidos = [8, 1, 11, 21, 23, 30, 31, 28];
    escolhidos.forEach(function (id) {
      var ex = estado.dados.exemplos.filter(function (e) { return e.id === id; })[0];
      if (!ex) return;
      var li = el("li"), b = el("button"); b.type = "button";
      var cat = ex.resultado.triagem.categoria;
      b.appendChild(el("small", null, ex.resultado.flags.indexOf("possivel_injecao") >= 0 ? "injeção de prompt" : NOMES[cat]));
      b.appendChild(document.createTextNode(ex.texto));
      b.addEventListener("click", function () {
        saudacaoSeVazio(); $("texto").value = "";
        tratar(ex.texto, ex.pedido_id, estado.vivo ? null : ex.resultado);
        
      });
      li.appendChild(b); ul.appendChild(li);
    });
  }

  function montarPedidos() {
    var tb = $("tabela-pedidos").querySelector("tbody");
    Object.keys(estado.dados.pedidos).forEach(function (id) {
      var p = estado.dados.pedidos[id], tr = el("tr");
      [id, p.status, p.atraso_min + " min", p.itens.map(function (i) { return i.nome + " (R$ " + i.preco.toFixed(0) + ")"; }).join(", ")]
        .forEach(function (c) { tr.appendChild(el("td", null, c)); });
      tb.appendChild(tr);
    });
  }

  function montarAvaliacao() {
    var a = estado.dados.avaliacao, box = $("avaliacao"), pct = function (x) { return (x * 100).toFixed(1) + "%"; };
    var c = el("div", "cartoes");
    [["Acerto de categoria", pct(a.acerto_categoria)], ["Acerto de decisão", pct(a.acerto_decisao)], ["Guardrails", pct(a.acerto_flags)],
     ["Casos", a.total], ["Chamadas por ticket", a.chamadas_por_ticket]].forEach(function (x) {
      var d = el("div", "cartao"); d.appendChild(el("b", null, String(x[1]))); d.appendChild(el("span", null, x[0])); c.appendChild(d);
    });
    box.appendChild(c);
    var t = el("table"), th = el("thead"), trh = el("tr");
    ["Categoria", "Acerto (categoria e decisão)", ""].forEach(function (h) { trh.appendChild(el("th", null, h)); });
    th.appendChild(trh); t.appendChild(th);
    var tb = el("tbody");
    Object.keys(a.por_categoria).forEach(function (k) {
      var tr = el("tr"); tr.appendChild(el("td", null, NOMES[k] || k));
      var td = el("td"), barra = el("div", "barra"), i = el("i"); i.style.width = (a.por_categoria[k] * 100) + "%"; barra.appendChild(i); td.appendChild(barra); tr.appendChild(td);
      tr.appendChild(el("td", null, pct(a.por_categoria[k]))); tb.appendChild(tr);
    });
    t.appendChild(tb); var rol = el("div", "tabela-rolavel"); rol.appendChild(t); box.appendChild(rol);
    box.appendChild(el("p", "nota", "Provedor: " + a.provedor + ". O provedor simulado é determinístico e não lê o prompt: estes números validam o pipeline, as ferramentas e os guardrails, não a qualidade de um modelo. Rode com Ollama ou Anthropic para comparar prompts e modelos de verdade."));
  }

  function abas() {
    var botoes = document.querySelectorAll('[role="tab"]');
    function ir(alvo) {
      botoes.forEach(function (b) {
        var ativo = b === alvo; b.setAttribute("aria-selected", ativo); b.tabIndex = ativo ? 0 : -1;
        $(b.getAttribute("aria-controls")).hidden = !ativo;
      });
    }
    botoes.forEach(function (b, i) {
      b.addEventListener("click", function () { ir(b); });
      b.addEventListener("keydown", function (e) {
        if (e.key === "ArrowRight" || e.key === "ArrowLeft") { var n = botoes[(i + (e.key === "ArrowRight" ? 1 : botoes.length - 1)) % botoes.length]; ir(n); n.focus(); }
      });
    });
  }

  async function iniciar() {
    abas();
    try { if (window.COMANDA_DADOS) { estado.dados = window.COMANDA_DADOS; } else { var r = await fetch("dados.json"); estado.dados = await r.json(); } }
    catch (e) { $("modo").textContent = "Não consegui carregar os dados de exemplo."; return; }
    try {
      var h = await fetch("/health", { cache: "no-store" });
      estado.vivo = h.ok && (await h.json()).ok === true;
    } catch (e) { estado.vivo = false; }
    var modo = $("modo");
    modo.dataset.estado = estado.vivo ? "vivo" : "demo";
    modo.textContent = estado.vivo ? "API ao vivo: texto livre habilitado" : "Modo demonstração: rastros gravados de execuções reais";
    $("aviso-livre").hidden = estado.vivo;
    montarExemplos(); montarPedidos(); montarAvaliacao();
    $("token").addEventListener("input", function (e) { estado.token = e.target.value; });
    saudacao();
    $("limpar").addEventListener("click", function () { if (!estado.ocupado) { saudacao(); $("rastro").textContent = ""; $("vazio").hidden = false; $("resumo").hidden = true; } });
    $("form").addEventListener("submit", function (e) {
      e.preventDefault();
      var texto = $("texto").value.trim();
      if (!texto) { $("texto").focus(); return; }
      if (estado.vivo) { $("texto").value = ""; return tratar(texto, "", null); }
      var achado = estado.dados.exemplos.filter(function (x) { return x.texto === texto; })[0];
      if (achado) { $("texto").value = ""; return tratar(texto, "", achado.resultado); }
      $("aviso-livre").hidden = false;
    });
  }
  iniciar();
})();
