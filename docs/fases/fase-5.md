# Fase 5 — Auditoria pública e âncora

**Status:** concluída (backend implementado; ver relatório)
**Depende de:** Fase 4

---

## 1. Objetivo

Permitir que qualquer pessoa, sem login, consulte o resultado da verificação do
histórico de lances de um lote e do comprovante, com garantias explícitas sobre
o que o desenho detecta e o que não detecta.

---

## 2. Escopo

- Serviço de verificação da cadeia de lances.
- Endpoint público de auditoria.
- Checkpoint externo em arquivo append-only.
- Endpoint público de verificação do comprovante.
- Testes de adulteração.
- Documentação da técnica e do modelo de ameaça.
- Explicação da diferença entre verificação pelo backend e verificação
  independente.

Fora do escopo: assinatura Ed25519 e prova independente completa; isso fica
como evolução opcional.

---

## 3. Técnica

Para cada lance:

```text
content_hash = SHA-256(JSON canônico)
hash = HMAC-SHA256(BID_HISTORY_SECRET, prev_hash + ":" + content_hash)
```

Payload canônico:

```json
{
  "lot_id": "uuid",
  "sequence": 1,
  "bidder_id": "uuid",
  "bidder_alias": "Licitante-7F3A9C",
  "amount": "1500.00",
  "placed_at": "2026-10-27T12:00:00.000000Z",
  "ends_at_before": "2026-10-27T18:00:00.000000Z",
  "ends_at_after": "2026-10-27T18:00:00.000000Z",
  "prev_hash": "0000000000000000000000000000000000000000000000000000000000000000",
  "hash_version": 1
}
```

- Primeiro `prev_hash` é 64 zeros.
- `bidder_id` entra no hash, mas não é exposto publicamente.
- `Lot.history_head` e `Lot.bids_count` são atualizados na mesma transação do
  lance.
- O segredo fica em `BID_HISTORY_SECRET`, fora do banco.
- `hash_version` permite evolução.
- Não rotacionar o segredo sem plano de múltiplas chaves.

---

## 4. Verificação

A auditoria deve:

1. Buscar lances ordenados por `sequence`.
2. Verificar sequência contínua 1..n.
3. Recalcular `content_hash`.
4. Verificar `prev_hash`.
5. Recalcular HMAC.
6. Comparar `bids_count`.
7. Comparar `history_head`.
8. Comparar com checkpoint externo, se existir.
9. Retornar `valid`, `head_hash`, `bid_count`, `first_invalid_sequence`,
   `anchor_status` e falhas.

Códigos:

- `SEQUENCE_GAP`
- `PREV_HASH_MISMATCH`
- `CONTENT_HASH_MISMATCH`
- `CHAIN_HASH_MISMATCH`
- `COUNT_MISMATCH`
- `HEAD_MISMATCH`
- `ROLLBACK_DETECTED`

`ANCHOR_UNAVAILABLE` não é falha de integridade; é status da garantia adicional.

---

## 5. Âncora externa

Arquivo append-only:

```env
BID_ANCHOR_PATH=/caminho/fora-do-banco/bid_anchors.jsonl
```

Linha:

```json
{"lot_id":"...","sequence":3,"head":"...","count":3,"recorded_at":"..."}
```

- Escrita após o commit do lance.
- Se o processo cair entre commit e escrita, a âncora pode ficar atrasada.
- Arquivo ausente/atrasado retorna `unavailable`/`behind`, nunca `adulterado`.
- Arquivo no mesmo servidor protege contra atacante restrito ao banco, não
  contra quem controla o servidor.
- `Receipt` no mesmo banco não protege contra rollback completo.
- Para garantia mais forte, usar log externo append-only, object storage com
  versionamento/object lock ou outro serviço fora do controle do atacante.

---

## 6. Garantias

| Objetivo | Situação |
|---|---|
| Consulta pública ao resultado da verificação | Atendido |
| Detectar alteração/inserção/remoção sem o segredo | Atendido, com limites de rollback |
| Verificação independente pelo visitante | Não atendido pelo HMAC |
| Detectar rollback completo do banco | Só com checkpoint externo confiável |
| Resistir a atacante com segredo + controle total | Não garantido |

O README e o endpoint devem deixar isso explícito. O visitante consulta a
verificação feita pelo backend; ele não reproduz o HMAC sozinho.

---

## 7. Comprovante

`Receipt.verification_hash`:

```text
HMAC-SHA256(RECEIPT_SECRET, payload canônico do comprovante)
```

Payload inclui:

- `token`, `lot_id`, `lot_code`;
- `winner_alias`, `seller_alias`;
- `item_source`, `item_external_id`, `item_title`, `item_image_url`;
- `final_price`, `issued_at`;
- `audit_head`, `bid_count`, `hash_version`.

Verificação retorna:

```json
{
  "receipt_valid": true,
  "history_valid": true,
  "head_matches": true,
  "bid_count": 3,
  "anchor_status": "ok"
}
```

- `receipt_valid` é HMAC verificado pelo backend, não prova independente.
- `history_valid` compara o head congelado com a cadeia atual.
- `anchor_status` não trata ausência como adulteração.

---

## 8. API

| Método | Rota | Acesso | Função |
|---|---|---|---|
| GET | `/api/lots/{id}/audit` | público | histórico + verificação |
| GET | `/api/receipts/{token}/verify` | público | verificação do comprovante |

A auditoria não exige login, não chama a AIC e não expõe PII.

Resposta de auditoria deve incluir:

- `valid`;
- `head_hash`;
- `bid_count`;
- `anchor_status`;
- `first_invalid_sequence`;
- `failures`;
- lances com `sequence`, `amount`, `bidder_alias`, `placed_at`, `prev_hash`,
  `content_hash`, `hash`.

---

## 9. Testes

- histórico íntegro;
- alteração de valor via SQL;
- alteração de alias/data;
- inserção de lance falso;
- remoção de lance do meio;
- remoção do último;
- reordenação;
- rollback com checkpoint externo;
- âncora ausente/atrasada não vira adulteração;
- rollback completo sem checkpoint é limitação documentada;
- comprovante íntegro/adulterado;
- comprovante sozinho não protege rollback do banco;
- ausência de PII.

---

## 10. Critérios de aceite

- [x] Endpoint público retorna `valid=true` para histórico íntegro.
- [x] UPDATE/INSERT/DELETE direto no banco é detectado.
- [x] Rollback com âncora é detectado quando o checkpoint está disponível.
- [x] Ausência de âncora não é tratada como adulteração.
- [x] Comprovante é verificável sem login e sem PII.
- [x] Limitações estão escritas no README e na resposta da API.
- [x] Testes verdes.

---

## 11. Riscos

| Risco | Mitigação |
|---|---|
| Overclaim de garantia | documentar HMAC vs verificação independente |
| Rollback completo | checkpoint externo confiável |
| Arquivo atrasado | `unavailable`/`behind`, não inválido |
| Segredo vazado | rotação planejada e variável de ambiente |
| PII no payload | alias snapshot; `bidder_id` só no hash |
| Performance | verificação linear; lotes pequenos |

---

## 12. Evolução opcional

Para verificação independente:

- payload público sem `bidder_id`;
- cadeia SHA-256 reproduzível;
- assinatura Ed25519 por lance/checkpoint;
- chave pública publicada;
- checkpoint em log externo append-only.

Isso aumenta complexidade de chaves, rotação e operação; não é necessário para o
case se a verificação pelo backend for aceita.

---

## 13. Checklist

- [x] Implementar canonicalização.
- [x] Implementar verificação da cadeia.
- [x] Criar endpoint de auditoria.
- [x] Criar escrita/leitura da âncora.
- [x] Criar verificação do comprovante.
- [x] Criar testes de adulteração.
- [x] Documentar garantias e limitações.
- [x] Relatório em [`../implemented/fase-5.md`](../implemented/fase-5.md).
- [x] Rodar lint, tipos e testes.
