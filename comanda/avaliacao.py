"""Harness de avaliação: roda o dataset, mede acerto de categoria e de decisão, e gera relatório."""
import json
import statistics
from collections import defaultdict
from pathlib import Path

from .pipeline import RAIZ, Comanda
from .providers import criar_provedor


def carregar_dataset(caminho: Path | None = None) -> list[dict]:
    caminho = caminho or RAIZ / "evals" / "dataset.jsonl"
    return [json.loads(l) for l in caminho.read_text(encoding="utf-8").splitlines() if l.strip()]


def avaliar(provedor_nome: str | None = None, versao: str = "v2", dataset: list[dict] | None = None) -> dict:
    prov = criar_provedor(provedor_nome)
    casos, falhas = [], []
    for d in dataset or carregar_dataset():
        r = Comanda(prov, versao).tratar(d["texto"], d.get("pedido_id"))  # sistema novo por caso: sem vazamento de estado
        cat_ok = d["categoria"] is None or r["triagem"]["categoria"] == d["categoria"]
        dec_ok = r["decisao"] == d["decisao"]
        flag_ok = d.get("flag") is None or any(f.startswith(d["flag"]) for f in r["flags"])
        casos.append({"id": d["id"], "categoria": d["categoria"], "cat_ok": cat_ok, "dec_ok": dec_ok, "flag_ok": flag_ok,
                      "latencia_ms": r["metricas"]["latencia_ms"], "chamadas": r["metricas"]["chamadas_llm"]})
        if not (cat_ok and dec_ok and flag_ok):
            falhas.append({"id": d["id"], "texto": d["texto"], "obtido": [r["triagem"]["categoria"], r["decisao"], r["flags"]],
                           "esperado": [d["categoria"], d["decisao"], d.get("flag")]})
    pontuados = [c for c in casos if c["categoria"] is not None]
    por_cat: dict[str, list[bool]] = defaultdict(list)
    for c in pontuados:
        por_cat[c["categoria"]].append(c["cat_ok"] and c["dec_ok"])
    return {
        "provedor": prov.nome, "versao_triagem": versao, "total": len(casos),
        "acerto_categoria": sum(c["cat_ok"] for c in pontuados) / len(pontuados),
        "acerto_decisao": sum(c["dec_ok"] for c in casos) / len(casos),
        "acerto_flags": sum(c["flag_ok"] for c in casos) / len(casos),
        "por_categoria": {k: sum(v) / len(v) for k, v in sorted(por_cat.items())},
        "latencia_media_ms": round(statistics.mean(c["latencia_ms"] for c in casos), 2),
        "chamadas_por_ticket": round(statistics.mean(c["chamadas"] for c in casos), 2), "falhas": falhas,
    }


def relatorio_md(r: dict) -> str:
    pct = lambda x: f"{x * 100:.1f}%"  # noqa: E731
    linhas = [f"# Relatório de avaliação", "",
              f"- Provedor: `{r['provedor']}` | prompt de triagem: `{r['versao_triagem']}` | casos: {r['total']}",
              f"- Acerto de categoria: **{pct(r['acerto_categoria'])}**",
              f"- Acerto de decisão final: **{pct(r['acerto_decisao'])}**",
              f"- Guardrails (flags esperadas): **{pct(r['acerto_flags'])}**",
              f"- Latência média: {r['latencia_media_ms']} ms | chamadas ao modelo por ticket: {r['chamadas_por_ticket']}", "",
              "## Acerto por categoria (categoria e decisão corretas)", "", "| Categoria | Acerto |", "|---|---|"]
    linhas += [f"| {k} | {pct(v)} |" for k, v in r["por_categoria"].items()]
    linhas += ["", "## Falhas", ""]
    if not r["falhas"]:
        linhas.append("Nenhuma.")
    for f in r["falhas"]:
        linhas.append(f"- caso {f['id']}: \"{f['texto']}\" obtido {f['obtido']}, esperado {f['esperado']}")
    if r["provedor"] == "simulado":
        linhas += ["", "> Provedor simulado é heurístico e determinístico: este relatório valida o pipeline, as ferramentas e os",
                   "> guardrails. Para comparar prompts ou modelos, rode com `COMANDA_PROVEDOR=ollama` ou `anthropic`."]
    return "\n".join(linhas) + "\n"
