"""Gera dados/avaliacoes.csv: 120 avaliações sintéticas (semente fixa) para o exemplo de análise de dados."""
import csv
import random
from pathlib import Path

random.seed(7)
rest = ["Pizzaria do Zé", "Burger Norte", "Sushi Maré", "Cantina Bela", "Marmitaria Casa", "Açaí do Porto"]
neg = ["Demorou demais para chegar", "Pedido atrasou mais de uma hora", "Faltou um item no meu pedido", "A comida chegou fria",
       "Veio errado, pedi outra coisa", "Fui cobrado duas vezes", "Embalagem vazou, tudo derramado", "Atendimento do restaurante foi ruim"]
neu = ["Chegou no prazo, comida normal", "Tudo ok, nada de especial", "Pedido correto, preço um pouco alto"]
pos = ["Excelente, chegou quente e rápido", "Adorei o sabor, perfeito", "Muito bom, entrega pontual", "Amei, nota 10"]
linhas = []
for i in range(1, 121):
    r = random.choice(rest)
    if r == "Burger Norte":
        nota = random.choices([1, 2, 3, 4, 5], [30, 25, 20, 15, 10])[0]
    else:
        nota = random.choices([1, 2, 3, 4, 5], [8, 10, 20, 32, 30])[0]
    texto = random.choice(neg if nota <= 2 else neu if nota == 3 else pos)
    linhas.append({"id": i, "restaurante": r, "nota": nota, "texto": texto})
with open(Path(__file__).resolve().parent.parent / "dados" / "avaliacoes.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=["id", "restaurante", "nota", "texto"])
    w.writeheader()
    w.writerows(linhas)
