# Fase 4 — Liquidação, comprovante e ticker

**Status:** concluída  
**Data:** 2026-10-27  
**Documento de aceite:** [`../fases/fase-4.md`](../fases/fase-4.md)

## Resumo

Entregues liquidação idempotente, validação de histórico e hold antes de
qualquer débito, recibo imutável assinado, ticker no lifespan ASGI, comando
operacional e painéis de resultados. Lotes com inconsistência ficam bloqueados
com registro de `settlement_error` e timestamp, sem transação financeira.

## Arquivos, modelos e migrations

- `auctions/models.py`: model `Receipt` com snapshots privados e públicos,
  token público, HMAC, head/contagem e criação apenas uma vez.
- Migration `auctions/0003_receipt.py`, gerada e aplicada no PostgreSQL local.
- Criados `auctions/services/settlement.py`, `core/settlement_ticker.py` e
  `auctions/management/commands/close_due_lots.py`; alterações em ASGI,
  settings, URLs, views e serializers.
- `core/asgi.py` controla startup, batch, isolamento de erros e shutdown;
  `ENABLE_SETTLEMENT_TICKER` desliga o loop.

## Serviços, endpoints e eventos

- `settle_lot`, `settle_if_due` e `settle_due_lots` validam contagem, cadeia,
  líder/valor, hold e carteiras sob lock antes de transferir valores.
- Lote sem lance encerra sem recibo; cancelado é ignorado; lote corrompido
  registra erro sem cobrar.
- APIs: `/api/seller/lots`, `/api/seller/summary`, `/api/me/wins`,
  `/api/receipts/{token}`, `/health/settlement/`.
- Eventos `lot.closed`, `user.won` e `user.sold` são registrados após commit,
  incluindo `state_version` nos eventos do lote.

## Testes e qualidade

- 9 testes focados de liquidação, isolamento de falha, concorrência e health;
  suíte integral no marco da fase: **128 passaram**.
- Comandos verdes: Ruff, format check, mypy, `manage.py check`,
  `makemigrations --check --dry-run` e pytest.
- `uv run python manage.py migrate`: nenhuma migration pendente.

## Limitações e decisões

O ticker é local ao processo ASGI único. Se o processo for suspenso, os lotes
serão liquidados no retorno do processo ou em leitura sob demanda. Os campos de
health usam cache local e são reiniciados após restart.

## Ajustes finais

- `settle_lot` obtém primeiro os locks ordenados das carteiras e captura o
  `now` definitivo depois; débito e crédito financeiro foram movidos para
  `wallet.services.settle_debit` e `settle_credit`.
- `/api/seller/summary` retorna recebimentos por lote, lotes sem arremate e
  lotes bloqueados; comprovante e `/api/me/wins` expõem `share_url` e
  `issued_at` sem PII.
- Views de painel filtram `settlement_error` antes de liquidação sob demanda.
  Os testes exercitam o batch configurado e o ticker habilitado no startup,
  incluindo liquidação de lote vencido; o serviço de batch cobre falha isolada.
- A suíte backend completa passou com **165 testes**.
