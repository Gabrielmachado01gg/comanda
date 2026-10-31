"""Ferramentas que o agente pode chamar. As regras de negócio ficam AQUI, no código,
e não no prompt: o modelo pede, a ferramenta decide se pode."""
from dataclasses import dataclass, field

LIMITE_CREDITO_AUTOMATICO = 40.0


@dataclass
class Loja:
    """Estado simulado do sistema de pedidos (em produção seria um serviço/banco)."""
    pedidos: dict[str, dict]
    creditos: dict[str, float] = field(default_factory=dict)
    escalonamentos: list[dict] = field(default_factory=list)

    def consultar_pedido(self, pedido_id: str) -> dict:
        p = self.pedidos.get(str(pedido_id))
        if not p:
            return {"erro": f"pedido {pedido_id} não encontrado"}
        return {"pedido_id": str(pedido_id), **p}

    def emitir_credito(self, pedido_id: str, valor: float, motivo: str) -> dict:
        p = self.pedidos.get(str(pedido_id))
        if not p:
            return {"erro": "pedido não encontrado"}
        try:
            valor = round(float(valor), 2)
        except (TypeError, ValueError):
            return {"erro": "valor inválido"}
        if valor <= 0:
            return {"erro": "valor deve ser positivo"}
        if valor > LIMITE_CREDITO_AUTOMATICO:
            return {"erro": f"acima do limite automático de R$ {LIMITE_CREDITO_AUTOMATICO:.2f}; use escalar_humano"}
        if valor > p["valor"]:
            return {"erro": "valor maior que o total do pedido"}
        if str(pedido_id) in self.creditos:
            return {"erro": "este pedido já recebeu crédito"}
        self.creditos[str(pedido_id)] = valor
        return {"ok": True, "credito": valor, "motivo": motivo}

    def cancelar_pedido(self, pedido_id: str) -> dict:
        p = self.pedidos.get(str(pedido_id))
        if not p:
            return {"erro": "pedido não encontrado"}
        if p["status"] != "confirmado":
            return {"erro": f"pedido em '{p['status']}' não pode ser cancelado automaticamente"}
        p["status"] = "cancelado"
        return {"ok": True}

    def escalar_humano(self, fila: str, resumo: str) -> dict:
        protocolo = f"ESC-{len(self.escalonamentos) + 1:04d}"
        self.escalonamentos.append({"protocolo": protocolo, "fila": fila, "resumo": resumo})
        return {"ok": True, "protocolo": protocolo, "fila": fila}


ESQUEMA_FERRAMENTAS = {
    "consultar_pedido": {"descricao": "Consulta status, itens, valor e atraso de um pedido.", "args": {"pedido_id": "string"}},
    "emitir_credito": {"descricao": "Emite crédito ao cliente. Limite automático de R$ 40,00 por pedido.", "args": {"pedido_id": "string", "valor": "number", "motivo": "string"}},
    "cancelar_pedido": {"descricao": "Cancela pedido apenas se estiver 'confirmado'.", "args": {"pedido_id": "string"}},
    "escalar_humano": {"descricao": "Encaminha para atendente humano. Filas: financeiro, saude, cancelamento, seguranca, geral.", "args": {"fila": "string", "resumo": "string"}},
}


def executar(loja: Loja, nome: str, args: dict) -> dict:
    """Executa uma ferramenta pelo nome, validando que ela existe e que os argumentos batem."""
    if nome not in ESQUEMA_FERRAMENTAS:
        return {"erro": f"ferramenta desconhecida: {nome}"}
    esperados = set(ESQUEMA_FERRAMENTAS[nome]["args"])
    if not isinstance(args, dict) or set(args) != esperados:
        return {"erro": f"argumentos inválidos; esperado {sorted(esperados)}"}
    return getattr(loja, nome)(**args)
