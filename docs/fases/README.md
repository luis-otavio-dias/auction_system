# Fases de implementação

**Relatórios de entrega:** [`../implemented/`](../implemented/)  
**README do projeto:** [`../../README.md`](../../README.md)

Este diretório registra o plano executável e o histórico das fases. Cada
documento tem escopo, dependências, modelos, endpoints, testes, critérios de
aceite e riscos. A ordem recomendada é sequencial: uma fase só começa quando a
anterior estiver validada.

## Status

| Fase | Tema | Status | Depende de | Documento |
|---|---|---|---|---|
| 1 | Fundação: users, wallet, cookies JWT, settings, testes | Concluída | — | [`fase-1.md`](fase-1.md) |
| 2 | Catálogo AIC e lotes | Concluída | Fase 1 | [`fase-2.md`](fase-2.md) |
| 3 | Lances, carteira comprometida e anti-sniping | Concluída | Fase 2 | [`fase-3.md`](fase-3.md) |
| 4 | Liquidação, comprovante e ticker | Concluída | Fase 3 | [`fase-4.md`](fase-4.md) |
| 5 | Auditoria pública e âncora | Concluída | Fase 4 | [`fase-5.md`](fase-5.md) |
| 6 | WebSocket, notificações e polling | Concluída | Fase 5 | [`fase-6.md`](fase-6.md) |
| 7 | Frontend, seed, README e deploy | Concluída | Fase 6 | [`fase-7.md`](fase-7.md) · [`backend`](../implemented/fase-7-backend.md) / [`frontend`](../implemented/fase-7-frontend.md) |

## Dependências

```text
Fase 1 (concluída)
    │
    ▼
Fase 2 — catálogo + lotes
    │
    ▼
Fase 3 — lances + wallet holds
    │
    ▼
Fase 4 — liquidação + comprovante
    │
    ▼
Fase 5 — auditoria pública
    │
    ▼
Fase 6 — tempo real
    │
    ▼
Fase 7 — frontend + seed + deploy
```

## Decisões que valem para todas as fases

- Backend Django 6.1 + DRF + SimpleJWT; Python 3.14.
- Autenticação por cookies HttpOnly com fallback Bearer.
- Refresh com rotação e blacklist; logout revoga o refresh.
- PostgreSQL é obrigatório para concorrência e locks.
- Dinheiro em `Decimal(12,2)`; API devolve string decimal.
- API externa: Art Institute of Chicago (AIC).
- Anti-sniping: `ends_at = max(ends_at, now + 2 min)`, incrementando
  `extension_count` apenas quando o prazo aumentar.
- `Lot.state_version` é o contrato de reconciliação entre HTTP e WebSocket.
- Idempotência é verificada depois do lock e antes das validações mutáveis.
- Liquidação valida a integridade do histórico antes de cobrar.
- Auditoria é feita pelo backend com HMAC; o visitante consulta o resultado.
  Verificação independente e rollback completo têm limitações documentadas.
- Deploy demonstrativo de uma única instância/processo uvicorn, sem Redis e sem
  worker separado. Channels usa `InMemoryChannelLayer`; polling cobre o atraso.
- Nenhum `# noqa`, `# type: ignore` ou `Any`/`Unknown` como atalho de tipo.

## Regras de atualização

Ao concluir uma fase:

1. Atualizar o status na tabela acima.
2. Registrar o que foi entregue no documento da fase.
3. Rodar lint, format, mypy, migrations e testes.
4. Não iniciar a fase seguinte com critérios de aceite pendentes.
