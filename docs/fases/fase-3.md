# Fase 3 — Lances, carteira comprometida e anti-sniping

**Status:** concluída (backend implementado; ver relatório)
**Depende de:** Fase 2

---

## 1. Objetivo

Permitir que licitantes disputem lotes ao vivo com lances válidos, saldo
comprometido consistente e histórico preparado para auditoria.

A fase termina antes da liquidação. Um lote pode ser encerrado por tempo, mas
ainda não gera comprovante nem movimenta o saldo definitivamente.

---

## 2. Escopo

- Model `Bid` imutável com sequência e hashes.
- Serviços `hold` e `release` na carteira.
- Serviço `place_bid` transacional.
- Regras exatas de valor, líder e saldo disponível.
- Anti-sniping.
- Idempotência de lance.
- Códigos de erro.
- Endpoints de lance e histórico.
- `state_version` nas respostas.
- Testes de concorrência.

Fora do escopo: liquidação, comprovante, auditoria pública e WebSocket.

---

## 3. Modelo `Bid`

| Campo | Tipo | Observação |
|---|---|---|
| `id` | UUID | PK |
| `lot` | FK Lot PROTECT | `related_name="bids"` |
| `bidder` | FK User PROTECT | privado |
| `bidder_alias` | CharField(24) | snapshot público |
| `sequence` | PositiveInteger | 1..n por lote |
| `amount` | Decimal(12,2) | valor exato |
| `placed_at` | DateTimeField | horário do servidor |
| `prev_hash` | CharField(64) | genesis = 64 zeros |
| `content_hash` | CharField(64) | SHA-256 do payload canônico |
| `hash` | CharField(64) | HMAC da cadeia |
| `hash_version` | PositiveSmallInteger | versão do algoritmo |
| `ends_at_before` | DateTimeField | |
| `ends_at_after` | DateTimeField | |
| `client_bid_id` | UUID nullable | idempotência |
| `created_at` | DateTimeField | |

Constraints:

```text
unique(lot, sequence)
unique(lot, bidder, client_bid_id) quando client_bid_id não é nulo
amount > 0
sequence > 0
```

- Imutável; sem update/delete pela API ou admin.
- `bidder_alias` é snapshot.
- `bidder_id` entra no payload do hash, mas não é exposto publicamente.
- `content_hash` e `hash` serão verificados na Fase 5.

---

## 4. Regras de lance

Um lance só é aceito se:

1. O lote existe e não está cancelado.
2. O lote não está liquidado.
3. `starts_at <= now < ends_at`.
4. O usuário é `BIDDER`.
5. O usuário não é o vendedor.
6. O usuário não é o líder atual.
7. O valor é exatamente:
   - `starting_bid`, se não há lances;
   - `current_bid + min_increment`, se já há.
8. `amount <= wallet.available`, onde `available = balance - committed`.

O valor não pode ser maior nem menor que o esperado; o enunciado exige
igualdade.

### Anti-sniping

```text
new_ends_at = max(ends_at, now + 2 min)
if new_ends_at > ends_at:
    ends_at = new_ends_at
    extension_count += 1
```

- `ends_at_before` e `ends_at_after` sempre registrados.
- Exatamente a 2 minutos, não há extensão.
- `original_ends_at` nunca muda.
- `state_version` incrementa na mesma transação do lance.

---

## 5. Carteira

Adicionar aos serviços existentes:

```text
hold(wallet, amount, reference_kind, reference_id)
release(wallet, amount, reference_kind, reference_id)
```

Regras:

- Lock da carteira com `select_for_update`.
- Hold incrementa `committed`.
- Release decrementa `committed`.
- Não permitir `committed > balance`.
- Cada operação grava `WalletTransaction`:
  - `BID_HOLD`;
  - `BID_RELEASE`.
- `reference_kind=BID` e `reference_id=bid.id`.
- Idempotência quando aplicável.

O vencedor só é debitado na Fase 4.

---

## 6. Fluxo transacional de `place_bid`

Tudo em `transaction.atomic()`:

1. Lock do lote.
2. Busca de idempotência por `(lot, bidder, client_bid_id)`.
   - mesmo conteúdo: retorna resultado original;
   - conteúdo diferente: `IDEMPOTENCY_KEY_REUSED`;
   - sem chave: continua.
3. Identificar líder atual.
4. Lock das carteiras do licitante e do líder em ordem de PK.
5. Capturar `now = timezone.now()` **depois de todos os locks**.
6. Validar papel, vendedor, cancelamento, liquidação e prazo.
7. Calcular valor esperado.
8. Validar igualdade, auto-lance e disponibilidade.
9. Liberar hold do líder anterior.
10. Reservar hold do novo lance.
11. Criar `Bid` com sequência, hashes e snapshots de `ends_at`.
12. Atualizar `current_bid`, `current_winner`, `bids_count`, `history_head` e
    `state_version`.
13. Aplicar anti-sniping com o mesmo `now`.
14. Gravar lançamentos financeiros.
15. Agendar eventos com `transaction.on_commit` (os consumers chegam na Fase 6).

Ordem de lock:

```text
Lot -> carteiras ordenadas por PK
```

A ordem vale para lance, cancelamento, liquidação e operações em lote.

---

## 7. Idempotência

- `POST /api/lots/{id}/bids` aceita `client_bid_id`.
- Mesma chave + mesmo conteúdo retorna o lance original.
- Mesma chave + valor diferente retorna `409 IDEMPOTENCY_KEY_REUSED`.
- Replay não cria reserva, lançamento, hash, sequência nem notificação.
- Replay após encerramento retorna o resultado original.
- O frontend gera o UUID antes do request e reutiliza em retries.

---

## 8. API

| Método | Rota | Acesso | Função |
|---|---|---|---|
| POST | `/api/lots/{id}/bids` | licitante | dar lance |
| GET | `/api/lots/{id}/bids` | público | histórico paginado |
| GET | `/api/lots/{id}` | público/autenticado | inclui `my_position` |
| GET | `/api/me/bids` | licitante | lotes em que deu lance |

`my_position` deve conter:

- `is_leading`;
- `status`: `leading`, `outbid` ou `no_bid`;
- último lance do usuário;
- rank/posição quando aplicável.

Histórico público:

- `sequence`, `amount`, `bidder_alias`, `placed_at`;
- `is_mine` apenas em contexto autenticado;
- nunca expor email, nome ou ID de usuário.

---

## 9. Códigos de erro

| Código | HTTP | Situação |
|---|---|---|
| `LOT_NOT_STARTED` | 409 | antes de `starts_at` |
| `LOT_ENDED` | 409 | depois de `ends_at` |
| `LOT_CANCELLED` | 409 | lote cancelado |
| `LOT_SETTLED` | 409 | lote liquidado |
| `BID_AMOUNT_MISMATCH` | 422 | valor diferente do esperado |
| `BID_BELOW_MINIMUM` | 422 | valor abaixo do mínimo |
| `ALREADY_LEADING` | 409 | líder cobrindo o próprio lance |
| `INSUFFICIENT_FUNDS` | 409 | disponível insuficiente |
| `SELLER_CANNOT_BID` | 403 | leiloeiro tentando dar lance |
| `FORBIDDEN_ROLE` | 403 | papel incorreto |
| `IDEMPOTENCY_KEY_REUSED` | 409 | chave com conteúdo diferente |

---

## 10. Testes

### Regras

- primeiro lance igual ao inicial;
- lance seguinte igual a atual + incremento;
- valor acima/abaixo recusado;
- antes do início e depois do fim;
- líder não cobre o próprio lance;
- saldo insuficiente;
- leiloeiro não dá lance;
- lote cancelado/liquidado.

### Concorrência

- dois lances simultâneos no mesmo lote: apenas um aceito;
- disputa da mesma carteira em dois lotes: holds somam e não estouram o
  disponível;
- lance contra encerramento: `now` é o capturado depois dos locks;
- replay após fechamento retorna original;
- nenhuma cobrança dupla.

### Anti-sniping

- fora dos últimos 2 minutos não prorroga;
- dentro prorroga para `now + 2 min`;
- exatamente 2 minutos não prorroga nem incrementa contador;
- múltiplas prorrogações;
- `original_ends_at` preservado.

---

## 11. Critérios de aceite

- [x] Lance válido atualiza lote e carteira na mesma transação.
- [x] Líder anterior tem o hold liberado imediatamente.
- [x] Líder não consegue cobrir o próprio lance.
- [x] Saldo insuficiente é recusado com mensagem clara.
- [x] Anti-sniping funciona nos limites.
- [x] Idempotência não movimenta saldo em replay.
- [x] Concorrência não corrompe lote, carteira ou sequência.
- [x] Histórico público não expõe PII.
- [x] `state_version` incrementa corretamente.

---

## 12. Riscos

| Risco | Mitigação |
|---|---|
| Deadlock | ordem fixa de locks |
| Cobrança dupla | idempotência + unique constraints |
| Lote expirando durante espera | `now` após locks |
| Hash inconsistente | payload canônico e testes |
| Saldo negativo | constraints e revalidação |
| Replay após fim | busca antes de validar prazo |

---

## 13. Checklist

- [x] Model `Bid`, constraints, índices e migration.
- [x] Serviços de carteira e `place_bid` transacional.
- [x] Idempotência, cadeia/hash, snapshots e anti-sniping.
- [x] Endpoints e serializers sem PII.
- [x] Testes de regras, concorrência PostgreSQL e limites temporais.
- [x] Comandos de qualidade executados; suite verde.
- [x] Relatório em [`../implemented/fase-3.md`](../implemented/fase-3.md).

- [x] Criar `Bid` e migration.
- [x] Implementar `hold`/`release`.
- [x] Implementar `place_bid`.
- [x] Implementar hashes e `history_head`.
- [x] Criar endpoints e serializers.
- [x] Criar `my_position`.
- [x] Criar testes de concorrência.
- [x] Rodar lint, tipos, migrations e testes.
