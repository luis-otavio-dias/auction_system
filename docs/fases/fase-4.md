# Fase 4 — Liquidação, comprovante e ticker

**Status:** concluída (backend implementado; ver relatório)
**Depende de:** Fase 3

---

## 1. Objetivo

Encerrar lotes com segurança financeira: validar o resultado, debitar o
vencedor, creditar o leiloeiro, gerar comprovante e expor os painéis de
resultados.

A fase termina antes da auditoria pública completa e do tempo real.

---

## 2. Escopo

- Model `Receipt` imutável.
- Serviço `settle_lot`.
- Validação de integridade antes de cobrar.
- `settle_due_lots` e `settle_if_due`.
- Ticker no ASGI lifespan.
- Comando `close_due_lots`.
- Resumo do leiloeiro.
- “Meus arremates”.
- Health do ticker.
- Testes de liquidação e concorrência.

Fora do escopo: auditoria pública, âncora externa, WebSocket e frontend.

---

## 3. Modelo `Receipt`

| Campo | Tipo | Observação |
|---|---|---|
| `id` | UUID | PK |
| `token` | UUID unique | link público não adivinhável |
| `code` | CharField(16) unique | código curto |
| `lot` | OneToOne(Lot) | `related_name="receipt"` |
| `winner` | FK User PROTECT | privado |
| `winner_alias` | CharField(24) | snapshot público |
| `seller_alias` | CharField(24) | snapshot público |
| `lot_code` | CharField(12) | snapshot |
| `item_source` | CharField(32) | identificação imutável do item |
| `item_external_id` | CharField(64) | identificação imutável do item |
| `item_title` | CharField(300) | snapshot |
| `item_image_url` | URLField | snapshot |
| `final_price` | Decimal(12,2) | valor arrematado |
| `issued_at` | DateTimeField | |
| `audit_head` | CharField(64) | head no encerramento |
| `bid_count` | PositiveInteger | |
| `verification_hash` | CharField(64) | HMAC do comprovante |
| `hash_version` | PositiveSmallInteger | |
| `created_at` | DateTimeField | |

- Imutável.
- Público por `token`.
- Nunca expõe email, nome ou ID de usuário.
- O payload do HMAC inclui os snapshots de vendedor, item, valor, head e
  contagem.
- O `Receipt` no mesmo banco é um snapshot, não uma âncora externa.

---

## 4. Serviço de liquidação

### 4.1 `settle_lot`

Tudo em transação curta:

1. Lock do lote.
2. Verificar `ends_at <= now`, `cancelled_at is null` e `settled_at is null`.
3. Capturar `now` depois dos locks.
4. Validar integridade do resultado.
5. Liquidar ou registrar falha.
6. Incrementar `state_version`.
7. Agendar eventos com `transaction.on_commit`.

### 4.2 Validação de integridade

Antes de cobrar:

1. O último lance (`sequence == bids_count`) existe.
2. O último lance pertence a `current_winner`.
3. O valor do último lance é igual a `current_bid`.
4. `bids_count` e `history_head` correspondem à cadeia.
5. A cadeia HMAC do histórico está íntegra.
6. Existe hold ativo compatível com o valor devido:
   - último lançamento do `bid` é `BID_HOLD`;
   - valor do hold é igual a `final_price`;
   - não há `BID_RELEASE`/`SETTLEMENT_DEBIT` posterior para o mesmo lance;
   - `wallet.committed >= final_price`.
7. Carteira do vencedor e do leiloeiro pertencem aos usuários corretos.

Em inconsistência:

- não cobra;
- não credita;
- não cria comprovante;
- não preenche `settled_at`;
- grava `settlement_error` e `settlement_checked_at`;
- loga o erro;
- bloqueia novas tentativas automáticas daquele lote;
- interrompe apenas aquele lote.

### 4.3 Liquidação com lances

- Vencedor = `current_winner`.
- Valor final = `current_bid`.
- Debita `balance` e `committed` do vencedor.
- Credita `balance` do leiloeiro.
- Cria lançamentos `SETTLEMENT_DEBIT` e `SETTLEMENT_CREDIT`.
- Cria `Receipt` com snapshots.
- Preenche `winner`, `final_price`, `settled_at`.
- Incrementa `state_version`.
- Publica `lot.closed`, `user.won`, `user.sold` (a publicação real será ligada
  na Fase 6; nesta fase os eventos podem ser registrados/serializados).

### 4.4 Lote sem lances

- Preenche `settled_at`.
- `winner` e `final_price` ficam nulos.
- Não cria comprovante.
- Incrementa `state_version`.

### 4.5 Lote cancelado

- Não liquida.
- Não cria comprovante.
- O hold ativo já deve ter sido liberado no cancelamento.

---

## 5. Ticker sem worker

O deploy é uma única instância/processo uvicorn, sem Redis e sem worker
separado.

Implementação:

- Wrapper de lifespan em `core/asgi.py`.
- No startup, processa lotes vencidos antes de dormir.
- Loop a cada `SETTLEMENT_INTERVAL_SECONDS` (5 s).
- Lote máximo de `SETTLEMENT_BATCH_SIZE` (50) por execução.
- Uma transação curta por lote.
- `database_sync_to_async` ou equivalente para manter a transação fora do
  event loop.
- Falha isolada por lote; um erro não bloqueia os seguintes.
- Shutdown cancela a task e aguarda.
- `ENABLE_SETTLEMENT_TICKER=false` desliga.
- Nos testes, o ticker fica desligado; serviços são chamados diretamente.
- `close_due_lots --once` disponível para cron futuro.
- `settle_if_due(lot)` chamado nos endpoints de detalhe, auditoria, arremates e
  resumo do leiloeiro.

Limitação: se o servidor estiver suspenso, não há liquidação até ele voltar.
O polling/liquidação sob demanda cobre apenas acessos.

---

## 6. Health e observabilidade

`GET /health/settlement/`:

```json
{
  "ticker_enabled": true,
  "last_run_at": "...",
  "last_success_at": "...",
  "due_count": 0,
  "blocked_count": 0
}
```

- Sem PII.
- `last_run_at`/`last_success_at` podem usar memória/cache local.
- Após restart, ficam vazios até a primeira execução.

---

## 7. API

| Método | Rota | Acesso | Função |
|---|---|---|---|
| GET | `/api/seller/lots` | leiloeiro | próprios lotes |
| GET | `/api/seller/summary` | leiloeiro | total recebido e resultado |
| GET | `/api/me/wins` | licitante | arremates + comprovante |
| GET | `/api/receipts/{token}` | público | comprovante |
| GET | `/api/receipts/{token}/verify` | público | verificação futura |
| GET | `/health/settlement/` | público/ops | estado do ticker |

`/api/seller/summary`:

- total recebido;
- lote, item, valor final, vencedor alias, data;
- lotes sem arremate;
- lotes bloqueados por `settlement_error`.

`/api/me/wins`:

- lotes vencidos;
- valor final;
- link do comprovante;
- data de emissão.

---

## 8. Testes

### Liquidação

- vencedor debitado e leiloeiro creditado;
- comprovante gerado;
- lote sem lances encerra sem vencedor;
- cancelado não liquida;
- liquidação concorrente idempotente;
- `state_version` incrementa;
- `settlement_error` bloqueia nova tentativa;
- comprovante inclui `seller_alias`, `lot_code`, `item_source` e
  `item_external_id`.

### Integridade

- `current_winner` divergente do último lance bloqueia;
- `current_bid` divergente bloqueia;
- `bids_count`/`history_head` divergentes bloqueiam;
- hold incompatível bloqueia;
- falha de um lote não impede os seguintes.

### Ticker

- startup processa vencidos;
- shutdown encerra a task;
- lote limitado por execução;
- transação por lote;
- health responde.

---

## 9. Critérios de aceite

- [x] Lote encerrado com lance gera comprovante.
- [x] Vencedor é debitado e leiloeiro creditado corretamente.
- [x] Lote sem lance encerra sem vencedor e sem comprovante.
- [x] Inconsistência impede cobrança e fica registrada.
- [x] Ticker liquida sem worker e lida com falhas isoladas.
- [x] Comprovante público não expõe PII.
- [x] Testes e migrations verdes.

---

## 10. Riscos

| Risco | Mitigação |
|---|---|
| Cobrança incorreta | validação de integridade antes do débito |
| Liquidação dupla | lock + `settled_at` + transação |
| Ticker parado | liquidação sob demanda + health |
| Servidor suspenso | documentar pendência financeira |
| Lote bloqueado | `settlement_error` e ação administrativa |
| Snapshot insuficiente | campos explícitos no `Receipt` |

---

## 11. Checklist

- [x] Criar `Receipt` e migration.
- [x] Implementar `settle_lot`.
- [x] Implementar validação de integridade.
- [x] Implementar `settle_due_lots`/`settle_if_due`.
- [x] Criar ticker ASGI e comando.
- [x] Criar resumo do leiloeiro e meus arremates.
- [x] Criar health do ticker.
- [x] Criar testes.
- [x] Rodar lint, tipos, migrations e testes.
- [x] Relatório em [`../implemented/fase-4.md`](../implemented/fase-4.md).
