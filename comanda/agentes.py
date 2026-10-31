"""Agentes: triagem, resolução (com ferramentas) e revisão. Cada um valida a saída do modelo."""
import json
from pathlib import Path

from .providers import Provedor
from .tools import ESQUEMA_FERRAMENTAS

PASTA_PROMPTS = Path(__file__).resolve().parent.parent / "prompts"
CATEGORIAS = {"atraso", "item_faltando", "item_errado", "cobranca", "qualidade", "cancelamento", "elogio", "fora_de_escopo"}
URGENCIAS = {"baixa", "media", "alta"}
DECISOES = {"credito", "escalar", "informar", "pedir_info", "recusar", "cancelar"}


class SaidaInvalida(ValueError):
    pass


def carregar_prompt(nome: str) -> str:
    return (PASTA_PROMPTS / f"{nome}.md").read_text(encoding="utf-8").strip()


def extrair_json(texto: str) -> dict:
    """Pega o primeiro objeto JSON balanceado da resposta (modelos às vezes escrevem texto em volta)."""
    ini = texto.find("{")
    if ini < 0:
        raise SaidaInvalida("sem JSON na resposta")
    nivel, em_str, esc = 0, False, False
    for i in range(ini, len(texto)):
        c = texto[i]
        if em_str:
            esc = (c == "\\") and not esc
            if c == '"' and not esc:
                em_str = False
            continue
        if c == '"':
            em_str = True
        elif c == "{":
            nivel += 1
        elif c == "}":
            nivel -= 1
            if nivel == 0:
                try:
                    obj = json.loads(texto[ini:i + 1])
                except json.JSONDecodeError as e:
                    raise SaidaInvalida(f"JSON inválido: {e}") from e
                if not isinstance(obj, dict):
                    raise SaidaInvalida("JSON não é um objeto")
                return obj
    raise SaidaInvalida("JSON incompleto")


def _com_reparo(chamar, validar, tentativas: int = 2):
    """Chama o modelo; se a saída não validar, pede uma correção citando o erro."""
    erro = ""
    for _ in range(tentativas):
        bruto = chamar(erro)
        try:
            return validar(extrair_json(bruto)), bruto
        except SaidaInvalida as e:
            erro = str(e)
    raise SaidaInvalida(f"saída inválida após {tentativas} tentativas: {erro}")


def _validar_triagem(o: dict) -> dict:
    if o.get("categoria") not in CATEGORIAS:
        raise SaidaInvalida(f"categoria inválida: {o.get('categoria')!r}")
    if o.get("urgencia") not in URGENCIAS:
        raise SaidaInvalida(f"urgencia inválida: {o.get('urgencia')!r}")
    return {"categoria": o["categoria"], "urgencia": o["urgencia"],
            "sentimento": o.get("sentimento", "neutro"), "confianca": float(o.get("confianca", 0))}


def triar(prov: Provedor, texto_seguro: str, versao: str = "v2") -> tuple[dict, str]:
    system = carregar_prompt(f"triagem_{versao}")

    def chamar(erro: str) -> str:
        user = f"Ticket:\n<<<\n{texto_seguro}\n>>>"
        if erro:
            user += f"\n\nSua resposta anterior foi rejeitada ({erro}). Responda só com o JSON correto."
        return prov.completar("triagem", system, user, {"texto": texto_seguro})

    return _com_reparo(chamar, _validar_triagem)


def _validar_passo(o: dict) -> dict:
    if o.get("acao") == "chamar_ferramenta":
        if o.get("ferramenta") not in ESQUEMA_FERRAMENTAS or not isinstance(o.get("args"), dict):
            raise SaidaInvalida("chamada de ferramenta inválida")
        return o
    if o.get("acao") == "responder":
        if not isinstance(o.get("mensagem"), str) or o.get("decisao") not in DECISOES:
            raise SaidaInvalida("resposta final inválida")
        return o
    raise SaidaInvalida("acao deve ser chamar_ferramenta ou responder")


def passo_resolucao(prov: Provedor, ctx: dict, politicas_txt: str) -> dict:
    ferramentas = json.dumps(ESQUEMA_FERRAMENTAS, ensure_ascii=False, indent=1)
    system = f"{carregar_prompt('resolucao_v1')}\n\nFERRAMENTAS:\n{ferramentas}\n\nPOLÍTICAS:\n{politicas_txt}"
    obs = json.dumps(ctx["observacoes"], ensure_ascii=False)

    def chamar(erro: str) -> str:
        user = (f"Ticket:\n<<<\n{ctx['texto']}\n>>>\nCategoria: {ctx['triagem']['categoria']}\n"
                f"Pedido informado: {ctx['pedido_id']}\nObservações das ferramentas até agora: {obs}")
        if erro:
            user += f"\n\nResposta anterior rejeitada ({erro}). Responda só com o JSON correto."
        return prov.completar("resolucao", system, user, ctx)

    return _com_reparo(chamar, _validar_passo)[0]


def revisar(prov: Provedor, ctx: dict) -> dict:
    system = carregar_prompt("revisao_v1")

    def chamar(erro: str) -> str:
        user = f"RESPOSTA: {ctx['resposta']}\nOBSERVAÇÕES: {json.dumps(ctx['observacoes'], ensure_ascii=False)}"
        return prov.completar("revisao", system, user, ctx)

    def validar(o: dict) -> dict:
        if not isinstance(o.get("aprovado"), bool):
            raise SaidaInvalida("campo aprovado ausente")
        return {"aprovado": o["aprovado"], "problemas": list(o.get("problemas", []))}

    return _com_reparo(chamar, validar)[0]
