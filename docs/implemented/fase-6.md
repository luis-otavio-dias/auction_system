# Fase 6 — Tempo real, notificações e polling

**Status:** concluída  
**Data:** 2026-10-27  
**Documento de aceite:** [`../fases/fase-6.md`](../fases/fase-6.md)

## Resumo

ASGI agora roteia HTTP, WebSocket e lifespan do ticker. A origem é validada
contra `WS_ALLOWED_ORIGINS` e `AllowedHostsOriginValidator`; tickets curtos com
`TimestampSigner` carregam usuário autenticado sem expor JWT na URL. Consumers
enviam snapshot de lote, posição pessoal, eventos públicos e notificações.

## Arquivos e serviços

- Criados/alterados: `core/asgi.py`, `auctions/ws_auth.py`, `routing.py`,
  `consumers.py`, `events.py`, integrações em serviços de lance, liquidação e
  cancelamento, endpoint `/api/auth/ws-ticket`.
- Falhas do channel layer são registradas e não retornam ao serviço financeiro.
- Ticket expirado na sala pública vira conexão anônima; notificações recusam
  com código 4401. Conexões autenticadas expiram conforme
  `WS_CONNECTION_MAX_AGE_SECONDS`.
- Eventos `lot.snapshot`, `bid.accepted`, `lot.extended`, `lot.closed`,
  `lot.cancelled`, `user.outbid`, `user.won` e `user.sold` são publicados após
  commit; todos os eventos de lote contêm `state_version`.

## Endpoints e polling

- `POST /api/auth/ws-ticket` emite ticket temporário.
- WebSockets: `/ws/lots/{id}/` e `/ws/notifications/`.
- Estado HTTP permanece recuperável via `GET /api/lots/{id}`; o cliente
  compara `state_version` e mantém polling como fallback.

## Testes e qualidade

- 12 testes `WebsocketCommunicator`: origem, ticket expirado, snapshot
  anônimo/autenticado, bid/extension, outbid, close/won, cancelamento,
  rollback sem broadcast e falha channel layer.
- Suíte integral final da fase: **144 passaram**.
- Ruff, format check, mypy, `manage.py check`,
  `makemigrations --check --dry-run` e pytest verdes.

## Limitações e decisões

`InMemoryChannelLayer` exige uma única instância/processo e não replica eventos.
O polling do frontend recupera estado do lote, mas uma notificação efêmera pode
se perder; Redis é a evolução para múltiplos processos.

## Ajustes finais

- Snapshot WS agora calcula rank pela posição real e retorna `null` em
  `no_bid`; notificações `user.outbid`, `user.won` e `user.sold` incluem
  `lot_id` UUID sem PII.
- `bid.accepted` e `lot.extended` usam timestamp UTC com microssegundos e `Z`,
  consistente com snapshots e liquidação.
- A suíte backend completa passou com **165 testes**.
