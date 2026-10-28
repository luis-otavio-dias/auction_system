# Backend — Auction System

API em Django e Django REST Framework para a plataforma de leilões.

## Requisitos

- Python 3.14+
- [uv](https://docs.astral.sh/uv/)
- PostgreSQL 18+ ou o serviço `db` do Docker Compose
- Docker e Docker Compose (opcional)

## Configuração

```sh
cp .env.example .env
# Edite .env com SECRET_KEY e credenciais do banco.
uv sync
```

O PostgreSQL deve ser configurado por `DATABASE_URL` ou `POSTGRES_URL` para
produção e testes de concorrência. SQLite fica limitado ao desenvolvimento sem
validação de locks; `DEBUG=False` exige PostgreSQL.

## Execução local

```sh
uv run python manage.py migrate
uv run python manage.py collectstatic --noinput
uv run uvicorn core.asgi:application --reload --port 8001
```

A API fica em `http://localhost:8001` e o health check em
`http://localhost:8001/health/`.

## Autenticação por cookies JWT

- `POST /api/auth/token/` — login com `email` e `password`; grava
  `access_token` e `refresh_token` em cookies HttpOnly.
- `POST /api/auth/refresh/` — renova o access token a partir do cookie de
  refresh e rotaciona o refresh. O alias `/api/auth/token/refresh/` também
  existe.
- `POST /api/auth/logout/` — remove os cookies de autenticação.
- `GET /api/auth/me/` — dados privados do usuário autenticado.

O access token também pode ser enviado em `Authorization: Bearer <token>` como
fallback para ferramentas e clientes de API.

O app `rest_framework_simplejwt.token_blacklist` está habilitado. O refresh é
rotacionado e o token antigo é invalidado (`BLACKLIST_AFTER_ROTATION=True`); o
logout também revoga o refresh token antes de limpar os cookies.

Em produção/HTTPS, configure `AUTH_COOKIE_SECURE=True`. Para frontend e API em
origens diferentes, configure `AUTH_COOKIE_SAMESITE=None` junto com
`AUTH_COOKIE_SECURE=True` e adicione proteção CSRF aos endpoints de escrita.

## Catálogo e lotes

- `GET /api/catalog/search?q=` — leiloeiro; busca a Art Institute of Chicago
  com cache local e fallback para itens já persistidos. Quando a AIC está
  indisponível (por exemplo, bloqueio do Cloudflare), a resposta traz
  `degraded: true` e o acervo local completo em vez de HTTP 503.
- As imagens do seed são empacotadas em
  `auctions/static/auctions/catalog/` e servidas em `/static/...`; imagens
  remotas baixadas com sucesso continuam sendo cacheadas em `/media/...`.
- `GET /api/catalog/items/{id}` — leiloeiro; item em cache, sem chamada externa.
- `GET /api/lots` — público; vitrine paginada com `tab`, `q`, `category` e
  `sort`.
- `GET /api/lots/{id}` — público; detalhe com `minimum_bid`, `server_time`,
  `state_version` e `seller_alias`.
- `POST /api/lots` — leiloeiro; cria o lote a partir de um `catalog_item_id`
  persistido.
- `POST /api/lots/{id}/cancel` — leiloeiro dono; cancela lote sem lances.

O seed de demonstração não depende da API externa:

```sh
uv run python manage.py seed_demo
```

Ele cria um leiloeiro (`leiloeiro@demo.com`), dois licitantes
(`cliente1@demo.com`, `cliente2@demo.com`), carteiras com depósitos, um lote ao
vivo com ao menos dois lances, um lote agendado e um encerrado com comprovante.
A senha padrão é `demo-password-123` e pode ser alterada com `DEMO_PASSWORD`.
`--new-live` adiciona outro lote ao vivo; `--reset` remove e reconstrói os dados
de demonstração.

Imagens baixadas ficam em `MEDIA_ROOT/lots/`; se o download falhar, o lote usa
a URL remota e `image_cached=False`.

## Docker Compose

```sh
cp .env.example .env
# Edite .env antes de subir os containers.
docker compose up --build
```

O Compose exige que `POSTGRES_PASSWORD` esteja definida no `.env`. O backend fica
disponível em `http://localhost:8001` (porta 7860 no container).

## Qualidade

```sh
uv run ruff check .
uv run ruff format --check .
uv run mypy .
uv run pytest
```

## Estrutura

- `core/` — configuração Django, rotas e health check.
- `users/` — usuário customizado, papéis e autenticação por cookies JWT.
- `wallet/` — carteira, livro-razão e depósito simulado.
- `auctions/` — catálogo AIC, lotes, vitrine, criação e cancelamento.
- `tests/` — testes automatizados.
- `scripts/entrypoint.sh` — executa as migrações antes de iniciar o container.
