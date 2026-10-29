# Fase 7 — Frontend integrado

**Status:** concluída  
**Data:** 2026-10-27  
**Escopo:** frontend React/TypeScript consumindo a API real, autenticação por
cookies, vitrine, sala do lote com WebSocket/polling, carteira, painel do
leiloeiro, meus arremates, auditoria pública e comprovante compartilhável.  
**Documento mestre:** [`../fases/fase-7.md`](../fases/fase-7.md)

---

## 1. Resumo

O frontend deixou de usar o catálogo local e passou a consumir os contratos da
API documentados nas fases 3 a 6. A aplicação agora tem rotas reais, sessão por
cookies HttpOnly, cliente HTTP tipado com refresh único em `401`, telas de
carteira e painel do leiloeiro, sala de lances com `state_version`, WebSocket por
ticket efêmero, polling de fallback, notificações de outbid/vitória e páginas
públicas de auditoria e comprovante.

Nenhuma dependência de runtime foi adicionada. `react-router-dom` já existia e
passou a ser efetivamente usado; testes usam `vitest` e
`@testing-library/react`, já presentes no projeto.

O backend das fases 3–7 foi concluído e validado depois desta primeira entrega.
A segunda rodada de integração (seção 13) reconciliou os decoders e chamadas com
as rotas, serializers, consumers e respostas reais, e executou um smoke E2E
contra o servidor em `http://127.0.0.1:8002`, sem alterar `backend/**`.

---

## 2. Rotas entregues

| Rota | Tela | Proteção |
|---|---|---|
| `/` | Vitrine com abas ao vivo, programados e resultados | pública |
| `/lotes/:id` | Sala do lote, lance, posição, histórico e countdown | pública; lance exige licitante |
| `/lotes/:id/auditoria` | Auditoria pública da cadeia de lances | pública |
| `/comprovantes/:token` | Comprovante público e link compartilhável | pública |
| `/carteira` | Saldo, comprometido, disponível, depósito e extrato | autenticado |
| `/painel` | Busca AIC, criação/cancelamento de lotes e resultados | `SELLER` |
| `/meus-arremates` | Arremates, valor final, data e comprovante | autenticado |
| `/login` | Login por e-mail e senha | pública |
| `/cadastro` | Cadastro público quando disponível no backend | pública |
| `*` | Página 404 | pública |

O header é compartilhado por todas as rotas, com navegação por perfil,
notificações em tempo real, link de busca, identificação do usuário e logout.
O layout mantém a tipografia, paleta e componentes do design existente e foi
estendido com CSS responsivo em `src/styles/app.css`.

---

## 3. Camada de API e autenticação

Arquivos principais:

```text
src/api/client.ts       cliente HTTP, refresh único, ApiError, URLs e WS
src/api/json.ts         JsonValue/JsonObject, type guards e decoders base
src/api/decoders.ts     decoders tipados de todos os contratos consumidos
src/api/auth.ts         login, cadastro, logout, me, ws-ticket
src/api/lots.ts         vitrine, detalhe, lances, painel e arremates
src/api/wallet.ts       carteira, depósito e extrato
src/api/catalog.ts      busca AIC, auditoria, comprovante e verificação
```

Decisões:

- base `VITE_API_URL` com padrão `http://localhost:8001`;
- toda requisição usa `credentials: "include"`;
- cookies HttpOnly nunca são lidos pelo JavaScript;
- em `401`, uma única renovação é compartilhada entre requisições concorrentes;
  a requisição original é repetida uma vez;
- falha do refresh dispara `auth:expired`, limpa a sessão e leva ao login;
- erros são convertidos em `ApiError` com `code`, `status`, `detail` e campos
  de validação;
- respostas e payloads são validados por decoders que usam `JsonValue`,
  uniões discriminadas e type guards. Não há `any`, `unknown`, `@ts-ignore`,
  `@ts-expect-error` nem `eslint-disable` em `src/`;
- `tsconfig.app.json` passou a usar `strict: true`.

`POST /api/auth/register` é tentado com fallback de barra final. Quando o
backend não oferece o endpoint (404/405), a tela de cadastro exibe a limitação e
as credenciais do seed.

---

## 4. Contratos consumidos

| Método | Rota | Uso no frontend |
|---|---|---|
| POST | `/api/auth/token/` | login |
| POST | `/api/auth/refresh/` | refresh automático |
| POST | `/api/auth/logout/` | logout |
| GET | `/api/auth/me/` | sessão e perfil |
| POST | `/api/auth/ws-ticket` | ticket de WebSocket |
| GET | `/api/lots` | vitrine com `tab`, `q`, `category`, `sort`, `page` |
| GET | `/api/lots/{id}` | sala, `my_position`, `server_time`, `state_version` |
| GET | `/api/lots/{id}/bids` | histórico paginado |
| POST | `/api/lots/{id}/bids` | lance com `amount` e `client_bid_id` |
| GET | `/api/lots/{id}/audit` | auditoria pública |
| POST | `/api/lots` | criação de lote pelo leiloeiro |
| POST | `/api/lots/{id}/cancel` | cancelamento sem lances |
| GET | `/api/catalog/search?q=` | busca AIC no painel |
| GET | `/api/wallet` | saldo, comprometido e disponível |
| POST | `/api/wallet/deposits` | depósito simulado |
| GET | `/api/wallet/transactions` | extrato paginado |
| GET | `/api/seller/lots` | lotes do leiloeiro |
| GET | `/api/seller/summary` | total recebido, resultado por lote, sem arremate e bloqueios |
| GET | `/api/me/bids` | lotes em que o licitante deu lance (`lot_id`/`lot_code`/`lot_title`) |
| GET | `/api/me/wins` | meus arremates com `issued_at` e `share_url` |
| GET | `/api/receipts/{token}` | comprovante público |
| GET | `/api/receipts/{token}/verify` | verificação do comprovante |
| WS | `/ws/lots/{id}/?ticket=` | eventos da sala |
| WS | `/ws/notifications/?ticket=` | outbid, vitória e venda |

Paginação `{count,next,previous,results}` e respostas em lista simples são
aceitas pelos decoders, cobrindo endpoints de painel que podem evoluir para
paginação.

---

## 5. Vitrine

- abas `live`, `scheduled` e `ended`, com contagens independentes;
- busca por texto, filtro por categoria, ordenação e filtros extras;
- paginação por `next`/`previous` do backend;
- lotes cancelados são ocultados no cliente além do filtro do backend;
- countdown usa `ends_at`; quando a lista não traz `server_time`, o primeiro
  detalhe é consultado para sincronizar o relógio do servidor;
- imagem remota com placeholder local em caso de URL vazia ou quebrada;
- estados de carregamento, erro, vazio e nova tentativa.

---

## 6. Sala do lote e lance

- lance atual, próximo valor exato, incremento, contagem e encerramento;
- `my_position` com indicadores “Você está ganhando”, “Você foi superado” e
  “Você ainda não deu lance”;
- histórico público paginado com “carregar mais”;
- formulário envia `amount` decimal com duas casas e `client_bid_id` UUID;
- o UUID é gerado antes do request e mantido quando a falha é de rede ou `5xx`;
  é descartado em rejeições `4xx` e após sucesso, permitindo retry idempotente;
- mensagens dedicadas para todos os códigos:
  `LOT_NOT_STARTED`, `LOT_ENDED`, `LOT_CANCELLED`, `LOT_SETTLED`,
  `BID_AMOUNT_MISMATCH`, `BID_BELOW_MINIMUM`, `ALREADY_LEADING`,
  `INSUFFICIENT_FUNDS`, `SELLER_CANNOT_BID`, `FORBIDDEN_ROLE` e
  `IDEMPOTENCY_KEY_REUSED`;
- perfil `SELLER` não recebe formulário de lance; visitante recebe convite para
  login preservando o retorno à sala.

---

## 7. Tempo real e `state_version`

Implementação em `src/hooks/useLotRoom.ts`, `src/context/NotificationsProvider.tsx`
e `src/domain/lotState.ts`.

- ticket efêmero obtido em `POST /api/auth/ws-ticket`;
- conexão em `/ws/lots/{id}/?ticket=...` e
  `/ws/notifications/?ticket=...`;
- reconexão com backoff exponencial (1 s até 30 s);
- fechamento `4401` dispara nova tentativa; o cliente HTTP renova o access antes
  de pedir novo ticket;
- limite de idade da conexão de 14 minutos no cliente, seguido de reconexão;
- polling de `GET /api/lots/{id}` a cada 4 segundos enquanto a sala está aberta;
- `lastSeenVersion` por sala: versões menores são descartadas; eventos exigem
  versão estritamente maior; o snapshot achatado do WebSocket pode atualizar
  `my_position`/`server_time` na mesma versão; salto de versão em evento dispara
  snapshot HTTP;
- o guard é aplicado no momento de aplicar a resposta, portanto um polling
  antigo que chega depois de um evento novo não regride o estado;
- eventos `bid.accepted`, `lot.extended`, `lot.closed` e `lot.cancelled` são
  mesclados no lote; `bid.accepted` atualiza o histórico;
- notificações `user.outbid`, `user.won` e `user.sold` aparecem no header, com
  link para lote/comprovante e indicador de conexão.

---

## 8. Carteira, painel, arremates e páginas públicas

### Carteira

Saldo total, comprometido, disponível, depósito simulado com chave de
idempotência, extrato paginado, rótulos por tipo de lançamento, sinais de
crédito/débito e mensagens de erro da API.

### Painel do leiloeiro

Busca na AIC com seleção de item, criação de lote com datas, lance inicial e
incremento, lista paginada dos próprios lotes, cancelamento apenas quando
`bids_count === 0`, resumo com total recebido, resultado por lote
(`lot_id`, `code`, `title`, `final_price`, `winner_alias`, `settled_at`), lotes
sem arremate, lotes bloqueados (`code`, `title`, `settlement_error`) e links
diretos para o lote.

### Meus arremates

Lista de lotes vencidos com `lot_code`, título, valor final, `issued_at`,
`share_url` e link direto para o comprovante. Quando o backend não envia
`share_url`, o frontend cai para `/comprovantes/{token}`. A mesma página lista
os lotes em que o usuário deu lance a partir de `GET /api/me/bids`, mostrando
`lot_id`, `lot_code`, `lot_title`, valor e data.

### Auditoria

Página pública, sem login e sem PII, com indicador íntegro/adulterado, cabeça da
cadeia, contagem, primeira sequência inválida, status da âncora, falhas,
histórico completo com hashes, garantias e limitações explícitas.

### Comprovante

Página pública com aliases, lote, valor final, data, contagem, cabeça auditada,
verificação HMAC/head/âncora e link compartilhável copiável. Não exibe e-mail,
nome ou ID de usuário.

---

## 9. Testes

Arquivos:

```text
src/api/client.test.ts
src/api/decoders.test.ts
src/App.test.tsx
src/pages/Room/LotRoomPage.test.tsx
src/domain/lotState.test.ts
src/domain/bidErrors.test.ts
src/pages/Audit/AuditPage.test.tsx
src/hooks/useCountdown.test.ts
src/pages/Wallet/WalletPage.test.tsx
src/pages/Seller/SellerPage.test.tsx
src/pages/Wins/WinsPage.test.tsx
```

Cobertura dos fluxos críticos:

- refresh único em `401`, repetição da requisição, `credentials: include`,
  expiração de sessão e preservação de `{code, detail}`;
- vitrine carregando lotes da API, contagem, preço e troca para programados;
- lance com erro `BID_AMOUNT_MISMATCH`, mensagem em português e presença de
  `client_bid_id` UUID no request;
- reutilização do `client_bid_id` após falha de rede;
- `state_version`: evento novo antes de resposta HTTP antiga, descarte de versão
  menor/igual, salto de versão com snapshot e mesclagem de lance/encerramento;
- auditoria íntegra e adulterada, primeira sequência inválida, âncora e ausência
  de PII;
- mensagens próprias para os onze códigos de erro de lance do contrato;
- decoders do contrato real: `my_position.last_amount`, resumo do leiloeiro,
  arremates em lista, `limitations` textual da auditoria, snapshot achatado do
  WebSocket e notificação pessoal sem `lot_id`.

Testes unitários usam fetch e WebSocket mockados. O smoke E2E é o único teste
que depende do backend em execução (seção 13).

Resultados finais da segunda rodada:

```text
npm run lint
> eslint .
(sem erros ou avisos)

npm run build
vite v8.3.5 building client environment for production...
✓ 70 modules transformed.
dist/index.html                   0.58 kB │ gzip:   0.36 kB
dist/assets/index-BJbaPKiz.css   36.14 kB │ gzip:   7.57 kB
dist/assets/index-DXV70T48.js    367.27 kB │ gzip: 113.77 kB
✓ built in 2.19s

npm run test:run
Test Files  7 passed (7)
Tests       21 passed (21)
```

---

## 10. Limitações conhecidas

- A seção 13 registra o contrato observado na segunda rodada. As divergências
  ali listadas (`/api/seller/summary` sem resultado por lote, notificações sem
  `lot_id`, `/api/me/wins` sem `issued_at`/`share_url`) foram corrigidas no
  backend e absorvidas pelo frontend na seção 14.
- O cadastro público existe no backend e define a sessão em seguida via
  `POST /api/auth/token/`; o fallback de barra final permanece por
  compatibilidade. Senha padrão do seed: `demo-password-123`.
- O offset do countdown é recalculado a cada chegada de `serverTime` com o
  `Date.now()` do instante de recebimento; o tick local é separado e não
  reutiliza uma origem fixa de montagem. Na vitrine, quando a lista não traz
  `server_time`, a sincronização usa o detalhe do primeiro lote.
- O WebSocket usa `InMemoryChannelLayer` no backend demonstrativo. Em múltiplas
  instâncias, o polling de 4 segundos é o mecanismo de recuperação de estado, com
  atraso e perda possível de notificações efêmeras.
- A conexão é proativamente renovada em 14 minutos, antes do limite de 15
  minutos do backend, para reduzir fechamentos por idade.
- `share_url` do comprovante é usado quando fornecido; caso contrário, o link
  atual da página é compartilhado.
- Imagens remotas quebradas caem no placeholder; não há cache local de imagem no
  frontend.
- Rotas usam `BrowserRouter`; o host de produção precisa de fallback SPA para
  `index.html`.

---

## 11. Como executar

```sh
cd frontend
npm install
VITE_API_URL=http://localhost:8001 npm run dev
```

Backend esperado em `http://localhost:8001`, com CORS para a origem do Vite e
cookies adequados ao ambiente. Para demonstração:

```sh
cd backend
python manage.py migrate
python manage.py seed_demo
uvicorn core.asgi:application --reload --port 8001
```

Credenciais do seed:

```text
leiloeiro@demo.com / demo-password-123
cliente1@demo.com / demo-password-123
cliente2@demo.com / demo-password-123
```

Verificação de qualidade:

```sh
cd frontend
npm run lint
npm run build
npm run test:run
E2E_API_URL=http://127.0.0.1:8002 npm run test:e2e
```

---

## 12. Arquivos principais

Criados:

```text
src/api/client.ts, json.ts, decoders.ts, auth.ts, lots.ts, wallet.ts, catalog.ts
src/components/RequireAuth.tsx
src/components/catalog/CatalogLotCard.tsx
src/components/layout/{SiteLayout,SiteHeader,SiteFooter,NotificationBell}.tsx
src/components/ui/{LotImage,StatusBadge,PaginationControls,States}.tsx
src/context/{auth-context,AuthProvider,toast-context,ToastProvider,
             notifications-context,NotificationsProvider}
src/domain/{lotState,bidErrors}.ts + testes
src/hooks/{useCountdown,useLotRoom}.ts
src/pages/{Catalog,Room,Wallet,Seller,Wins,Audit,Receipt,Auth}/
src/pages/NotFoundPage.tsx
src/styles/app.css
src/test/{apiMock,fixtures}.ts
src/types/api.ts
src/utils/{errors,id}.ts
scripts/e2e-smoke.mjs
```

Alterados:

```text
src/App.tsx                 rotas e providers
src/App.test.tsx            teste da vitrine integrada
src/components/Announcement.tsx
src/components/Icon.tsx
src/components/Toast.tsx
src/test/setup.ts           limpeza de mocks e scrollTo
src/utils/format.ts         valores decimais da API, datas e status
tsconfig.app.json           strict: true
README.md                   instruções e arquitetura atuais
../docs/fases/fase-7.md     status e registro do frontend
```

O catálogo demonstrativo antigo (`src/services/lots.json`, `useAuction`,
`BidModal`, `LotCard`, `Header`, `Modal`, `Home` e tipos/hooks exclusivos) foi
removido na etapa final após confirmação de que nenhuma rota, teste ou
componente atual o referenciava (seção 14).

---

## 13. Integração E2E real (segunda rodada)

**Data:** 2026-10-27  
**Backend alvo:** `http://127.0.0.1:8002` (ASGI já em execução, banco migrado e
`seed_demo --reset` aplicado)  
**Escopo alterado:** somente `frontend/**` e este documento.

### 13.1 Inspeção do contrato real

Foram lidos no backend, em modo somente leitura, `core/urls.py`,
`auctions/urls.py`, `users/urls.py`, `wallet/urls.py`, serializers, views,
selectors, `auctions/consumers.py`, `auctions/events.py`, `auctions/ws_auth.py`,
serviços de lance/liquidação/auditoria, `seed_demo` e o README raiz.

Rotas reais confirmadas (sem barra final, exceto autenticação):

- autenticação: `POST /api/auth/token/`, `POST /api/auth/refresh/`,
  `POST /api/auth/logout/`, `GET /api/auth/me/`,
  `POST /api/auth/register`, `POST /api/auth/ws-ticket`;
- carteira: `GET /api/wallet`, `POST /api/wallet/deposits`,
  `GET /api/wallet/transactions`;
- lotes: `GET|POST /api/lots`, `GET /api/lots/{id}`,
  `GET|POST /api/lots/{id}/bids`, `GET /api/lots/{id}/audit`,
  `POST /api/lots/{id}/cancel`;
- leiloeiro/licitante: `GET /api/seller/lots`, `GET /api/seller/summary`,
  `GET /api/me/bids`, `GET /api/me/wins`;
- comprovantes: `GET /api/receipts/{token}`,
  `GET /api/receipts/{token}/verify`;
- catálogo: `GET /api/catalog/search`, `GET /api/catalog/items/{id}`;
- WebSocket: `/ws/lots/{id}/` e `/ws/notifications/`, ticket por query string.

### 13.2 Reconciliações aplicadas no frontend

| Contrato real | Ajuste no frontend |
|---|---|
| `my_position = {is_leading, status, last_amount, rank}` | tipo e decoder passaram de `last_bid_amount`/`last_bid_at` para `last_amount`; sala usa o novo campo |
| resumo do leiloeiro = `{total_received, settled_count, unsold_count, blocked_lots}` | decoder e painel exibem os contadores reais e a tabela de bloqueios |
| `/api/seller/lots` usa `LotListSerializer` | `SellerLot` alinhado; removidos `final_price`/`settlement_error` inexistentes; valor exibido é `current_bid ?? starting_bid` |
| `/api/me/wins` é lista simples | decoder aceita lista; painel usa `lot_code`, `title`, `final_price`, `settled_at`, `receipt_token` |
| auditoria envia `limitations` como string e não envia `guarantees` | `stringList` normaliza string única; UI mantém fallback local de garantias |
| snapshot WS é achatado (`event`, `lot_id`, campos no root) | novo `LotSnapshot` + `mergeLotSnapshot`, sem tentar decodificar um `LotDetail` completo |
| eventos WS são achatados e `bid.accepted` não traz `minimum_bid`/`current_bid` | decoder lê `amount` e o merge calcula o próximo mínimo com `min_increment` |
| notificações `user.outbid`/`user.sold` não trazem `lot_id` | notificação não inventa link; usa `lot_code` na mensagem |
| `POST /api/lots/{id}/bids` devolve somente o `Bid` aceito | cliente confirma e refaz `GET /api/lots/{id}` para posição e `state_version` |
| paginação `{count,next,previous,results}` com `PAGE_SIZE=20` | painel do leiloeiro passou a enviar `page`; lista simples de arremates continua aceita |
| papéis reais `SELLER`/`BIDDER` | removido `ADMIN` do tipo, header, rotas e checagens |
| erros `{code, detail}` e validação DRF por campo | `ApiError` preserva código/status/detalhe e campos; `BidErrorCode` cobre os 11 códigos reais |

### 13.3 Smoke E2E

Arquivo: `frontend/scripts/e2e-smoke.mjs`  
Script npm: `test:e2e`  
Dependências novas: nenhuma (Node 24, `fetch` e `WebSocket` globais).

Execução:

```sh
cd frontend
E2E_API_URL=http://127.0.0.1:8002 npm run test:e2e
```

O smoke usa apenas APIs públicas e os serviços do backend, sem acesso direto ao
banco. Ele cobre:

1. `GET /health/`, login por cookie de leiloeiro, cliente1 e cliente2,
   `GET /api/auth/me/` dos três;
2. vitrine paginada, detalhe, carteira e extrato de cliente1;
3. depósito simulado com `idempotency_key`, incluindo replay sem novo crédito;
4. busca de item em cache no catálogo do leiloeiro e criação de lote com datas
   válidas, lance inicial e incremento;
5. primeiro lance exato de cliente1 com `client_bid_id` e
   `my_position.status = leading`;
6. cobertura exata de cliente2, `my_position.status = outbid` para cliente1 e
   reserva de cliente1 liberada;
7. replay do mesmo `client_bid_id` sem lance, hold ou lançamento duplicado;
8. valor incorreto (`BID_AMOUNT_MISMATCH`, HTTP 422) sem criar lance;
9. saldo insuficiente (`INSUFFICIENT_FUNDS`, HTTP 409) em lote de valor alto,
   seguido de cancelamento pelo leiloeiro;
10. anti-sniping: lote com `ends_at` em 45 s, lance estende para
    `now + 2 min`, `extension_count` e nova cobertura de cliente2;
11. `GET /api/lots/{id}/bids` anônimo sem PII (`is_mine` ausente);
12. `/api/seller/lots` e `/api/seller/summary`;
13. `POST /api/auth/ws-ticket` + WebSocket da sala com `Origin` permitida,
    recebendo `lot.snapshot` achatado com `my_position`;
14. espera da liquidação pelo ticker (5 s) e `settle_if_due` das leituras;
15. `/api/me/wins` de cliente2, comprovante público, `/verify` e auditoria;
16. resumo do leiloeiro e status `ended` após a liquidação.

O `Origin` do WebSocket precisa estar em `WS_ALLOWED_ORIGINS` (ou herdar
`CORS_ALLOWED_ORIGINS`). O script usa `http://localhost:5173` por padrão e aceita
`E2E_WS_ORIGIN` para outro valor. Sem esse header o `OriginValidator` rejeita o
handshake; o script falha explicitamente, sem simular snapshot.

Resultado observado:

```text
E2E API: http://127.0.0.1:8002
E2E WS origin: http://localhost:5173
- health do backend ... ok
- login do leiloeiro ... ok
- login de cliente1 ... ok
- login de cliente2 ... ok
- GET /api/auth/me/ do leiloeiro ... ok
- GET /api/auth/me/ de cliente1 ... ok
- GET /api/auth/me/ de cliente2 ... ok
- GET /api/lots paginado ... ok
- GET /api/lots/{id} com posição pessoal ... ok
- GET /api/wallet e extrato de cliente1 ... ok
- depósito simulado idempotente em cliente1 ... ok
- busca de item no catálogo do leiloeiro ... ok
- criação de lote pelo leiloeiro ... ok
- cliente1 envia o primeiro lance exato ... ok
- cliente2 cobre com o próximo valor exato ... ok
- repetição idempotente do mesmo client_bid_id ... ok
- erro de valor incorreto sem criar lance ... ok
- criação de lote para saldo insuficiente ... ok
- saldo insuficiente retorna INSUFFICIENT_FUNDS ... ok
- criação de lote com encerramento em menos de 2 minutos ... ok
- anti-sniping estende o lote para now+2min ... ok
- cliente2 cobre o lote anti-sniping ... ok
- GET /api/lots/{id}/bids sem PII ... ok
- GET /api/seller/lots e /api/seller/summary ... ok
- WebSocket da sala entrega snapshot ... ok
- aguardando liquidação do lote L-81068C7D81 (~125s) ...
- liquidação e GET /api/me/wins de cliente2 ... ok
- GET /api/receipts/{token} público ... ok
- GET /api/receipts/{token}/verify público ... ok
- GET /api/lots/{id}/audit público ... ok
- resumo do leiloeiro reflete a liquidação ... ok

E2E concluído: 30/30 etapas ok.
Lote principal: ac3f3da3-f553-4d52-bb6a-eecc99acf260 (L-30198885B4)
Lote liquidado: c662ef58-c39f-4c58-8d29-e6ebafffbf83 (L-81068C7D81) com recibo a9239bdb-2a11-4ae0-9e4c-123e4d7ec74c
```

### 13.4 Divergências e limitações do backend

> Registro histórico da segunda rodada. As divergências de contrato abaixo foram
> corrigidas no backend e absorvidas na seção 14.

Nenhum defeito de contrato impediu o fluxo. Foram encontrados contratos mais
enxutos que os documentos usados na primeira rodada; todos foram absorvidos no
frontend, sem alterar `backend/**`:

- `/api/seller/summary` não entrega resultado por lote, vencedor, data ou token
  de comprovante; entrega apenas `total_received`, `settled_count`,
  `unsold_count` e `blocked_lots[{code, settlement_error}]`.
- `/api/seller/lots` usa `LotListSerializer` e não inclui `final_price`,
  `settled_at` nem `settlement_error`.
- `/api/me/wins` é lista simples, não paginada, e não inclui `lot_id`, imagem,
  `issued_at` nem link do comprovante; só `lot_code`, `title`, `final_price`,
  `settled_at` e `receipt_token`.
- notificações `user.outbid`, `user.won` e `user.sold` não incluem `lot_id`;
  `user.outbid`/`user.sold` também não incluem valor. Notificações de outbid não
  podem abrir o lote diretamente com o contrato atual.
- auditoria devolve `limitations` como uma string e não devolve `guarantees`; a
  página usa textos locais para garantias e normaliza limitações.
- `POST /api/lots/{id}/bids` devolve apenas o `Bid` criado, sem posição,
  `state_version` ou lote; o frontend sempre refaz o snapshot HTTP após aceite.
- Não há endpoint HTTP de liquidação manual; o fluxo suportado é ticker ASGI
  (5 s) e `settle_if_due` nas leituras de detalhe/auditoria/painel. O smoke
  aguarda o encerramento real (aproximadamente 2 min após o último lance por
  causa do anti-sniping).
- O smoke deixa artefatos de demonstração por execução: um lote ao vivo com
  lances, um lote cancelado de saldo insuficiente e um lote liquidado com
  comprovante. Não há limpeza automática porque o escopo proíbe escrita direta
  no banco; uma nova execução cria novos lotes.
- O WebSocket demonstrativo usa `InMemoryChannelLayer`; com mais de um worker a
  notificação pode se perder e o polling de 4 s recupera o estado do lote.
- A lista de arremates não permite “Ver lote” por falta de `lot_id`; o link
  disponível é o comprovante público.
- O painel do leiloeiro não mostra resultado/recibo por lote por falta desses
  campos nos endpoints de leiloeiro; mostra contadores e bloqueios reais.
- O comprovante não traz `share_url`; a página compartilha a URL atual.
- O anti-sniping exige espera real de até dois minutos no E2E; não foi usado
  relógio falso nem manipulação de banco.

---

## 14. Ajustes finais

**Data:** 2026-10-27  
**Escopo alterado:** `frontend/**`, `docs/implemented/fase-7-frontend.md` e
`docs/fases/fase-7.md`. Nenhum arquivo de `backend/**` foi editado e nenhum
commit foi criado.

### 14.1 Ajustes de frontend

| Área | Correção aplicada | Evidência |
|---|---|---|
| Login de demonstração | Confirmado que o frontend já usava `demo-password-123` em `LoginPage.tsx`, `frontend/README.md` e `e2e-smoke.mjs`; não há valores divergentes de senha no código. O E2E não tem fallback de cadastro e agora testa explicitamente que senha incorreta recebe `401` sem criar sessão. | `grep` de senhas divergentes sem ocorrências; `LoginPage.tsx:41,61`; `scripts/e2e-smoke.mjs` |
| Cronômetro | `useCountdown` deixou de congelar `clockOrigin` no mount. O offset é recalculado quando `serverTime` muda, usando `Date.now()` do instante de chegada; o tick local permanece em estado separado. | `src/hooks/useCountdown.ts`; `src/hooks/useCountdown.test.ts` |
| Carteira do leiloeiro | `/carteira` carrega carteira e extrato em efeitos independentes; `403` isolado no extrato do `SELLER` não derruba mais a página. O leiloeiro vê saldo, orientação e, quando o backend libera, os créditos de liquidação. O formulário de depósito fica restrito a `BIDDER`. | `src/pages/Wallet/WalletPage.tsx`; `src/pages/Wallet/WalletPage.test.tsx` |
| Resultados por lote | Tipos, decoder e painel passaram a consumir `results_by_lot`, `unsold_lots` e `blocked_lots`, com lote, item, valor final, vencedor, data e links diretos. | `src/types/api.ts`; `src/api/decoders.ts`; `src/pages/Seller/SellerPage.tsx`; `SellerPage.test.tsx` |
| Participações | `/api/me/bids` é consumido em `/meus-arremates`, com `lot_id`, `lot_code` e `lot_title`; o decoder aceita lista simples ou paginada. | `src/api/lots.ts`; `src/api/decoders.ts`; `src/pages/Wins/WinsPage.tsx`; `WinsPage.test.tsx` |
| Links nas notificações | Notificações `user.outbid`, `user.won` e `user.sold` usam `lot_id` para link direto ao lote; `won` mantém o comprovante como link principal e o lote como secundário. O fallback por `lot_code` continua quando `lot_id` não vem. | `src/api/decoders.ts`; `NotificationBell.tsx`; `decoders.test.ts` |
| Feedback de saldo | `ApiError` preserva o corpo contextual; em `INSUFFICIENT_FUNDS` a sala exibe `available` e `minimum_bid` retornados pela API além da mensagem. | `src/api/client.ts`; `src/hooks/useLotRoom.ts`; `src/pages/Room/LotRoomPage.tsx`; `LotRoomPage.test.tsx` |
| Compartilhamento de comprovante | Comprovante e meus arremates usam `share_url` e `issued_at`; quando `share_url` falta, o link local `/comprovantes/{token}` é o fallback. | `src/types/api.ts`; `src/api/decoders.ts`; `src/pages/Wins/WinsPage.tsx`; `ReceiptPage.tsx` |
| Tipos e código legado | `apiMock.ts` passou de `object` para `JsonValue`. O código legado da vitrine estática foi removido após confirmação de que nada em `src/` o referenciava: `Home.tsx`, `BidModal.tsx`, `LotCard.tsx`, `Header.tsx`, `Modal.tsx`, `auctionService.ts`, `lots.json`, `useAuction`, `useElapsedTime`, `useToast`, `types/auction.ts`, `types/ui.ts` e `utils/catalog.ts`. | `src/test/apiMock.ts`; árvore `src/` sem referências aos módulos removidos |

O `Announcement` compartilhado pelo `SiteLayout` foi preservado (o texto atual é
o da versão integrada). `Home.css` permanece porque é importado diretamente por
`App.tsx` e contém estilos globais usados pelas rotas atuais.

### 14.2 Testes adicionados/atualizados

- `src/hooks/useCountdown.test.ts`: com fake timers, avança 30 s e envia um novo
  `serverTime` equivalente; prova que o contador vai de 600 s para 570 s sem
  salto regressivo e continua coerente após novas sincronizações.
- `src/pages/Wallet/WalletPage.test.tsx`: `SELLER` com extrato `200` exibe
  crédito de liquidação; falha isolada `403` mantém saldo, orientação e não
  mostra erro genérico; formulário de depósito não aparece para leiloeiro.
- `src/pages/Seller/SellerPage.test.tsx`: resultado por lote, lote sem arremate
  e bloqueio aparecem com vínculo ao lote.
- `src/pages/Wins/WinsPage.test.tsx`: `share_url` vira link do comprovante,
  `issued_at` é exibido e `/api/me/bids` lista o lote com `lot_id`.
- `src/pages/Room/LotRoomPage.test.tsx`: erro `INSUFFICIENT_FUNDS` exibe
  `available` e `minimum_bid`.
- `src/api/decoders.test.ts`: resumo com `results_by_lot`/`unsold_lots`,
  notificação com e sem `lot_id`, arremate com `issued_at`/`share_url` e lance
  com `lot_code`/`lot_title`.

### 14.3 Validação executada

```text
npm run lint
> eslint .
(sem erros ou avisos)

npm run build
vite v8.3.5 building client environment for production...
✓ 70 modules transformed.
dist/index.html                   0.58 kB │ gzip:   0.36 kB
dist/assets/index-BJbaPKiz.css   36.14 kB │ gzip:   7.57 kB
dist/assets/index-wOu_wqWA.js    375.63 kB │ gzip: 115.43 kB
✓ built in 9.27s

npm run test:run
Test Files  11 passed (11)
Tests       30 passed (30)
```

### 14.4 E2E e bloqueio de backend

`scripts/e2e-smoke.mjs` foi ajustado para cobrir:

- login demo real, com senha incorreta rejeitada sem fallback de cadastro;
- `GET /api/wallet/transactions` do leiloeiro com `200` e paginação;
- `POST /api/wallet` do leiloeiro com `405`;
- duas leituras de `GET /api/lots/{id}` com `server_time` atualizado, validando
  que o restante derivado de `ends_at - server_time` não salta;
- `GET /api/me/bids` com `lot_id`, `lot_code` e `lot_title`;
- `user.outbid` recebido por WebSocket contendo `lot_id`;
- `INSUFFICIENT_FUNDS` com `available` e `minimum_bid`;
- `/api/me/wins` com `issued_at` e `share_url`;
- `results_by_lot`, `unsold_lots` e `blocked_lots` em `/api/seller/summary`;
- replay idempotente de lance/depósito com `200` e header
  `Idempotent-Replayed: true`.

O E2E **não foi executado nesta rodada** porque o processo ASGI em
`http://127.0.0.1:8002` ainda servia a versão anterior do backend, apesar de o
código-fonte já conter as correções. Evidência coletada em 2026-10-27:

```text
GET /api/seller/summary
200 {"total_received":"1055.00","settled_count":4,"unsold_count":0,"blocked_lots":[]}

GET /api/wallet/transactions?page=1 (SELLER)
403 {"detail":"Apenas licitantes podem usar esta operação."}

POST /api/wallet (SELLER)
201 {"balance":"...","committed":"0.00","available":"...", ...}
```

Como as restrições da rodada proíbem encerrar ou reiniciar processos, o E2E
final fica pendente de um restart do servidor em `8002`. O comando previsto é:

```sh
cd frontend
E2E_API_URL=http://127.0.0.1:8002 npm run test:e2e
```

### 14.5 Resultado

Os ajustes de frontend estão cobertos por testes automatizados,
lint/build/test verdes e documentação atualizada. O único item pendente é a
execução do smoke E2E contra o backend reiniciado, bloqueada pelo processo
`8002` desatualizado.
