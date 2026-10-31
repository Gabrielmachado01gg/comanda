"""API HTTP mínima (stdlib) para integrar com n8n, Make, Zapier ou qualquer webhook.

POST /tickets  {"ticket": "...", "pedido_id": "1001"}  -> resultado completo do pipeline
GET  /health   -> {"ok": true}
GET  /metrics  -> contadores e latência
GET /  -> tela de demonstração (web/index.html)
Se COMANDA_TOKEN estiver definido, POST exige o cabeçalho  Authorization: Bearer <token>.
"""
import hmac
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from pathlib import Path

from .pipeline import RAIZ, Comanda

MAX_CORPO = 16 * 1024
WEB = RAIZ / "web"
TIPOS = {".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".json": "application/json; charset=utf-8"}


class Estado:
    def __init__(self, comanda: Comanda):
        self.comanda = comanda
        self.trava = threading.Lock()
        self.total = 0
        self.por_decisao: dict[str, int] = {}
        self.por_categoria: dict[str, int] = {}
        self.latencia_total = 0.0
        self.erros = 0


def criar_servidor(comanda: Comanda, host: str = "127.0.0.1", porta: int = 8787, token: str | None = None) -> ThreadingHTTPServer:
    estado = Estado(comanda)
    token = token if token is not None else os.environ.get("COMANDA_TOKEN", "")

    class Handler(BaseHTTPRequestHandler):
        server_version = "Comanda/0.1"

        def _json(self, codigo: int, corpo: dict) -> None:
            dados = json.dumps(corpo, ensure_ascii=False).encode()
            self.send_response(codigo)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(dados)))
            self.end_headers()
            self.wfile.write(dados)

        def log_message(self, *a):  # silencioso: não registra corpo de tickets
            pass

        def _arquivo(self, nome: str) -> None:
            alvo = (WEB / nome).resolve()
            if WEB.resolve() not in alvo.parents or alvo.suffix not in TIPOS or not alvo.is_file():
                return self._json(404, {"erro": "arquivo não encontrado"})
            dados = alvo.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", TIPOS[alvo.suffix])
            self.send_header("Content-Length", str(len(dados)))
            self.end_headers()
            self.wfile.write(dados)

        def do_GET(self):
            if self.path in ("/", "/index.html"):
                return self._arquivo("index.html")
            if self.path not in ("/health", "/metrics") and "/" not in self.path[1:]:
                return self._arquivo(self.path[1:].split("?")[0])  # estilo.css, app.js, dados.json
            if self.path == "/health":
                return self._json(200, {"ok": True})
            if self.path == "/metrics":
                with estado.trava:
                    media = estado.latencia_total / estado.total if estado.total else 0
                    return self._json(200, {"tickets": estado.total, "erros": estado.erros, "por_decisao": estado.por_decisao,
                                            "por_categoria": estado.por_categoria, "latencia_media_ms": round(media, 2)})
            self._json(404, {"erro": "rota não encontrada"})

        def do_POST(self):
            if self.path != "/tickets":
                return self._json(404, {"erro": "rota não encontrada"})
            if token and not hmac.compare_digest(self.headers.get("Authorization", ""), f"Bearer {token}"):
                return self._json(401, {"erro": "token inválido"})
            try:
                tam = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                return self._json(400, {"erro": "Content-Length inválido"})
            if tam <= 0 or tam > MAX_CORPO:
                return self._json(413 if tam > MAX_CORPO else 400, {"erro": "corpo ausente ou grande demais"})
            try:
                corpo = json.loads(self.rfile.read(tam))
                ticket = corpo["ticket"]
                pedido = corpo.get("pedido_id")
                if not isinstance(ticket, str) or not ticket.strip():
                    raise ValueError
            except (ValueError, KeyError, TypeError):
                return self._json(400, {"erro": "envie JSON com o campo 'ticket' (texto)"})
            try:
                with estado.trava:  # a Loja simulada é estado compartilhado: serializa as chamadas
                    r = estado.comanda.tratar(ticket, str(pedido) if pedido else None)
                    estado.total += 1
                    estado.por_decisao[r["decisao"]] = estado.por_decisao.get(r["decisao"], 0) + 1
                    cat = r["triagem"]["categoria"]
                    estado.por_categoria[cat] = estado.por_categoria.get(cat, 0) + 1
                    estado.latencia_total += r["metricas"]["latencia_ms"]
            except Exception as e:  # noqa: BLE001 - devolve erro limpo ao chamador
                with estado.trava:
                    estado.erros += 1
                return self._json(502, {"erro": f"falha ao processar: {type(e).__name__}"})
            self._json(200, r)

    return ThreadingHTTPServer((host, porta), Handler)
