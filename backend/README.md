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

Sem `DATABASE_URL` ou `POSTGRES_URL`, o projeto usa SQLite em `db.sqlite3`.

## Execução local

```sh
uv run python manage.py migrate
uv run uvicorn core.asgi:application --reload --port 8001
```

A API fica em `http://localhost:8001` e o health check em
`http://localhost:8001/health/`.

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
- `tests/` — testes automatizados.
- `scripts/entrypoint.sh` — executa as migrações antes de iniciar o container.
