# Fase 5 — Auditoria pública e âncora

**Status:** concluída  
**Data:** 2026-10-27  
**Documento de aceite:** [`../fases/fase-5.md`](../fases/fase-5.md)

## Resumo

Implementadas canonicalização estável, SHA-256 de conteúdo, HMAC-SHA256
encadeado, verificação integral da cadeia e checkpoint JSONL append-only. A API
pública verifica também snapshots de recibos e explicita que o resultado é
validado pelo backend, sem alegar prova independente.

## Arquivos, modelos e migrations

- `auctions/services/integrity.py`: payload dataclass-like TypedDict, timestamps
  UTC com microssegundos, decimais de duas casas e JSON com chaves ordenadas.
- `auctions/services/audit.py`: verificação, comparação com contagem/head,
  estados de âncora e HMAC de recibo.
- Sem novos modelos/migrations: usa `Bid`, `Lot` e `Receipt` das fases
  anteriores; lances e liquidações gravam checkpoints após commit.
- Testes em `tests/auctions/test_audit.py` cobrem SQL UPDATE/INSERT/DELETE/
  reordenação, falhas específicas, âncora, rollback, recibo e privacidade.

## Serviços e endpoints

- Falhas `SEQUENCE_GAP`, `PREV_HASH_MISMATCH`, `CONTENT_HASH_MISMATCH`,
  `CHAIN_HASH_MISMATCH`, `COUNT_MISMATCH`, `HEAD_MISMATCH` e
  `ROLLBACK_DETECTED` são retornadas publicamente.
- Âncora ausente/atrasada apresenta `unavailable`/`behind` e não torna a cadeia
  inválida; âncora à frente ou com mesmo count e head diferente detecta rollback.
- `GET /api/lots/{id}/audit` e `GET /api/receipts/{token}/verify` não exigem
  login e não expõem PII.

## Testes e qualidade

- 16 testes específicos de auditoria; suíte integral do marco: **138 passaram**.
- Ruff, format check, mypy, `manage.py check`,
  `makemigrations --check --dry-run` e pytest verdes.

## Limitações e decisões

O HMAC é validado pelo próprio backend e não pode ser reproduzido por visitante
sem segredo. Arquivo de âncora no mesmo host protege contra alteração apenas do
banco, não contra controle integral do servidor nem rollback sem checkpoint
externo confiável.

## Ajustes finais

- A verificação avança pela hash persistida do lance, não pela hash recalculada.
  Teste adultera o conteúdo do lance intermediário e confirma que as falhas
  ficam restritas à sequência adulterada, sem cascata nos lances seguintes.
- A suíte backend completa passou com **165 testes**.
