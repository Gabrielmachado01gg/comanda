"""Proteções de entrada e saída: mascaramento de dados pessoais e detecção de injeção de prompt."""
import re

_PADROES_PII = [
    ("cpf", re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b"), "[CPF]"),
    ("email", re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"), "[EMAIL]"),
    ("cartao", re.compile(r"\b(?:\d[ -]?){13,16}\b"), "[CARTAO]"),
    ("telefone", re.compile(r"(?:\(?\d{2}\)?\s?)?9?\d{4}-?\d{4}\b"), "[TELEFONE]"),
]

_PADROES_INJECAO = [
    re.compile(r"ignor[ea]\s+(todas\s+)?(as\s+)?(instru[cç][oõ]es|regras)", re.I),
    re.compile(r"(system|sistema)\s*prompt", re.I),
    re.compile(r"voc[eê]\s+agora\s+(é|e|sera|será)", re.I),
    re.compile(r"(revele|mostre|exiba)\s+(suas|as)\s+(instru[cç][oõ]es|regras)", re.I),
    re.compile(r"ignore\s+(all\s+)?(previous|prior)\s+instructions", re.I),
]


def mascarar_pii(texto: str) -> tuple[str, list[str]]:
    """Troca dados pessoais por marcadores e devolve os tipos encontrados."""
    achados: list[str] = []
    for nome, padrao, marcador in _PADROES_PII:
        texto, n = padrao.subn(marcador, texto)
        if n:
            achados.append(nome)
    return texto, achados


def detectar_injecao(texto: str) -> bool:
    return any(p.search(texto) for p in _PADROES_INJECAO)


def tem_pii(texto: str) -> bool:
    return bool(mascarar_pii(texto)[1])
