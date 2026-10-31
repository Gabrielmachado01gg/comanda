"""Recuperação de trechos de política por TF-IDF (sem dependências)."""
import math
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path


def normalizar(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return sem_acento.lower()


def tokens(texto: str) -> list[str]:
    """Tokens normalizados, cortados em 5 letras (stemming bruto: cobrado/cobrança, estorno/estornos)."""
    return [t[:5] for t in re.findall(r"[a-z0-9]+", normalizar(texto)) if len(t) > 2]


@dataclass(frozen=True)
class Trecho:
    id: str
    titulo: str
    texto: str


def carregar_politicas(pasta: Path) -> list[Trecho]:
    trechos: list[Trecho] = []
    for arq in sorted(pasta.glob("*.md")):
        for i, bloco in enumerate(re.split(r"(?m)^## ", arq.read_text(encoding="utf-8"))[1:], 1):
            titulo, _, corpo = bloco.partition("\n")
            trechos.append(Trecho(f"{arq.stem}#{i}", titulo.strip(), corpo.strip()))
    return trechos


class Recuperador:
    def __init__(self, trechos: list[Trecho]):
        self.trechos = trechos
        self._docs = [tokens(t.titulo + " " + t.texto) for t in trechos]
        n = len(self._docs)
        df: dict[str, int] = {}
        for d in self._docs:
            for t in set(d):
                df[t] = df.get(t, 0) + 1
        self._idf = {t: math.log((1 + n) / (1 + c)) + 1 for t, c in df.items()}

    def buscar(self, consulta: str, k: int = 2) -> list[Trecho]:
        q = tokens(consulta)
        pontuados = []
        for trecho, doc in zip(self.trechos, self._docs):
            if not doc:
                continue
            tf = {t: doc.count(t) / len(doc) for t in set(doc)}
            nota = sum(tf.get(t, 0) * self._idf.get(t, 0) for t in q)
            if nota > 0:
                pontuados.append((nota, trecho))
        pontuados.sort(key=lambda p: -p[0])
        return [t for _, t in pontuados[:k]]
