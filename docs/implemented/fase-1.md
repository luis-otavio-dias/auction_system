# Fase 1 — Fundação do backend

**Status:** concluída  
**Data:** 2026-10-27  
**Escopo:** apps `users`, `wallet` e esqueleto de `auctions`; autenticação JWT por cookies; carteira inicial; configuração Django/DRF; migrations; testes e documentação.

---

## 1. Resumo

A Fase 1 entregou a base sobre a qual as fases seguintes serão construídas:

- usuário customizado com email como login, papéis de leiloeiro/licitante e alias público;
- carteira financeira com saldo total, comprometido e disponível;
- livro-razão append-only para depósitos;
- autenticação JWT entregue em cookies HttpOnly;
- refresh com rotação e blacklist;
- logout com revogação do refresh token;
- configuração de DRF, JWT, CORS, Channels em memória e mídia;
- migrations e testes automatizados.

O app `auctions` foi criado apenas como esqueleto. Lotes, lances, liquidação e auditoria pertencem às próximas fases.

---

## 2. Estrutura criada

```text
backend/
├── users/
│   ├── __init__.py
│   ├── admin.py
│   ├── apps.py
│   ├── authentication.py
│   ├── forms.py
│   ├── managers.py
│   ├── models.py
│   ├── serializers.py
│   ├── urls.py
│   ├── views.py
│   └── migrations/
│       ├── __init__.py
│       └── 0001_initial.py
├── wallet/
│   ├── __init__.py
│   ├── admin.py
│   ├── apps.py
│   ├── models.py
│   ├── services.py
│   ├── signals.py
│   └── migrations/
│       ├── __init__.py
│       └── 0001_initial.py
├── auctions/
│   ├── __init__.py
│   ├── admin.py
│   ├── apps.py
│   ├── models.py
│   └── migrations/__init__.py
└── tests/
    ├── conftest.py
    ├── users/
    │   ├── __init__.py
    │   ├── test_auth_cookies.py
    │   └── test_user_model.py
    └── wallet/
        ├── __init__.py
        ├── test_deposit_service.py
        └── test_wallet_model.py
```

---

## 3. App `users`

### 3.1 Modelo `User`

Custom user baseado em `AbstractBaseUser` + `PermissionsMixin`.

| Campo | Tipo | Observação |
|---|---|---|
| `id` | UUID | PK, gerado automaticamente |
| `email` | EmailField unique | login (`USERNAME_FIELD`) |
| `role` | CharField | `SELLER` ou `BIDDER` |
| `public_alias` | CharField unique | alias público, gerado automaticamente |
| `full_name` | CharField blank | dado privado |
| `is_active` | BooleanField | ativo/inativo |
| `is_staff` | BooleanField | acesso ao admin |
| `is_superuser` | BooleanField | superusuário |
| `date_joined` | DateTimeField | data de cadastro |
| `last_login` | DateTimeField | atualizado no login JWT |

Regras:

- `email` é normalizado para lowercase no manager e no `save()`.
- `public_alias` usa prefixo por papel:
  - `Leiloeiro-XXXXXX` para `SELLER`;
  - `Licitante-XXXXXX` para `BIDDER`.
- O sufixo tem 6 caracteres hexadecimais maiúsculos, gerados com `secrets`.
- Há checagem de unicidade em loop antes do `save`; a constraint do banco é a proteção final.
- `role` não é alterável pela API.
- `get_full_name()` retorna o nome civil ou o alias.
- `get_short_name()` retorna o alias público, preservando privacidade.
- `is_seller` e `is_bidder` são propriedades de conveniência.
- `REQUIRED_FIELDS` ficou como `list[str]` porque o tipo base do Django define `list[str]`; usar `tuple` quebraria o mypy.

### 3.2 Manager

`UserManager` implementa:

```python
create_user(
    email: str,
    password: str | None = None,
    *,
    role: str,
    full_name: str = "",
) -> User
```

```python
create_superuser(
    email: str,
    password: str | None = None,
    *,
    role: str = "SELLER",
    full_name: str = "",
) -> User
```

- `create_superuser` define `is_staff=True` e `is_superuser=True`.
- `set_password` é usado para armazenar o hash.
- `use_in_migrations = True`.

### 3.3 Admin

- `UserAdmin` customizado com `UserCreationForm` e `UserChangeForm`.
- `public_alias`, `id`, datas e `last_login` são readonly.
- Campos de coleção usam tuplas (`fieldsets`, `add_fieldsets`, `list_display`, `list_filter`, `search_fields`, `ordering`, `readonly_fields`, `filter_horizontal`).

### 3.4 Autenticação por cookies

Arquivo `users/authentication.py`:

```python
class CookieJWTAuthentication(JWTAuthentication):
    def get_header(self, request: Request) -> bytes:
        ...
```

- Lê o access token do cookie `access_token`.
- Mantém fallback para `Authorization: Bearer <token>`.
- Reutiliza `JWTAuthentication` para validar assinatura, expiração, usuário ativo etc.
- Se o cookie existir e for inválido, a requisição é rejeitada; não há fallback para header nesse caso.

### 3.5 Endpoints

Prefixo: `/api/auth/`.

| Método | Rota | Acesso | Função |
|---|---|---|---|
| POST | `/api/auth/token/` | público | login; grava cookies |
| POST | `/api/auth/refresh/` | refresh cookie | renova access e rotaciona refresh |
| POST | `/api/auth/token/refresh/` | refresh cookie | alias de compatibilidade |
| POST | `/api/auth/logout/` | público | blacklista refresh e apaga cookies |
| GET | `/api/auth/me/` | autenticado | dados privados do próprio usuário |

Exemplo de login:

```http
POST /api/auth/token/
Content-Type: application/json

{
  "email": "bidder@example.com",
  "password": "senha"
}
```

Resposta:

```json
{"detail": "Login realizado com sucesso."}
```

Os tokens **não** aparecem no corpo da resposta. Eles são enviados em `Set-Cookie`.

### 3.6 Cookies

| Configuração | Valor padrão | Uso |
|---|---|---|
| `AUTH_COOKIE_ACCESS_NAME` | `access_token` | nome do cookie de acesso |
| `AUTH_COOKIE_REFRESH_NAME` | `refresh_token` | nome do cookie de refresh |
| `AUTH_COOKIE_ACCESS_PATH` | `/` | acesso enviado a toda API |
| `AUTH_COOKIE_REFRESH_PATH` | `/api/auth/` | refresh restrito às rotas de auth |
| `AUTH_COOKIE_HTTP_ONLY` | `True` | JavaScript não lê o cookie |
| `AUTH_COOKIE_SECURE` | `False` (env) | `True` obrigatório em HTTPS |
| `AUTH_COOKIE_SAMESITE` | `Lax` (env) | proteção contra envio cross-site |
| `AUTH_COOKIE_DOMAIN` | vazio (env) | domínio opcional |
| `AUTH_COOKIE_ACCESS_MAX_AGE` | 15 min | validade do cookie de acesso |
| `AUTH_COOKIE_REFRESH_MAX_AGE` | 7 dias | validade do cookie de refresh |

Em produção/HTTPS:

```env
AUTH_COOKIE_SECURE="True"
AUTH_COOKIE_SAMESITE="Lax"
```

Para frontend e API em sites diferentes:

```env
AUTH_COOKIE_SECURE="True"
AUTH_COOKIE_SAMESITE="None"
```

Nesse cenário, endpoints que alteram estado precisam de proteção CSRF explícita.

### 3.7 Rotação e blacklist

Configuração em `SIMPLE_JWT`:

```python
"ROTATE_REFRESH_TOKENS": True,
"BLACKLIST_AFTER_ROTATION": True,
"UPDATE_LAST_LOGIN": True,
```

App instalado:

```python
"rest_framework_simplejwt.token_blacklist"
```

Comportamento:

- Login cria access e refresh.
- Refresh válido gera novo access e novo refresh.
- O refresh antigo é inserido na blacklist e não pode ser reutilizado.
- Logout tenta blacklistar o refresh atual antes de limpar os cookies.
- Refresh inválido, expirado ou blacklistado retorna `401`.
- Access expirado continua retornando `401` até o refresh ser feito.

Observação: o blacklist cobre refresh tokens. Access tokens continuam válidos até o `exp`; para revogação imediata de access seria necessário um mecanismo adicional de denylist/versionamento.

---

## 4. App `wallet`

### 4.1 Modelo `Wallet`

| Campo | Tipo | Observação |
|---|---|---|
| `id` | UUID | PK |
| `user` | OneToOne(User) | `related_name="wallet"`, `PROTECT` |
| `balance` | Decimal(12,2) | saldo total |
| `committed` | Decimal(12,2) | reservado em lances ativos |
| `created_at` | DateTimeField | |
| `updated_at` | DateTimeField | |

Propriedade:

```python
available = balance - committed
```

Constraints:

```text
balance >= 0
committed >= 0
committed <= balance
```

- A carteira é criada automaticamente para todo usuário, inclusive leiloeiro.
- `PROTECT` impede apagar usuário sem tratar a carteira; a política de exclusão será soft delete.

### 4.2 Modelo `WalletTransaction`

Livro-razão append-only.

| Campo | Tipo | Observação |
|---|---|---|
| `id` | UUID | PK |
| `wallet` | FK Wallet | `related_name="transactions"` |
| `type` | CharField | tipos abaixo |
| `amount` | Decimal(12,2) | sempre positivo |
| `balance_after` | Decimal(12,2) | snapshot |
| `committed_after` | Decimal(12,2) | snapshot |
| `reference_kind` | CharField | `NONE`, `LOT`, `BID`, `DEPOSIT` |
| `reference_id` | UUID nullable | referência externa |
| `idempotency_key` | CharField nullable | evita duplicidade |
| `description` | CharField blank | extrato |
| `metadata` | JSONField | dados extras |
| `created_at` | DateTimeField | |

Tipos:

- `DEPOSIT`
- `BID_HOLD`
- `BID_RELEASE`
- `SETTLEMENT_DEBIT`
- `SETTLEMENT_CREDIT`
- `CANCELLATION_RELEASE`
- `ADJUSTMENT_CREDIT`
- `ADJUSTMENT_DEBIT`

Constraints e índices:

```text
amount > 0
unique(wallet, idempotency_key) quando idempotency_key não é nulo
index(wallet, created_at)
index(reference_kind, reference_id)
```

`amount` é sempre positivo; o tipo define a direção. Ajustes usam tipos explícitos
`ADJUSTMENT_CREDIT`/`ADJUSTMENT_DEBIT` para não haver ambiguidade.

`WalletTransaction.signed_amount`:

- positivo para `DEPOSIT`, `SETTLEMENT_CREDIT`, `ADJUSTMENT_CREDIT`;
- negativo para `SETTLEMENT_DEBIT`, `ADJUSTMENT_DEBIT`;
- zero para holds/releases, que alteram apenas `committed`.

### 4.3 Signal de criação de carteira

`wallet/signals.py` escuta `post_save` no `AUTH_USER_MODEL` e executa:

```python
Wallet.objects.get_or_create(user_id=instance.pk)
```

O signal é carregado por `WalletConfig.ready()` via `importlib.import_module("wallet.signals")`.

### 4.4 Serviço de depósito

Arquivo `wallet/services.py`:

```python
deposit(
    wallet_id: UUID,
    amount: Decimal,
    idempotency_key: str | None = None,
    description: str = "",
) -> WalletTransaction
```

- Valida valor positivo e finito.
- Abre transação atômica.
- Faz `select_for_update()` na carteira.
- Busca a chave de idempotência **depois** do lock.
- Mesma chave + mesmo valor retorna o lançamento original.
- Mesma chave + valor diferente levanta `IdempotencyConflictError`.
- Atualiza `balance` e grava snapshots `balance_after`/`committed_after`.
- Exceções:
  - `WalletError`;
  - `InvalidAmountError`;
  - `IdempotencyConflictError`.

Hold, release e liquidação serão implementados na Fase 3.

### 4.5 Admin

- `Wallet` e `WalletTransaction` são somente leitura.
- `WalletTransaction` não permite add/change/delete.
- `available` e `signed_amount` aparecem como campos readonly.
- Coleções usam tuplas.

---

## 5. App `auctions`

Criado apenas como esqueleto:

- `AuctionsConfig`;
- `models.py` vazio;
- `admin.py` vazio;
- `migrations/__init__.py`.

As models de catálogo, lote, lance, comprovante e auditoria pertencem às fases seguintes.

---

## 6. Configuração Django

### 6.1 Apps instalados

Adicionados:

```python
"channels",
"corsheaders",
"rest_framework",
"rest_framework_simplejwt.token_blacklist",
"users",
"wallet",
"auctions",
```

### 6.2 Autenticação e DRF

```python
AUTH_USER_MODEL = "users.User"
ASGI_APPLICATION = "core.asgi.application"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "users.authentication.CookieJWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticatedOrReadOnly",
    ),
    "DEFAULT_PAGINATION_CLASS": (
        "rest_framework.pagination.PageNumberPagination"
    ),
    "PAGE_SIZE": 20,
}
```

### 6.3 JWT

- Access: 15 minutos.
- Refresh: 7 dias.
- Rotação de refresh: habilitada.
- Blacklist após rotação: habilitada.
- Atualização de `last_login`: habilitada.

### 6.4 Channels

```python
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    },
}
```

A camada em memória é uma concessão para o deploy demonstrativo de uma instância.
Redis externo será necessário se houver múltiplos processos.

### 6.5 CORS, mídia e locale

- `CorsMiddleware` habilitado.
- `CORS_ALLOW_CREDENTIALS = True`.
- `CORS_ALLOWED_ORIGINS` por env.
- `WS_ALLOWED_ORIGINS` por env, com fallback para CORS.
- `MEDIA_URL = "media/"`, `MEDIA_ROOT = BASE_DIR / "media"`.
- `LANGUAGE_CODE = "pt-br"`.
- `TIME_ZONE = "UTC"`.
- `DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"`.

### 6.6 Variáveis de ambiente

Adicionadas ao `.env.example`:

```env
AUTH_COOKIE_SECURE="False"
AUTH_COOKIE_SAMESITE="Lax"
AUTH_COOKIE_DOMAIN=""

WS_ALLOWED_ORIGINS="http://localhost:5173"

BID_HISTORY_SECRET="CHANGE-ME"
RECEIPT_SECRET="CHANGE-ME"
BID_ANCHOR_PATH=""

CATALOG_PROVIDER="artic"
FRONTEND_URL="http://localhost:5173"

ENABLE_SETTLEMENT_TICKER="True"
SETTLEMENT_INTERVAL_SECONDS="5"
SETTLEMENT_BATCH_SIZE="50"

WS_TICKET_MAX_AGE_SECONDS="60"
WS_CONNECTION_MAX_AGE_SECONDS="900"
```

### 6.7 Dependências

Adicionadas/ajustadas em `pyproject.toml`:

- `channels>=4.3.2`
- `httpx>=0.28.0`
- `uvicorn[standard]>=0.52.4`
- `rest_framework_simplejwt.token_blacklist` já faz parte do SimpleJWT instalado.

`known-first-party` do ruff atualizado para:

```toml
known-first-party = ["core", "users", "wallet", "auctions"]
```

---

## 7. Migrations

### 7.1 Criadas pelo projeto

`users/migrations/0001_initial.py`:

- cria `User`;
- inclui manager customizado;
- cria índice de `date_joined`.

`wallet/migrations/0001_initial.py`:

- cria `Wallet`;
- cria `WalletTransaction`;
- adiciona constraints de saldo;
- adiciona índices;
- adiciona constraint de idempotência.

### 7.2 Blacklist

O app `token_blacklist` trouxe suas migrations próprias. Foram aplicadas:

```text
token_blacklist.0001_initial
...
token_blacklist.0013_alter_blacklistedtoken_options_and_more
```

### 7.3 Banco local

O banco `auction_system_db` foi criado no container Postgres e recebeu:

```sh
uv run python manage.py migrate
```

Estado:

```text
users            0001_initial applied
wallet           0001_initial applied
token_blacklist  migrations applied
```

---

## 8. Testes

Arquivos:

- `tests/conftest.py`
- `tests/users/test_user_model.py`
- `tests/users/test_auth_cookies.py`
- `tests/wallet/test_wallet_model.py`
- `tests/wallet/test_deposit_service.py`

Cobertura:

### Users

- normalização de email;
- prefixo e formato do alias;
- unicidade do alias;
- criação de seller/bidder;
- `is_seller`/`is_bidder`;
- `get_full_name`/`get_short_name`;
- superuser;
- email duplicado;
- serializers sem tokens.

### Auth cookies

- login grava access e refresh HttpOnly;
- paths corretos;
- `SameSite`, `max-age` e flags;
- `/me` via cookie;
- `/me` via Bearer fallback;
- cookie ausente/inválido retorna 401;
- refresh rotaciona access;
- refresh antigo é blacklistado após rotação;
- refresh ausente/inválido retorna 401;
- logout limpa cookies;
- logout blacklista o refresh, e ele não pode ser reutilizado.

### Wallet

- criação automática via signal;
- saldo inicial zero;
- `available = balance - committed`;
- constraints de saldo;
- depósito atualiza saldo e cria lançamento;
- idempotência de depósito;
- conflito de chave com valor diferente;
- rejeição de valor zero/negativo;
- persistência de descrição.

Resultado final:

```text
32 passed
```

---

## 9. Qualidade e validação

Comandos executados:

```sh
uv sync --frozen
uv run ruff check .
uv run ruff format --check .
uv run mypy .
uv run pytest
uv run python manage.py check
uv run python manage.py makemigrations --check --dry-run
```

Resultados:

| Comando | Resultado |
|---|---|
| `uv sync --frozen` | OK |
| `ruff check .` | All checks passed |
| `ruff format --check .` | 42 files formatted |
| `mypy .` | Success, 36 source files |
| `pytest` | 32 passed |
| `manage.py check` | No issues |
| `makemigrations --check` | No changes detected |

Regras de estilo seguidas:

- sem `# noqa`;
- sem `# type: ignore`;
- sem `Any`/`Unknown`/`object` como atalho;
- tuplas em campos de admin que aceitam sequência;
- `REQUIRED_FIELDS` como `list[str]` por exigência do tipo base do Django.

---

## 10. Como executar

```sh
cd backend
cp .env.example .env
# editar credenciais
uv sync
uv run python manage.py migrate
uv run uvicorn core.asgi:application --reload --port 8001
```

Health check:

```sh
curl http://localhost:8001/health/
```

Login:

```sh
curl -i -c cookies.txt \
  -H 'Content-Type: application/json' \
  -d '{"email":"bidder@example.com","password":"senha"}' \
  http://localhost:8001/api/auth/token/
```

Me:

```sh
curl -b cookies.txt http://localhost:8001/api/auth/me/
```

Refresh:

```sh
curl -i -b cookies.txt -c cookies.txt \
  -X POST http://localhost:8001/api/auth/refresh/
```

Logout:

```sh
curl -i -b cookies.txt -c cookies.txt \
  -X POST http://localhost:8001/api/auth/logout/
```

---

## 11. Segurança e limitações conhecidas

- `AUTH_COOKIE_SECURE` deve ser `True` em produção/HTTPS.
- Para frontend e API em sites diferentes, usar `SameSite=None` + `Secure=True` e proteção CSRF nos endpoints de escrita.
- O access token é stateless e continua válido até expirar; a blacklist cobre refresh tokens.
- O logout revoga o refresh atual e limpa os cookies.
- A camada de Channels em memória exige uma instância/processo.
- O app `auctions` ainda não possui models.
- Não há endpoints de carteira nem de usuários além de `/me` nesta fase.
- O container `auction-system-backend` não foi reiniciado após as alterações; a validação foi feita via ambiente local/`uv`.
- O banco local foi criado e migrado; o deploy precisará rodar `migrate`.

---

## 12. Próxima fase

**Plano detalhado:** [`../fases/fase-2.md`](../fases/fase-2.md)  
**Índice das fases:** [`../fases/README.md`](../fases/README.md)

A Fase 2 deve começar por:

- `CatalogItem` e adapter da Art Institute of Chicago;
- model `Lot` e snapshot do item;
- vitrine pública;
- detalhe do lote;
- criação e cancelamento pelo leiloeiro;
- cache e fallback para indisponibilidade da API externa.

Antes de iniciar a Fase 3, ainda serão necessários os serviços de hold/release e a cadeia de hashes dos lances.
