"""Orquestração: guardrails -> triagem -> políticas -> resolução com ferramentas -> revisão."""
import json
import re
import time
from copy import deepcopy
from pathlib import Path

from . import agentes
from .guardrails import detectar_injecao, mascarar_pii
from .providers import Provedor, criar_provedor
from .retriever import Recuperador, carregar_politicas
from .tools import Loja, executar

RAIZ = Path(__file__).resolve().parent.parent
MAX_PASSOS = 5


def carregar_pedidos() -> dict:
    return json.loads((RAIZ / "dados" / "pedidos.json").read_text(encoding="utf-8"))


def achar_pedido(texto: str, informado: str | None) -> str | None:
    if informado:
        return str(informado).lstrip("#")
    m = re.search(r"#?\b(\d{4})\b", texto)
    return m.group(1) if m else None


class Comanda:
    def __init__(self, provedor: Provedor | None = None, versao_triagem: str = "v2"):
        self.prov = provedor or criar_provedor()
        self.versao_triagem = versao_triagem
        self.recuperador = Recuperador(carregar_politicas(RAIZ / "politicas"))
        self.loja = Loja(deepcopy(carregar_pedidos()))

    def tratar(self, texto: str, pedido_id: str | None = None) -> dict:
        ini = time.perf_counter()
        chamadas = 0
        passos: list[dict] = []
        flags: list[str] = []

        texto_seguro, pii = mascarar_pii(texto[:2000])
        if pii:
            flags.append("pii_mascarado:" + ",".join(pii))
        injecao = detectar_injecao(texto)
        if injecao:
            flags.append("possivel_injecao")

        triagem, _ = agentes.triar(self.prov, texto_seguro, self.versao_triagem)
        chamadas += 1
        passos.append({"etapa": "triagem", "saida": triagem})

        trechos = self.recuperador.buscar(f"{triagem['categoria']} {texto_seguro}", k=2)
        passos.append({"etapa": "politicas", "ids": [t.id for t in trechos]})
        politicas_txt = "\n\n".join(f"[{t.id}] {t.titulo}\n{t.texto}" for t in trechos)

        ctx = {"texto": texto_seguro, "triagem": triagem, "pedido_id": achar_pedido(texto_seguro, pedido_id),
               "observacoes": [], "injecao": injecao, "politicas": politicas_txt}
        final = None
        for _ in range(MAX_PASSOS):
            passo = agentes.passo_resolucao(self.prov, ctx, politicas_txt)
            chamadas += 1
            if passo["acao"] == "responder":
                final = passo
                break
            resultado = executar(self.loja, passo["ferramenta"], passo["args"])
            ctx["observacoes"].append({"ferramenta": passo["ferramenta"], "args": passo["args"], "resultado": resultado})
            passos.append({"etapa": "ferramenta", "ferramenta": passo["ferramenta"], "args": passo["args"], "resultado": resultado})
        if final is None:
            protocolo = self.loja.escalar_humano("geral", "Limite de passos do agente atingido.")["protocolo"]
            final = {"mensagem": f"Encaminhei seu caso para um atendente (protocolo {protocolo}).", "decisao": "escalar"}
            flags.append("limite_de_passos")

        ctx.update(resposta=final["mensagem"], decisao=final["decisao"])
        revisao = agentes.revisar(self.prov, ctx)
        chamadas += 1
        passos.append({"etapa": "revisao", "saida": revisao})
        if not revisao["aprovado"]:
            flags.append("revisao_reprovou")
            protocolo = self.loja.escalar_humano("geral", "Resposta reprovada na revisão: " + "; ".join(revisao["problemas"]))["protocolo"]
            final = {"mensagem": f"Encaminhei seu caso para um atendente (protocolo {protocolo}).", "decisao": "escalar"}

        return {"entrada_segura": texto_seguro, "triagem": triagem, "politicas": [t.id for t in trechos], "passos": passos,
                "resposta": final["mensagem"], "decisao": final["decisao"], "flags": flags,
                "metricas": {"latencia_ms": round((time.perf_counter() - ini) * 1000, 1), "chamadas_llm": chamadas,
                             "tokens_estimados": (len(texto_seguro) + len(politicas_txt) + len(final["mensagem"])) // 4 * chamadas}}
