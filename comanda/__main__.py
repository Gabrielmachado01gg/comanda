"""CLI: python -m comanda {ticket,serve,avaliar,analisar}"""
import argparse
import json
import sys
from pathlib import Path

from .pipeline import RAIZ, Comanda
from .providers import criar_provedor


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="comanda", description=__doc__)
    ap.add_argument("--provedor", help="simulado (padrão), ollama ou anthropic")
    sub = ap.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("ticket", help="trata um ticket e mostra o rastro dos agentes")
    t.add_argument("texto")
    t.add_argument("--pedido")
    s = sub.add_parser("serve", help="sobe a API em 127.0.0.1")
    s.add_argument("--porta", type=int, default=8787)
    a = sub.add_parser("avaliar", help="roda o dataset de avaliação")
    a.add_argument("--versao", default="v2")
    a.add_argument("--minimo", type=float, default=0.9, help="falha (exit 1) se algum acerto ficar abaixo disto")
    a.add_argument("--saida", default=str(RAIZ / "evals" / "relatorio.md"))
    sub.add_parser("analisar", help="análise das avaliações de clientes")
    args = ap.parse_args(argv)

    if args.cmd == "ticket":
        r = Comanda(criar_provedor(args.provedor)).tratar(args.texto, args.pedido)
        print(json.dumps(r, ensure_ascii=False, indent=2))
    elif args.cmd == "serve":
        from .servidor import criar_servidor
        srv = criar_servidor(Comanda(criar_provedor(args.provedor)), porta=args.porta)
        print(f"Comanda em http://127.0.0.1:{args.porta}  (Ctrl+C para sair)")
        try:
            srv.serve_forever()
        except KeyboardInterrupt:
            srv.server_close()
    elif args.cmd == "avaliar":
        from .avaliacao import avaliar, relatorio_md
        r = avaliar(args.provedor, args.versao)
        Path(args.saida).write_text(relatorio_md(r), encoding="utf-8")
        print(relatorio_md(r))
        return 0 if min(r["acerto_categoria"], r["acerto_decisao"], r["acerto_flags"]) >= args.minimo else 1
    elif args.cmd == "analisar":
        from .analise import analisar, salvar
        r = analisar(criar_provedor(args.provedor))
        salvar(r, RAIZ / "evals")
        print(r["destaque"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
