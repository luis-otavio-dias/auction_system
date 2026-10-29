# Fase 6 — Tempo real, notificações e polling

**Status:** concluída (backend implementado; ver relatório)
**Depende de:** Fase 5

---

## 1. Objetivo

Atualizar a sala do lote sem recarregar a página, enviar notificações de
superação/vitória e manter o estado consistente mesmo quando o WebSocket falha.

---

## 2. Escopo

- ASGI com roteamento WebSocket.
- Autenticação de WebSocket por ticket efêmero.
- Validação de origem.
- `LotConsumer`.
- `NotificationConsumer`.
- Eventos de lote e usuário.
- `state_version` em todos os eventos.
- Publicação após commit.
- Polling de fallback.
- Testes com `WebsocketCommunicator`.

Fora do escopo: Redis, múltiplas instâncias e notificações push nativas.

---

## 3. Configuração

- `InMemoryChannelLayer`.
- Uma réplica e um processo uvicorn.
- `uvicorn[standard]`.
- `core/asgi.py` com:

```text
http      -> Django ASGI
websocket -> validação de origem + ticket + URLRouter
lifespan  -> ticker de liquidação
```

A documentação do Channels desaconselha a camada em memória em produção. Neste
case, ela é uma concessão consciente para o deploy demonstrativo de uma
instância.

---

## 4. Autenticação do WebSocket

O access token **não** vai na URL.

Fluxo:

1. Frontend autenticado chama `POST /api/auth/ws-ticket`.
2. Backend devolve ticket assinado com `django.core.signing`
   (`TimestampSigner`), `purpose="ws"`, `user_id`, validade de 60 s.
3. Frontend abre:

```text
wss://.../ws/lots/{id}/?ticket=<ticket>
wss://.../ws/notifications/?ticket=<ticket>
```

4. Middleware valida assinatura, `purpose` e `max_age`; carrega o usuário em
   `scope["user"]`.

Comportamento:

- Sala pública do lote: sem ticket = anônimo; ticket inválido/expirado =
  anônimo (somente leitura).
- Notificações: ticket obrigatório; inválido/expirado fecha com `4401`.
- Conexão autenticada tem idade máxima de 15 min
  (`WS_CONNECTION_MAX_AGE_SECONDS`).
- Ao expirar, servidor fecha com `4401`; frontend renova access, pede novo
  ticket e reconecta com backoff.
- A expiração do access token não derruba automaticamente uma conexão aberta;
  o limite de idade força a reautenticação.

### Origem

CORS não vale para WebSocket.

- `AllowedHostsOriginValidator`.
- Allowlist explícita `WS_ALLOWED_ORIGINS`, com fallback para
  `CORS_ALLOWED_ORIGINS`.
- Origem não permitida é rejeitada antes do `accept`.

---

## 5. Consumers

### `LotConsumer`

- URL: `/ws/lots/{lot_id}/`.
- Público para assistir.
- Autenticado recebe posição/status pessoal.
- Ao conectar: grupo `lot_{id}` e snapshot.
- Ao desconectar: sai do grupo.

### `NotificationConsumer`

- URL: `/ws/notifications/`.
- Requer autenticação.
- Grupo `user_{id}`.
- Recebe `user.outbid`, `user.won`, `user.sold`.

---

## 6. Eventos

| Evento | Destino | Conteúdo |
|---|---|---|
| `lot.snapshot` | conexão | estado atual + `state_version` |
| `bid.accepted` | grupo do lote | valor, alias, sequência, `ends_at`, contagem, versão |
| `lot.extended` | grupo do lote | novo `ends_at`, `server_time`, versão |
| `lot.closed` | grupo do lote | vencedor, valor final, comprovante, versão |
| `lot.cancelled` | grupo do lote | motivo, versão |
| `user.outbid` | usuário anterior | “você foi superado” |
| `user.won` | vencedor | link do comprovante |
| `user.sold` | leiloeiro | resultado e valor |

Regras:

- Broadcasts usam `transaction.on_commit`.
- Falha do channel layer não desfaz o lance; apenas loga.
- Nenhum evento contém PII.
- Eventos que alteram o lote carregam `state_version`.
- Eventos fora de ordem são descartados pelo frontend.

---

## 7. Polling de fallback

Mesmo com WebSocket, o frontend mantém:

- polling de `GET /api/lots/{id}` a cada 3–5 s enquanto a sala estiver aberta;
- comparação de `state_version` entre polling, eventos e resposta do `POST /bids`;
- descarte de respostas com versão menor;
- busca de snapshot quando houver salto/inconsistência;
- reconexão com backoff.

Cenário protegido:

1. Polling recebe versão 10 (ao vivo).
2. WS recebe `lot.closed` versão 11.
3. Resposta antiga do polling chega depois.
4. Frontend ignora versão 10 e mantém 11.

O polling cobre:

- queda do WebSocket;
- proxy sem suporte a upgrade;
- múltiplas instâncias no futuro;
- reinício do processo;
- eventos entregues fora de ordem.

---

## 8. Limitação de múltiplas instâncias

`InMemoryChannelLayer` não compartilha eventos entre processos.

Se houver múltiplos workers/instâncias:

- usar Redis externo via `REDIS_URL` + `channels-redis`; ou
- aceitar polling como mecanismo principal.

No modo polling, há atraso e notificações efêmeras podem desaparecer. O estado
do lote continua recuperável via HTTP.

Um cron/worker futuro pode liquidar pelo banco, mas seus broadcasts não chegam
ao processo web; o polling recupera o estado.

---

## 9. API

| Método | Rota | Acesso | Função |
|---|---|---|---|
| POST | `/api/auth/ws-ticket` | autenticado | ticket efêmero |
| WS | `/ws/lots/{id}/?ticket=` | público/autenticado | sala do lote |
| WS | `/ws/notifications/?ticket=` | autenticado | notificações |

---

## 10. Testes

- conexão pública na sala;
- autenticação de notificações por ticket;
- ticket expirado em notificações fecha `4401`;
- ticket expirado na sala pública cai para anônimo;
- origem não permitida é rejeitada antes do `accept`;
- snapshot ao conectar com `state_version`;
- broadcast após commit;
- nenhum broadcast em rollback;
- `bid.accepted` atualiza sala;
- `user.outbid` para o líder anterior;
- `lot.closed` com versão maior que snapshot antigo;
- resposta HTTP atrasada é ignorada pelo cliente;
- polling funciona com WS desconectado.

---

## 11. Critérios de aceite

- [x] Sala do lote atualiza sem recarregar.
- [x] WebSocket autentica por ticket e valida origem.
- [x] Notificações de outbid/vitória funcionam.
- [x] Eventos só saem após commit.
- [x] `state_version` evita regressão de estado.
- [x] Polling cobre queda do WS.
- [x] Limitação de uma instância documentada.
- [x] Testes verdes.

---

## 12. Riscos

| Risco | Mitigação |
|---|---|
| InMemory em produção | concessão para uma instância; Redis no futuro |
| WS não cruza processos | polling com atraso |
| Notificação perdida | polling recupera estado |
| Ticket vazado | curta duração + HTTPS |
| Origem indevida | allowlist explícita |
| Evento fora de ordem | `state_version` |
| Broadcast antes do commit | `transaction.on_commit` |

---

## 13. Checklist

- [x] Configurar `core/asgi.py`.
- [x] Criar middleware de ticket/origem.
- [x] Criar `LotConsumer`.
- [x] Criar `NotificationConsumer`.
- [x] Criar endpoint de ticket.
- [x] Ligar eventos aos serviços das fases 3/4.
- [x] Criar contrato de polling no frontend.
- [x] Criar testes com `WebsocketCommunicator`.
- [x] Rodar lint, tipos e testes.
- [x] Relatório em [`../implemented/fase-6.md`](../implemented/fase-6.md).
