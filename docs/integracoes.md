# Integrações (n8n, Make, Zapier)

A API da Comanda é um contrato HTTP simples, então qualquer ferramenta de automação com módulo de HTTP consegue usar.

## Contrato

```
POST http://127.0.0.1:8787/tickets
Authorization: Bearer <COMANDA_TOKEN>        (obrigatório só se a variável estiver definida)
Content-Type: application/json

{"ticket": "O refrigerante não veio no pedido 1001", "pedido_id": "1001"}   // pedido_id é opcional
```

Resposta (resumo): `triagem`, `politicas`, `passos` (rastro de cada agente e ferramenta), `resposta`, `decisao`
(`credito | escalar | informar | pedir_info | recusar | cancelar`), `flags` e `metricas`.
Erros: `400` corpo inválido, `401` token, `413` corpo grande, `502` falha ao processar.

## n8n

1. Suba a API: `COMANDA_TOKEN=meu-token python -m comanda serve`.
2. No n8n: Workflows > Import from File > `n8n/fluxo_comanda.json`.
3. No nó "Chamar API Comanda" troque `SEU_TOKEN`. Se o n8n rodar em Docker, troque `localhost` por `host.docker.internal`.
4. Os nós finais só montam o aviso; troque-os por Slack, Gmail, Google Sheets ou o CRM que você usar.

O fluxo exportado foi escrito a partir do formato do n8n e a API que ele chama é coberta por testes, mas o fluxo em si
ainda não foi executado numa instância de n8n por quem o escreveu: valide na importação.

## Make e Zapier

- Make: módulo "HTTP > Make a request", método POST, corpo JSON como acima, depois um "Router" filtrando `decisao = escalar`.
- Zapier: ação "Webhooks by Zapier > Custom Request" com o mesmo corpo, e um "Filter" em `decisao`.

## Segurança

Servidor escuta só em `127.0.0.1`. Para expor, use um proxy reverso com HTTPS e defina `COMANDA_TOKEN`.
