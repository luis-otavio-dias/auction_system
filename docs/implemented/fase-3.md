# Fase 3 — Lances, carteira comprometida e anti-sniping

**Status:** concluída  
**Data:** 2026-10-27  
**Documento de aceite:** [`../fases/fase-3.md`](../fases/fase-3.md)

## Resumo

Implementado o `Bid` imutável, reserva/liberação idempotente de carteira,
serviço transacional de lance, cadeia de hashes, idempotência, regras e
anti-sniping de dois minutos. As APIs expõem histórico e posição sem PII, com
`is_mine` somente para contexto autenticado.

## Arquivos, modelos e migrations

- Alterados: `auctions/models.py`, serializers, views, URLs, `core/settings.py`
  e serviços de domínio.
- Criados: `auctions/services/integrity.py`, `auctions/services/bidding.py`,
  migration `auctions/0002_bid.py` e testes `test_bidding.py`.
- `Bid` usa UUID, FKs PROTECT, sequência única por lote, chave client opcional
  única por licitante/lote, valor positivo, alias snapshot, horários e hashes.

## Serviços, endpoints e eventos

- `wallet.services.hold/release` bloqueiam carteira, atualizam `committed` e
  registram `BID_HOLD`/`BID_RELEASE` com idempotência.
- `place_bid` bloqueia Lot antes das carteiras ordenadas por PK; captura hora
  após locks, devolve replay antes de validações mutáveis, substitui hold, cria
  lance e atualiza líder, contagem, head, prazo e versão na mesma transação.
- Anti-sniping estende apenas quando `now + 2 min` ultrapassa o prazo; a borda
  de exatamente 120 segundos não estende.
- `POST/GET /api/lots/{id}/bids`, `GET /api/lots/{id}` com `my_position` e
  `GET /api/me/bids`; endpoints de wallet constam no relatório da fase 7.
- Replay idempotente é verificado antes do estado mutável, inclusive após o
  encerramento; uma chave divergente não cria reserva nem transação extra.
- Eventos aceitos são preparados para publicação após commit na fase 6.

## Testes e qualidade

- 52 testes relacionados ao domínio de lotes/lances foram coletados na fase;
  suíte integral final da fase: **120 passaram**, incluindo concorrência real
  PostgreSQL e bordas 121/120/119 segundos.
- Comandos verdes: `uv run ruff check .`, `uv run ruff format --check .`,
  `uv run mypy .`, `uv run python manage.py check`,
  `uv run python manage.py makemigrations --check --dry-run` e `uv run pytest`.
- Migrations aplicadas via PostgreSQL local com `uv run python manage.py
  migrate`.

## Limitações e decisões

O payload inclui o UUID do licitante apenas no HMAC; APIs/eventos públicos
exibem alias. A concorrência depende de PostgreSQL; SQLite não oferece a
garantia requerida para `select_for_update`.

## Ajustes finais

- `place_bid_result` informa replay ao endpoint; reenvio idempotente retorna
  HTTP 200, corpo original e `Idempotent-Replayed: true`; novo lance continua
  HTTP 201. Erro de saldo inclui `available` e `minimum_bid`.
- `my_position.rank` usa a posição pela sequência real, e `/api/me/bids`
  identifica lote por UUID, código e título.
- Foram adicionados testes PostgreSQL com barreira para a mesma carteira em
  dois lotes e para lance bloqueado pelo lock do lote enquanto a expiração é
  confirmada. Também cobrem os códigos de rejeição solicitados e POST HTTP.
- A suíte backend completa passou com **165 testes**.
