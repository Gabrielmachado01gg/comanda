# Relatório de avaliação

- Provedor: `simulado` | prompt de triagem: `v2` | casos: 31
- Acerto de categoria: **100.0%**
- Acerto de decisão final: **100.0%**
- Guardrails (flags esperadas): **100.0%**
- Latência média: 0.31 ms | chamadas ao modelo por ticket: 4.48

## Acerto por categoria (categoria e decisão corretas)

| Categoria | Acerto |
|---|---|
| atraso | 100.0% |
| cancelamento | 100.0% |
| cobranca | 100.0% |
| elogio | 100.0% |
| fora_de_escopo | 100.0% |
| item_errado | 100.0% |
| item_faltando | 100.0% |
| qualidade | 100.0% |

## Falhas

Nenhuma.

> Provedor simulado é heurístico e determinístico: este relatório valida o pipeline, as ferramentas e os
> guardrails. Para comparar prompts ou modelos, rode com `COMANDA_PROVEDOR=ollama` ou `anthropic`.
