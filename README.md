# Auction System

Plataforma de leilões com API Django/DRF, autenticação por cookies HttpOnly,
carteiras com saldo comprometido, lances concorrentes, liquidação, recibos,
auditoria pública e atualizações WebSocket. O frontend React consome a API e
mantém polling HTTP como recuperação do estado.

## Arquitetura

- `backend/core`: settings, HTTP/ASGI, WebSocket, health checks e ticker de
  liquidação.
- `backend/users`: usuário UUID com papel `SELLER`/`BIDDER`, cadastro e JWT.
- `backend/wallet`: carteira Decimal e livro-razão append-only.
- `backend/auctions`: catálogo AIC, lotes, lances encadeados, liquidação,
  comprovantes, auditoria, âncora e consumers.
- `frontend`: SPA React/TypeScript integrada à API, com WebSocket e polling.
- `docs/fases`: critérios de aceite; `docs/implemented`: registros de entrega.

Dependência de domínio: `users` não depende das outras apps; `wallet` depende
de `users`; `auctions` chama serviços de `wallet`; `core` conecta os serviços.

## Requisitos e setup local

- Python 3.14+, `uv` e PostgreSQL 18+.
- Node.js/npm para o frontend.
- Docker Compose é opcional para executar PostgreSQL e backend.

```sh
cd backend
cp .env.example .env
# Edite credenciais, SECRET_KEY e segredos HMAC independentes.
uv sync
uv run python manage.py migrate
uv run python manage.py seed_demo
uv run python manage.py collectstatic --noinput
uv run uvicorn core.asgi:application --reload --port 8001
```

A API fica em `http://localhost:8001`; o frontend de desenvolvimento usa
`http://localhost:5173`. PostgreSQL é obrigatório para produção e para validar
concorrência e locks. O SQLite pode ser usado apenas para desenvolvimento sem
testes de concorrência. Em ambiente `DEBUG=False`, SQLite é recusado.

## Docker Compose

O compose do backend está em `backend/docker-compose.yaml`:

```sh
cd backend
cp .env.example .env
# Configure POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB e segredos.
docker compose -f docker-compose.yaml up --build
```

O banco tem health check `pg_isready`; o backend executa migrations pelo
`scripts/entrypoint.sh` e expõe `/health/` para o health check do container.
O backend escuta na porta 7860 dentro do container e é publicado em 8001 no
host. O servidor ASGI precisa manter upgrade WebSocket habilitado.

## Variáveis de ambiente

Veja [`backend/.env.example`](backend/.env.example). As principais variáveis:

| Variável | Uso |
|---|---|
| `SECRET_KEY` | assinatura interna Django e tickets WS |
| `DEBUG`, `ALLOWED_HOSTS` | modo e hosts Django |
| `DATABASE_URL` ou `POSTGRES_URL` | conexão PostgreSQL; `DATABASE_URL` tem prioridade |
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` | Compose |
| `CORS_ALLOWED_ORIGINS` | origens HTTP do frontend |
| `WS_ALLOWED_ORIGINS` | allowlist do handshake WebSocket; fallback para CORS |
| `AUTH_COOKIE_SECURE`, `AUTH_COOKIE_SAMESITE`, `AUTH_COOKIE_DOMAIN` | cookies JWT |
| `BID_HISTORY_SECRET`, `RECEIPT_SECRET` | HMAC da cadeia e dos recibos; distintos e estáveis |
| `BID_ANCHOR_PATH` | arquivo JSONL append-only de checkpoint externo |
| `ENABLE_SETTLEMENT_TICKER` | liga/desliga ticker no lifespan ASGI |
| `SETTLEMENT_INTERVAL_SECONDS`, `SETTLEMENT_BATCH_SIZE` | frequência e limite por ciclo |
| `WS_TICKET_MAX_AGE_SECONDS`, `WS_CONNECTION_MAX_AGE_SECONDS` | validade do ticket e conexão |
| `CATALOG_*` | timeout/retry/cache do provedor Art Institute of Chicago |
| `FRONTEND_URL` | links compartilháveis de recibo |

Em produção, configure valores aleatórios fortes para `SECRET_KEY` e para cada
segredo HMAC; o app recusa segredos HMAC iguais entre si ou ao `SECRET_KEY`.
Use HTTPS, `AUTH_COOKIE_SECURE=True`, origens exatas, volume persistente para a
âncora e storage de mídia persistente. O arquivo de âncora ausente ou atrasado
é informado como limitação e não como adulteração.

## Migrations e dados de demonstração

```sh
cd backend
uv run python manage.py migrate
uv run python manage.py makemigrations --check --dry-run
uv run python manage.py seed_demo
uv run python manage.py seed_demo --new-live
uv run python manage.py seed_demo --reset
```

O seed usa os serviços de domínio para gerar reservas, cadeia, lances e
comprovante sem chamadas externas. Cria um leiloeiro, dois licitantes, depósitos,
um lote ao vivo com pelo menos dois lances, um agendado e um encerrado com
recibo. `--new-live` adiciona outro lote sem alterar os históricos; `--reset`
remove lotes/lançamentos dos usuários de demonstração e reconstrói os dados.

Credenciais locais padrão (altere `DEMO_PASSWORD` antes de disponibilizar uma
instância):

| Papel | Email | Senha padrão |
|---|---|---|
| Leiloeiro | `leiloeiro@demo.com` | `demo-password-123` |
| Licitante | `cliente1@demo.com` | `demo-password-123` |
| Licitante | `cliente2@demo.com` | `demo-password-123` |

## Autenticação e cookies

- `POST /api/auth/register`: cadastro com email, senha, papel e alias opcional.
- `POST /api/auth/token/`: login; cookies `access_token` e `refresh_token`
  HttpOnly.
- `POST /api/auth/refresh/`: renova access e rotaciona refresh.
- `POST /api/auth/logout/`: blacklista refresh e limpa cookies.
- `GET /api/auth/me/`: dados privados da conta autenticada.
- `POST /api/auth/ws-ticket`: emite ticket assinado, curto e de uso WS; JWT não
  é colocado na URL.

Access dura 15 minutos, refresh 7 dias, com rotação e blacklist do SimpleJWT.
Para origens diferentes em produção, configure `SameSite=None`, `Secure=True`
e proteção CSRF nos endpoints de escrita; mantenha CORS limitado às origens do
frontend. O header Bearer é aceito como fallback para clientes de API.

## Endpoints

Todos os valores monetários são `Decimal(12,2)` no banco e strings decimais na
API. Respostas públicas usam aliases e nunca incluem email, nome ou UUID de
usuário.

| Método e rota | Acesso | Descrição |
|---|---|---|
| `GET /api/lots` | público | vitrine paginada, filtros e ordenação |
| `GET /api/lots/{id}` | público/autenticado | detalhe, versão e posição pessoal |
| `POST /api/lots` | leiloeiro | cria lote de item do catálogo |
| `POST /api/lots/{id}/cancel` | leiloeiro dono | cancela lote sem lances |
| `POST /api/lots/{id}/bids` | licitante | tenta um lance idempotente |
| `GET /api/lots/{id}/bids` | público | histórico paginado; `is_mine` só autenticado |
| `GET /api/me/bids` | licitante | lances próprios |
| `GET /api/wallet` | autenticado | saldo, comprometido e disponível |
| `POST /api/wallet/deposits` | licitante | depósito simulado idempotente |
| `GET /api/wallet/transactions` | licitante | livro-razão privado |
| `GET /api/seller/lots` | leiloeiro | próprios lotes e liquidação sob demanda |
| `GET /api/seller/summary` | leiloeiro | total recebido, lotes sem venda e bloqueios |
| `GET /api/me/wins` | licitante | arremates e tokens de recibo |
| `GET /api/receipts/{token}` | público | comprovante imutável sem PII |
| `GET /api/lots/{id}/audit` | público | cadeia, falhas e estado da âncora |
| `GET /api/receipts/{token}/verify` | público | HMAC do recibo e vínculo à cadeia |
| `GET /health/` | público/ops | disponibilidade HTTP |
| `GET /health/settlement/` | público/ops | estado local do ticker |

Catálogo para leiloeiros: `GET /api/catalog/search?q=` e
`GET /api/catalog/items/{id}`. WebSockets: `/ws/lots/{id}/` (público, com
posição pessoal quando o ticket é válido) e `/ws/notifications/` (ticket
obrigatório). O frontend usa polling HTTP como fallback.

## Regras financeiras e de lance

O lote precisa estar ao vivo; apenas `BIDDER` pode participar, nunca o
leiloeiro ou o líder atual. O valor aceito é exatamente o lance inicial ou o
lance atual mais o incremento. `Lot` é bloqueado primeiro; carteiras do
licitante e do líder são bloqueadas por chave primária. O horário é capturado
depois dos locks. O hold aumenta `committed`; quando há novo líder, o hold
anterior é liberado na mesma transação. A liquidação valida cadeia, estado e
reserva antes de debitar vencedor e creditar leiloeiro.

Idempotência por `(lot, bidder, client_bid_id)` retorna o lance original sem
efeitos extras; chave com valor diferente retorna `IDEMPOTENCY_KEY_REUSED`.
Erros de regra incluem `LOT_NOT_STARTED`, `LOT_ENDED`, `LOT_CANCELLED`,
`LOT_SETTLED`, `BID_AMOUNT_MISMATCH`, `BID_BELOW_MINIMUM`, `ALREADY_LEADING`,
`INSUFFICIENT_FUNDS`, `SELLER_CANNOT_BID` e `FORBIDDEN_ROLE`.

Anti-sniping: lance feito estritamente dentro dos últimos 2 minutos define
`ends_at = max(ends_at, now + 2 minutos)`; no limite exato de 2 minutos não há
extensão. Cada mutação relevante incrementa `state_version`.

## Liquidação e recibos

O ticker ASGI inicia no lifespan, processa um lote limitado na inicialização e
em intervalos, trata lotes em transações separadas e cancela limpo no shutdown.
`settle_if_due` atende leituras de detalhe, auditoria e painéis. A liquidação
também pode ser executada por `uv run python manage.py close_due_lots --once`.
`ENABLE_SETTLEMENT_TICKER=False` desliga o loop. Se o servidor estiver suspenso,
a liquidação aguarda retorno do processo ou acesso ao lote.

Lote sem lances encerra sem recibo; lote cancelado não liquida. Inconsistências
preenchem `settlement_error`/`settlement_checked_at`, bloqueiam repetição
automática e não movimentam dinheiro. Comprovantes mantêm snapshots e HMAC,
sem identificação privada.

## Auditoria e garantias

O payload de cada lance é JSON canônico com chaves ordenadas, separadores fixos,
valores monetários com duas casas e timestamps UTC com microssegundos. A cadeia
usa `content_hash = SHA-256(payload)` e
`hash = HMAC-SHA256(BID_HISTORY_SECRET, prev_hash + ':' + content_hash)`. O
backend confere sequência, elo anterior, payload, HMAC, contagem, head e âncora.
Após commit, um checkpoint JSONL pode ser acrescentado em `BID_ANCHOR_PATH`.

O endpoint entrega a verificação feita pelo backend; HMAC não permite
verificação independente pelo visitante. Âncora local protege contra alteração
limitada ao banco, não contra controle do servidor. Sem âncora, ou quando ela
está atrasada, a resposta informa `unavailable`/`behind` sem classificar como
adulteração. Um checkpoint externo confiável, object lock ou log independente é
necessário para uma garantia forte contra rollback completo.

## Deploy e limitações operacionais

O deploy demonstrativo usa uma instância e um processo ASGI, PostgreSQL,
`InMemoryChannelLayer`, ticker e storage persistente configurado pelo operador.
A camada Channels em memória não compartilha eventos entre workers; use uma
instância/processo ou adicione Redis com `channels-redis`. O polling recupera o
estado do lote, mas notificações transitórias podem se perder. Configure proxy
com suporte a WebSocket, HTTPS e disco persistente para uploads/âncoras.

## Testes e qualidade

Execute de `backend/`:

```sh
uv run ruff check .
uv run ruff format --check .
uv run mypy .
uv run python manage.py check
uv run python manage.py makemigrations --check --dry-run
uv run python manage.py migrate
uv run pytest
```

Testes de concorrência usam PostgreSQL com conexões reais e verificam locks e
liquidação idempotente. Os testes cobrem regras/limites anti-sniping, hold e
release, adulteração da cadeia, recibo, âncora, ticket/origem, broadcast após
commit e supressão após rollback.

## Uso de IA

Ferramentas de IA foram usadas como apoio de implementação, revisão e geração de
testes e documentação. Decisões de domínio, integração, validação e execução dos
comandos de qualidade foram conferidas no repositório; limitações operacionais
e de auditoria estão registradas acima.
