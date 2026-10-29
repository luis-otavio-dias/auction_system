# Backend — Auction System

API em Django 6.1 e Django REST Framework para a plataforma de leilões. O
backend concentra autenticação por cookies JWT, carteiras com saldo
comprometido, lances concorrentes, liquidação, comprovantes, auditoria pública
e WebSocket.

- **API publicada:** https://api--auction-system-backend--cg7yjzmmcfrl.code.run/api
- **Health check:** https://api--auction-system-backend--cg7yjzmmcfrl.code.run/health/
- **Documentação completa:** [`../README.md`](../README.md)

## Stack

| Camada | Tecnologia |
|---|---|
| Linguagem | Python 3.14 |
| Framework | Django 6.1 + Django REST Framework 3.18 |
| Autenticação | SimpleJWT em cookies HttpOnly + Bearer fallback |
| Tempo real | Django Channels + `InMemoryChannelLayer` |
| Banco | PostgreSQL 18 (SQLite apenas em desenvolvimento sem concorrência) |
| Servidor | Uvicorn/ASGI |
| Testes | pytest + pytest-django |
| Qualidade | Ruff, mypy e Django checks |

## O que está pronto

| Requisito | Onde |
| --- | --- |
| Autenticação e dois papéis | `users/` — cadastro, cookies JWT e permissões |
| Integração com API pública | `auctions/services/catalog.py` — AIC, cache e fallback |
| Lances concorrentes e idempotentes | `auctions/services/bidding.py` — transações e locks |
| Carteira e saldo comprometido | `wallet/` — depósitos, holds, liberações e extrato |
| Anti-sniping e liquidação | `auctions/services/` e ticker ASGI |
| Comprovante compartilhável | `Receipt` e rotas públicas `/api/receipts/{token}` |
| Histórico verificável sem dados pessoais | Cadeia HMAC, aliases e auditoria pública |
| Atualizações ao vivo | Channels, tickets assinados e eventos após commit |
| Dados de demonstração | `python manage.py seed_demo` |

## Subir com Docker (recomendado)

Requisito: Docker com Compose. Os comandos abaixo partem da raiz do repositório.

1. Crie o arquivo de configuração:

   ```sh
   cd backend
   cp .env.example .env
   ```

2. Gere três segredos independentes com Python instalado na máquina:

   ```sh
   python3 - <<'PYTHON'
   import secrets
   for key in ("SECRET_KEY", "BID_HISTORY_SECRET", "RECEIPT_SECRET"):
       print(f"{key}={secrets.token_hex(32)}")
   PYTHON
   ```

   Cole os valores no `.env` e escolha uma `POSTGRES_PASSWORD`. Para acesso local
   por HTTP, mantenha `AUTH_COOKIE_SECURE=False` e `AUTH_COOKIE_SAMESITE=Lax`.
   O Compose monta `DATABASE_URL` com as variáveis `POSTGRES_*` e o host `db`.

3. Suba os serviços e aplique o seed:

   ```sh
   docker compose up -d --build
   docker compose exec auction-system-backend python manage.py seed_demo
   curl http://localhost:8001/health/
   ```

   O health check responde `{"status":"ok"}` e indica disponibilidade HTTP;
   ele não testa a conexão com o banco. O contêiner executa `collectstatic` e
   `migrate` antes do Uvicorn. **O seed é manual**, não faz parte da inicialização.

| Serviço | Endereço |
| --- | --- |
| API | `http://localhost:8001/api` |
| Health HTTP | `http://localhost:8001/health/` |
| Estado local do ticker | `http://localhost:8001/health/settlement/` |
| PostgreSQL | `localhost:5432` |

O backend escuta em `7860` dentro do contêiner, publicado em `8001` no host.
Para acompanhar a inicialização:

```sh
docker compose logs -f auction-system-backend
```

`docker compose down` preserva o volume do PostgreSQL. Acrescentar `-v` apaga o
banco. As credenciais `POSTGRES_*` inicializam o banco apenas quando o volume
está vazio; mudar o `.env` não altera um usuário já criado no PostgreSQL.

## Executar sem Docker

Requisitos: Python 3.14+, [uv](https://docs.astral.sh/uv/) e PostgreSQL
(o Compose e a CI usam a versão 18).

A partir de `backend/`, copie `.env.example` para `.env`, gere os segredos como
acima e ajuste `DATABASE_URL` para um banco e usuário existentes:

```env
DATABASE_URL=postgresql://usuario:senha@localhost:5432/auction_system_db
```

Instale dependências e inicie:

```sh
uv sync --frozen
uv run python manage.py migrate
uv run python manage.py seed_demo
uv run python manage.py collectstatic --noinput
uv run uvicorn core.asgi:application --reload --port 8001
```

Se usar apenas o serviço `db` do Compose e mantiver as credenciais do template,
o `DATABASE_URL` local deve usar `localhost`, enquanto o contêiner da API usa
`db`. O frontend roda separadamente; veja o [guia](../frontend/README.md).

Com `DEBUG=False`, o backend exige PostgreSQL, `SECRET_KEY` com pelo menos 50
caracteres e segredos HMAC distintos entre si e diferentes de `SECRET_KEY`.
SQLite só é aceito em modo de desenvolvimento e não valida os locks usados nos
testes de concorrência.

## Dados de demonstração

| Papel | E-mail | Senha padrão |
| --- | --- | --- |
| Leiloeiro | `leiloeiro@demo.com` | `demo-password-123` |
| Licitante | `cliente1@demo.com` | `demo-password-123` |
| Licitante | `cliente2@demo.com` | `demo-password-123` |

O seed é idempotente e usa fixtures locais, sem depender da AIC. Cria um lote
ao vivo com lances, um agendado e um encerrado com comprovante. Deposita
R$ 10.000,00 por licitante; lances e liquidação afetam os saldos finais.
`DEMO_PASSWORD` permite definir outra senha antes da execução.

```sh
uv run python manage.py seed_demo             # cria ou reutiliza os dados
uv run python manage.py seed_demo --new-live  # adiciona um lote ao vivo
uv run python manage.py close_due_lots --once # liquida lotes vencidos
```

`seed_demo --reset` apaga e reconstrói os dados de demonstração, incluindo
saldos e histórico relacionados. Use apenas em desenvolvimento.

## Publicar no Northflank

Configure o build com contexto `backend/` e o Dockerfile desse diretório. O
comando padrão já inicia o ASGI em `0.0.0.0:7860`; exponha essa porta por HTTPS.
O entrypoint aplica migrations antes de servir, mas o banco precisa existir.

Cadastre as variáveis no **runtime do serviço da API**:

```env
DEBUG=False
SECRET_KEY=<segredo aleatório de pelo menos 50 caracteres>
BID_HISTORY_SECRET=<outro segredo aleatório>
RECEIPT_SECRET=<terceiro segredo aleatório>
DATABASE_URL=postgresql://usuario:senha@host:5432/banco
ALLOWED_HOSTS=api--auction-system-backend--cg7yjzmmcfrl.code.run
CORS_ALLOWED_ORIGINS=https://auction-system-neon.vercel.app
WS_ALLOWED_ORIGINS=https://auction-system-neon.vercel.app
AUTH_COOKIE_SECURE=True
AUTH_COOKIE_SAMESITE=None
AUTH_COOKIE_DOMAIN=
FRONTEND_URL=https://auction-system-neon.vercel.app
ENABLE_SETTLEMENT_TICKER=True
```

Substitua os exemplos de segredo e banco por valores próprios. Em campos de
variáveis do provedor, informe os valores sem aspas literais, espaços no início
ou no final e sem ponto e vírgula. As aspas de um arquivo `.env` são tratadas
pelo carregador; aspas digitadas como parte do valor no runtime são literais.
Após alterar variáveis, reinicie ou faça redeploy do serviço.

Os booleanos são lidos com `.lower()`, sem remover espaços. Por exemplo,
`AUTH_COOKIE_SECURE=True ` (com espaço final) resulta em `False`. Para conferir
no terminal **do serviço que atende o domínio da API**:

```sh
python manage.py shell -c 'import os; from django.conf import settings; print("raw:", repr(os.getenv("AUTH_COOKIE_SECURE"))); print("effective:", settings.AUTH_COOKIE_SECURE); print("samesite:", repr(settings.AUTH_COOKIE_SAMESITE))'
```

Nesse deploy, o resultado esperado é `raw: 'True'`, `effective: True` e
`samesite: 'None'`. Depois de publicar, execute `python manage.py seed_demo`
uma vez para preparar a demonstração.

Mantenha **um processo web e uma instância** enquanto o channel layer for em
memória. Para a âncora de auditoria, monte armazenamento persistente e defina
`BID_ANCHOR_PATH` para um arquivo gravável nesse volume. `MEDIA_ROOT` também
precisa de persistência para manter imagens baixadas.

### Variáveis principais

A lista completa e os padrões locais estão em [`.env.example`](.env.example).

| Variável | Uso no backend |
| --- | --- |
| `DATABASE_URL` | Conexão com o banco; tem prioridade sobre `POSTGRES_URL` |
| `POSTGRES_*` | Configuração do serviço PostgreSQL e da URL construída pelo Compose |
| `ALLOWED_HOSTS` | Hosts HTTP aceitos, sem protocolo |
| `CORS_ALLOWED_ORIGINS` | Origens HTTP do frontend, separadas por vírgula |
| `WS_ALLOWED_ORIGINS` | Origens WebSocket; usa CORS como fallback quando vazia. É a única lista usada no handshake, mesmo com frontend e API em hosts diferentes |
| `AUTH_COOKIE_SECURE` | Acrescenta `Secure` aos cookies JWT |
| `AUTH_COOKIE_SAMESITE` | Política `Lax`, `Strict` ou `None` |
| `AUTH_COOKIE_DOMAIN` | Domínio do cookie; vazio restringe ao host da API |
| `FRONTEND_URL` | Base para links compartilháveis de comprovantes |
| `BID_HISTORY_SECRET` / `RECEIPT_SECRET` | Segredos independentes de integridade |
| `BID_ANCHOR_PATH` | Caminho opcional do checkpoint JSONL fora do banco |
| `ENABLE_SETTLEMENT_TICKER` | Habilita o ticker no processo ASGI |

`POSTGRES_PORT` do template não é consultada por `settings.py` nem pelo Compose
atual; para alterar a porta de conexão local, ajuste `DATABASE_URL`. Para
alterar a porta publicada pelo Docker, ajuste o mapeamento do Compose.

### Verificar autenticação no navegador

Vercel e Northflank são sites diferentes: esse deploy requer
`AUTH_COOKIE_SECURE=True` e `AUTH_COOKIE_SAMESITE=None`. Em HTTP local, use
`False` e `Lax`. Políticas contra cookies de terceiros ainda podem impedir a
sessão; nesse caso, hospede frontend e API no mesmo site ou use um proxy na
origem do frontend.

Depois de entrar pelo frontend, confira em **Rede/Network**:

1. Login `POST /api/auth/token/` com `200` e dois `Set-Cookie` com `HttpOnly`,
   `Secure` e `SameSite=None`.
2. `GET /api/auth/me/` enviando `access_token` no cabeçalho `Cookie` e
   respondendo `200`.

Os cookies pertencem ao host da API. `HttpOnly` impede leitura por JavaScript,
mas permite inspeção no DevTools. A listagem no painel de armazenamento depende
do navegador e do contexto; no Firefox, o particionamento pode separar a sessão
usada pelo frontend da navegação direta ao domínio da API. Abrir `/me/` em
outra aba não substitui a verificação da chamada feita pelo frontend.

Um erro de CORS não prova que a API deixou de receber a requisição: o navegador
pode bloquear o acesso à resposta. Um preflight rejeitado pode impedir a chamada
seguinte. Já um `401` exige verificar os cookies enviados e a validade da sessão;
o status, sozinho, não determina a causa nem confirma que o CORS está correto.

Para previews da Vercel, cadastre a origem exata em CORS e WebSocket ou use o
domínio estável de produção. Origens incluem protocolo e não têm caminho nem
barra final.

Referências de comportamento do navegador: [Set-Cookie](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Set-Cookie),
[CORS](https://developer.mozilla.org/en-US/docs/Web/HTTP/Guides/CORS) e
[particionamento de estado no Firefox](https://developer.mozilla.org/en-US/docs/Web/Privacy/Guides/State_Partitioning).

## Autenticação

- `POST /api/auth/register` — cadastro com `email`, `password`, `role` e alias
  opcional.
- `POST /api/auth/token/` — login; grava `access_token` e `refresh_token` em
  cookies HttpOnly.
- `POST /api/auth/refresh/` — renova o access e rotaciona o refresh; o alias
  legado `/api/auth/token/refresh/` também existe.
- `POST /api/auth/logout/` — revoga o refresh e limpa os cookies.
- `GET /api/auth/me/` — dados privados da conta autenticada.
- `POST /api/auth/ws-ticket` — ticket curto e assinado para o WebSocket; o JWT
  não é colocado na URL.

Access dura 15 minutos; refresh dura 7 dias, com rotação e blacklist. O header
`Authorization: Bearer <token>` é aceito como fallback para ferramentas de API.
Em produção/HTTPS com frontend e API em sites diferentes, use
`AUTH_COOKIE_SECURE=True` e `AUTH_COOKIE_SAMESITE=None`; sem `Secure`, o
navegador descarta o cookie `SameSite=None`.

## API

Todos os valores monetários são strings decimais. Respostas públicas usam
aliases e nunca incluem e-mail, nome ou UUID de usuário. A paginação segue
`{count, next, previous, results}`.

| Método e rota | Acesso | Descrição |
|---|---|---|
| `POST /api/auth/register` | público | cadastro com e-mail, senha, papel e alias opcional |
| `POST /api/auth/token/` | público | login; grava cookies HttpOnly |
| `POST /api/auth/refresh/` | cookie | renova o access e rotaciona o refresh |
| `POST /api/auth/logout/` | público | revoga o refresh e limpa os cookies |
| `GET /api/auth/me/` | autenticado | dados privados da conta |
| `POST /api/auth/ws-ticket` | autenticado | ticket curto e assinado para WebSocket |
| `GET /api/catalog/search?q=` | leiloeiro | busca na AIC com cache e fallback local |
| `GET /api/catalog/items/{id}` | leiloeiro | item já persistido, sem chamada externa |
| `GET /api/lots` | público | vitrine com `tab`, `q`, `category`, `sort` e paginação |
| `GET /api/lots/{id}` | público | detalhe, `minimum_bid`, `server_time`, `state_version` e posição |
| `POST /api/lots` | leiloeiro | cria lote a partir de `catalog_item_id` |
| `POST /api/lots/{id}/cancel` | leiloeiro dono | cancela lote sem lances |
| `POST /api/lots/{id}/bids` | licitante | lance idempotente com `amount` e `client_bid_id` |
| `GET /api/lots/{id}/bids` | público | histórico paginado; `is_mine` só para autenticado |
| `GET /api/lots/{id}/audit` | público | cadeia, falhas e estado da âncora |
| `GET /api/me/bids` | licitante | lances próprios com `lot_id`, `lot_code` e `lot_title` |
| `GET /api/me/wins` | licitante | arremates, `issued_at` e `share_url` |
| `GET /api/wallet` | autenticado | saldo total, comprometido e disponível |
| `POST /api/wallet/deposits` | licitante | depósito simulado idempotente |
| `GET /api/wallet/transactions` | autenticado | extrato privado paginado |
| `GET /api/seller/lots` | leiloeiro | próprios lotes e liquidação sob demanda |
| `GET /api/seller/summary` | leiloeiro | total recebido, resultados, sem venda e bloqueios |
| `GET /api/receipts/{token}` | público | comprovante imutável sem PII |
| `GET /api/receipts/{token}/verify` | público | HMAC do recibo e vínculo com a cadeia |
| `GET /health/` | público/ops | disponibilidade HTTP |
| `GET /health/settlement/` | público/ops | estado do ticker de liquidação |
| `WS /ws/lots/{id}/` | público | eventos da sala; posição pessoal com ticket válido |
| `WS /ws/notifications/` | ticket | superado, vitória e venda |

Erros de regra seguem `{ "code": "...", "detail": "..." }`. Os códigos de lance
são `LOT_NOT_STARTED`, `LOT_ENDED`, `LOT_CANCELLED`, `LOT_SETTLED`,
`BID_AMOUNT_MISMATCH`, `BID_BELOW_MINIMUM`, `ALREADY_LEADING`,
`INSUFFICIENT_FUNDS`, `SELLER_CANNOT_BID`, `FORBIDDEN_ROLE` e
`IDEMPOTENCY_KEY_REUSED`. `INSUFFICIENT_FUNDS` inclui `available` e
`minimum_bid`.

## Regras de negócio

### Lances

- Só são aceitos em lote ao vivo, entre `starts_at` e `ends_at`.
- Só `BIDDER` pode dar lance; o leiloeiro nunca pode, nem no próprio lote.
- O primeiro lance deve ser exatamente o lance inicial; os seguintes, exatamente
  `current_bid + min_increment`.
- O líder atual não pode cobrir o próprio lance.
- O lance só é aceito se couber no saldo **disponível**.

### Saldo comprometido

`disponível = saldo total − comprometido`.

Quando um licitante assume a liderança, o valor do lance vira `committed`. Se
ele for superado, a reserva anterior é liberada imediatamente na mesma
transação. O débito definitivo só acontece na liquidação do arremate.

### Anti-sniping

Um lance aceito estritamente dentro dos últimos 2 minutos define
`ends_at = max(ends_at, now + 2 minutos)`. No limite exato de 2 minutos não há
extensão. Cada extensão real incrementa `extension_count`; `original_ends_at`
preserva o prazo original.

### Liquidação

O ticker ASGI processa lotes vencidos na inicialização e em intervalos, em
transações separadas. `settle_if_due` também atende leituras de detalhe,
auditoria e painéis. A liquidação valida a cadeia, o estado e a reserva antes de
debitar o vencedor e creditar o leiloeiro. Lote sem lances encerra sem vencedor;
lote cancelado não liquida. Inconsistências preenchem
`settlement_error`/`settlement_checked_at`, bloqueiam repetição automática e não
movimentam dinheiro.

Também é possível liquidar manualmente:

```sh
uv run python manage.py close_due_lots --once
```

### Integridade do histórico

Cada lance grava um payload JSON canônico (chaves ordenadas, separadores fixos,
valores com duas casas e timestamps UTC com microssegundos). A partir dele:

```text
content_hash = SHA-256(payload)
hash = HMAC-SHA256(BID_HISTORY_SECRET, prev_hash + ":" + content_hash)
```

O `prev_hash` do primeiro lance é 64 zeros; cada lance seguinte aponta para o
hash anterior. O lote guarda a cabeça da cadeia e a contagem de lances. A
auditoria recalcula e confere sequência, elo anterior, payload, HMAC, contagem e
cabeça. Alterações, remoções e inserções que não preservem essas verificações
resultam em `valid: false`, com a primeira sequência inválida.

Para detectar também um rollback completo do banco, um checkpoint JSONL pode ser
acrescentado fora do banco em `BID_ANCHOR_PATH`. Sem âncora, ou com âncora
atrasada, a resposta informa `unavailable`/`behind` e **não** classifica o lote
como adulterado. A limitação é consciente: a verificação HMAC é feita pelo
backend e a âncora local não protege contra controle total do servidor. Uma
garantia forte contra rollback exigiria um checkpoint externo confiável, object
lock ou log independente.

### Privacidade

Auditoria, histórico e comprovante mostram apenas aliases como
`Licitante-A1B2C3` e `Leiloeiro-D4E5F6`. E-mail, nome e UUID de usuário não
aparecem em respostas públicas, eventos WebSocket ou recibos. `is_mine` só é
exposto para o próprio usuário autenticado.

## Modelo de dados

| Modelo | Papel |
|---|---|
| `User` | E-mail como login, papel `SELLER`/`BIDDER`, alias público imutável |
| `Wallet` | Saldo total e comprometido por usuário |
| `WalletTransaction` | Livro-razão append-only de depósitos, holds, liberações e liquidações |
| `CatalogItem` | Snapshot do item da AIC, com atributos e imagens |
| `Lot` | Lote, valores, janela, vencedor, versão e estado de liquidação |
| `Bid` | Lance imutável, sequência, hashes e snapshot do prazo |
| `Receipt` | Comprovante imutável, token público, HMAC e cabeça da cadeia |

O banco também protege invariantes: `ends_at > starts_at`, valores positivos,
`current_bid >= starting_bid`, vencedor exige lance, `state_version >= 1` e
unicidade de `(lot, sequence)` em `Bid`. Lances, recibos e lotes usam `PROTECT`
para não apagar histórico por acidente.

## Qualidade

```sh
uv run ruff check .
uv run ruff format --check .
uv run mypy .
uv run python manage.py check
uv run python manage.py makemigrations --check --dry-run
uv run pytest
```

Os testes de concorrência usam PostgreSQL real e
verificam serialização por lote, carteira compartilhada entre lotes, corrida
entre lance e expiração, liquidação idempotente, adulteração da cadeia, recibo,
âncora, WebSocket e seed.

## Estrutura

```text
core/       settings, ASGI, health checks e ticker de liquidação
users/      usuário customizado, papéis, cookies JWT e ticket WS
wallet/     carteira, holds, extrato e depósitos simulados
auctions/   catálogo AIC, lotes, lances, liquidação, recibos e auditoria
tests/      domínio, API, concorrência, WebSocket e seed
scripts/    entrypoint do container
```

## Limitações operacionais

- O deploy de referência usa uma única instância; `InMemoryChannelLayer` não
  compartilha eventos entre processos. Para escalar, use Redis e um único
  processo para o ticker.
- A âncora JSONL é opcional e local. Sem ela, a auditoria informa
  `anchor_status: unavailable`; isso é uma limitação de garantia, não uma
  adulteração.
- A API externa (AIC) pode ficar indisponível; a busca cai para o acervo local e
  sinaliza `degraded: true`.
- O seed cria um lote ao vivo com três dias de duração; depois disso, use
  `--new-live` ou crie um lote pelo painel.
- O ticker roda no processo ASGI; com a aplicação parada, a liquidação aguarda
  a retomada ou uma consulta que execute `settle_if_due`.
- Imagens em `MEDIA_ROOT` exigem disco persistente para sobreviver a redeploys.
