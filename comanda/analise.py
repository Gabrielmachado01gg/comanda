"""Análise de dados com IA: classifica avaliações com o mesmo agente de triagem e resume por restaurante."""
import csv
import html
import json
from collections import Counter, defaultdict
from pathlib import Path

from . import agentes
from .pipeline import RAIZ
from .providers import Provedor, criar_provedor


def analisar(prov: Provedor | None = None, caminho: Path | None = None) -> dict:
    prov = prov or criar_provedor()
    caminho = caminho or RAIZ / "dados" / "avaliacoes.csv"
    with caminho.open(encoding="utf-8") as f:
        linhas = list(csv.DictReader(f))
    por_rest: dict[str, dict] = defaultdict(lambda: {"notas": [], "temas": Counter()})
    for l in linhas:
        nota = int(l["nota"])
        por_rest[l["restaurante"]]["notas"].append(nota)
        if nota <= 2:  # só classifica o que é reclamação
            tri, _ = agentes.triar(prov, l["texto"])
            por_rest[l["restaurante"]]["temas"][tri["categoria"]] += 1
    resumo = {}
    for nome, d in por_rest.items():
        n = len(d["notas"])
        resumo[nome] = {"avaliacoes": n, "nota_media": round(sum(d["notas"]) / n, 2),
                        "pct_negativas": round(100 * sum(x <= 2 for x in d["notas"]) / n, 1), "temas": dict(d["temas"].most_common())}
    pior = min(resumo, key=lambda k: resumo[k]["nota_media"])
    tema = next(iter(resumo[pior]["temas"]), "sem reclamações")
    return {"total": len(linhas), "restaurantes": dict(sorted(resumo.items(), key=lambda kv: kv[1]["nota_media"])),
            "destaque": f"{pior} tem a menor nota média ({resumo[pior]['nota_media']}); principal tema de reclamação: {tema}."}


def relatorio_md(r: dict) -> str:
    out = ["# Análise de avaliações", "", f"{r['total']} avaliações. **{r['destaque']}**", "",
           "| Restaurante | Avaliações | Nota média | % negativas | Temas (reclamações) |", "|---|---|---|---|---|"]
    for nome, d in r["restaurantes"].items():
        temas = ", ".join(f"{k} ({v})" for k, v in d["temas"].items()) or "-"
        out.append(f"| {nome} | {d['avaliacoes']} | {d['nota_media']} | {d['pct_negativas']}% | {temas} |")
    return "\n".join(out) + "\n"


def relatorio_html(r: dict) -> str:
    barras = "".join(
        f"<tr><td>{html.escape(n)}</td><td><div style='background:#1f4bff;height:14px;width:{d['nota_media'] / 5 * 100:.0f}%'></div></td>"
        f"<td>{d['nota_media']}</td></tr>" for n, d in r["restaurantes"].items())
    return (f"<!doctype html><meta charset='utf-8'><title>Análise de avaliações</title><body style='font:16px system-ui;max-width:640px;margin:2rem auto'>"
            f"<h1>Análise de avaliações</h1><p>{html.escape(r['destaque'])}</p><table style='width:100%'>{barras}</table>")


def salvar(r: dict, pasta: Path) -> None:
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / "analise.json").write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")
    (pasta / "analise.md").write_text(relatorio_md(r), encoding="utf-8")
    (pasta / "analise.html").write_text(relatorio_html(r), encoding="utf-8")
