"""Provedores de LLM com a mesma interface.

- simulado: heurísticas determinísticas, sem rede nem chave. Serve para rodar testes e CI.
  Ele NÃO lê o prompt: usa o `contexto` estruturado. Medir qualidade de prompt exige um modelo real.
- ollama: modelo local (http://localhost:11434).
- anthropic: API da Anthropic, chave na variável ANTHROPIC_API_KEY.
"""
import json
import os
import re
import urllib.request

from .retriever import normalizar


class Provedor:
    nome = "base"

    def completar(self, tarefa: str, system: str, user: str, contexto: dict | None = None) -> str:
        raise NotImplementedError


# --------------------------------------------------------------------------- simulado
_LEXICO = {
    "cobranca": ["cobrado duas", "cobranca", "cobraram", "estorno", "debitado", "fatura", "nao reconheco", "reembolse"],
    "qualidade": ["frio", "fria", "estragad", "azed", "cru ", "queimad", "gosto ruim", "passei mal", "intoxic", "vomit", "cabelo", "barata"],
    "item_faltando": ["faltou", "faltando", "nao veio", "esqueceram", "veio sem"],
    "item_errado": ["errado", "errada", "trocaram", "diferente", "nao era isso"],
    "cancelamento": ["cancelar", "cancela", "cancelamento", "desisti", "desistir"],
    "atraso": ["atras", "demor", "nao chegou", "ainda nao chegou", "horas esperando"],
    "elogio": ["parabens", "excelente", "adorei", "amei", "nota 10", "perfeito", "muito bom"],
}
_PRIORIDADE = ["cobranca", "qualidade", "item_faltando", "item_errado", "cancelamento", "atraso", "elogio"]
_NEGATIVAS = ["absurdo", "pessimo", "horrivel", "demor", "errado", "frio", "estragad", "cobrado", "nunca mais", "passei mal"]
_SAUDE = ["passei mal", "intoxic", "vomit", "alergia", "estragad"]


def _triagem(ctx: dict) -> dict:
    t = normalizar(ctx["texto"]) + " "
    placar = {c: sum(t.count(p) for p in ps) for c, ps in _LEXICO.items()}
    melhor = max(_PRIORIDADE, key=lambda c: (placar[c], -_PRIORIDADE.index(c)))
    categoria = melhor if placar[melhor] > 0 else "fora_de_escopo"
    neg = sum(t.count(p) for p in _NEGATIVAS)
    sentimento = "positivo" if categoria == "elogio" else ("negativo" if neg else "neutro")
    alta = any(p in t for p in _SAUDE) or categoria == "cobranca"
    urgencia = "alta" if alta else ("media" if categoria not in ("elogio", "fora_de_escopo") else "baixa")
    conf = 0.55 if categoria == "fora_de_escopo" else min(0.95, 0.7 + 0.1 * placar[categoria])
    return {"categoria": categoria, "urgencia": urgencia, "sentimento": sentimento, "confianca": round(conf, 2)}


def _chamar(ferramenta: str, args: dict) -> dict:
    return {"acao": "chamar_ferramenta", "ferramenta": ferramenta, "args": args}


def _responder(msg: str, decisao: str) -> dict:
    return {"acao": "responder", "mensagem": msg, "decisao": decisao}


def _resolucao(ctx: dict) -> dict:
    cat = ctx["triagem"]["categoria"]
    obs = ctx["observacoes"]
    feitas = lambda nome: [o for o in obs if o["ferramenta"] == nome]  # noqa: E731
    pid = ctx["pedido_id"]

    if ctx["injecao"]:
        if not feitas("escalar_humano"):
            return _chamar("escalar_humano", {"fila": "seguranca", "resumo": "Possível tentativa de alterar instruções do assistente."})
        return _responder("Não consegui atender esse pedido. Encaminhei para um atendente humano.", "escalar")
    if cat == "elogio":
        return _responder("Que bom saber disso! Obrigado pelo carinho, vamos repassar ao restaurante.", "informar")
    if cat == "fora_de_escopo":
        return _responder("Só consigo ajudar com pedidos de delivery. Se tiver algum problema com um pedido, me conte.", "recusar")
    if pid is None:
        return _responder("Para ajudar, pode me informar o número do pedido?", "pedir_info")
    if not feitas("consultar_pedido"):
        return _chamar("consultar_pedido", {"pedido_id": pid})
    pedido = feitas("consultar_pedido")[-1]["resultado"]
    if "erro" in pedido:
        return _responder(f"Não encontrei o pedido {pid}. Pode conferir o número?", "pedir_info")

    def escalar(fila: str, resumo: str) -> dict:
        ja = feitas("escalar_humano")
        if not ja:
            return _chamar("escalar_humano", {"fila": fila, "resumo": resumo})
        prot = ja[-1]["resultado"].get("protocolo", "")
        return _responder(f"Encaminhei seu caso para um atendente (protocolo {prot}). Você receberá retorno em breve.", "escalar")

    def creditar(valor: float, motivo: str) -> dict:
        ja = feitas("emitir_credito")
        if not ja:
            return _chamar("emitir_credito", {"pedido_id": pid, "valor": valor, "motivo": motivo})
        r = ja[-1]["resultado"]
        if "erro" in r:
            return escalar("geral", f"Crédito recusado pela ferramenta: {r['erro']}")
        valor = f"{r['credito']:.2f}".replace(".", ",")
        return _responder(f"Sinto muito pelo transtorno. Emiti um crédito de R$ {valor}.", "credito")

    def item_citado() -> dict | None:
        t = normalizar(ctx["texto"])
        for it in pedido["itens"]:
            palavras = [w for w in re.findall(r"[a-z0-9]+", normalizar(it["nome"])) if len(w) >= 4 and w != "combo"]
            if any(w in t for w in palavras):
                return it
        return None

    if cat == "cobranca":
        return escalar("financeiro", "Cobrança duplicada ou não reconhecida; verificar com o financeiro.")
    if cat == "qualidade":
        if any(p in normalizar(ctx["texto"]) for p in _SAUDE):
            return escalar("saude", "Relato de mal-estar ou comida estragada; prioridade alta.")
        return creditar(25.0, "qualidade da comida")
    if cat == "cancelamento":
        if pedido["status"] == "confirmado":
            if not feitas("cancelar_pedido"):
                return _chamar("cancelar_pedido", {"pedido_id": pid})
            return _responder("Pedido cancelado sem custo.", "cancelar")
        return escalar("cancelamento", f"Cliente quer cancelar pedido em '{pedido['status']}'.")
    if cat in ("item_faltando", "item_errado"):
        item = item_citado()
        if item is None:
            return _responder("Qual item do pedido teve problema? Assim consigo resolver.", "pedir_info")
        if item["preco"] > 40.0:
            return escalar("geral", f"Item '{item['nome']}' acima do limite automático de crédito.")
        return creditar(item["preco"], f"{cat}: {item['nome']}")
    if cat == "atraso":
        if pedido["status"] == "a_caminho" or pedido["atraso_min"] <= 20:
            return _responder(f"Seu pedido está com status '{pedido['status']}'. Pedimos desculpas pela demora.", "informar")
        return creditar(10.0 if pedido["atraso_min"] <= 45 else 20.0, f"atraso de {pedido['atraso_min']} min")
    return escalar("geral", "Caso não previsto pelas políticas.")


_PROMESSA = re.compile(r"reembolso (total|integral)|garanto|com certeza (voc[eê] )?receber", re.I)


def _revisao(ctx: dict) -> dict:
    from .guardrails import tem_pii
    problemas = []
    resp = ctx["resposta"]
    if not resp.strip():
        problemas.append("resposta vazia")
    if len(resp) > 600:
        problemas.append("resposta longa demais")
    if tem_pii(resp):
        problemas.append("resposta contém dado pessoal")
    if _PROMESSA.search(resp):
        problemas.append("promete algo que nenhuma ferramenta confirmou")
    if ctx["decisao"] != "credito" and re.search(r"cr[eé]dito de R\$", resp):
        problemas.append("menciona crédito sem ter emitido")
    return {"aprovado": not problemas, "problemas": problemas}


class Simulado(Provedor):
    nome = "simulado"

    def completar(self, tarefa, system, user, contexto=None):
        ctx = contexto or {}
        saida = {"triagem": _triagem, "resolucao": _resolucao, "revisao": _revisao}[tarefa](ctx)
        return json.dumps(saida, ensure_ascii=False)


# --------------------------------------------------------------------------- reais
def _post(url: str, corpo: dict, headers: dict, timeout: int = 60) -> dict:
    req = urllib.request.Request(url, json.dumps(corpo).encode(), {"Content-Type": "application/json", **headers})
    with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310 - URLs fixas abaixo
        return json.load(r)


class Ollama(Provedor):
    nome = "ollama"

    def __init__(self, modelo: str | None = None, base: str = "http://localhost:11434"):
        self.modelo = modelo or os.environ.get("COMANDA_MODELO", "llama3.2")
        self.base = base

    def completar(self, tarefa, system, user, contexto=None):
        r = _post(f"{self.base}/api/chat", {"model": self.modelo, "stream": False, "format": "json",
                                            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}, {})
        return r["message"]["content"]


class Anthropic(Provedor):
    nome = "anthropic"

    def __init__(self, modelo: str | None = None):
        self.modelo = modelo or os.environ.get("COMANDA_MODELO", "claude-haiku-5-5")
        self.chave = os.environ.get("ANTHROPIC_API_KEY", "")
        if not self.chave:
            raise RuntimeError("defina ANTHROPIC_API_KEY para usar o provedor anthropic")

    def completar(self, tarefa, system, user, contexto=None):
        r = _post("https://api.anthropic.com/v1/messages",
                  {"model": self.modelo, "max_tokens": 800, "system": system, "messages": [{"role": "user", "content": user}]},
                  {"x-api-key": self.chave, "anthropic-version": "2023-06-01"})
        return "".join(b.get("text", "") for b in r["content"])


def criar_provedor(nome: str | None = None) -> Provedor:
    nome = (nome or os.environ.get("COMANDA_PROVEDOR", "simulado")).lower()
    if nome == "simulado":
        return Simulado()
    if nome == "ollama":
        return Ollama()
    if nome == "anthropic":
        return Anthropic()
    raise ValueError(f"provedor desconhecido: {nome}")
