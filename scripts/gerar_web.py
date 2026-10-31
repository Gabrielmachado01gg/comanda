"""Grava web/dados.json: rastros reais do pipeline para cada caso do dataset, o resumo da avaliação e os pedidos.
Usado pela tela quando aberta sem a API (por exemplo, no GitHub Pages)."""
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
from comanda.avaliacao import avaliar, carregar_dataset  # noqa: E402
from comanda.pipeline import Comanda, carregar_pedidos  # noqa: E402

exemplos = [{"id": d["id"], "texto": d["texto"], "pedido_id": d.get("pedido_id"), "resultado": Comanda().tratar(d["texto"], d.get("pedido_id"))}
            for d in carregar_dataset()]
av = avaliar()
av.pop("falhas")
saida = {"gerado_com": "provedor simulado", "exemplos": exemplos, "avaliacao": av, "pedidos": carregar_pedidos()}
(RAIZ / "web" / "dados.json").write_text(json.dumps(saida, ensure_ascii=False), encoding="utf-8")
print(len(exemplos), "exemplos gravados")
