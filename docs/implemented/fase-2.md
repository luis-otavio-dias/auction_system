# Fase 2 — Catálogo AIC e lotes

**Status:** concluída  
**Data:** 2026-10-27  
**Depende de:** Fase 1  
**Escopo:** models `CatalogItem` e `Lot`; integração com a Art Institute of
Chicago; serviços de catálogo, imagem e lote; seletores; serializers; permissões;
views; rotas; admin; migration; seed local; testes e documentação.

---

## 1. Resumo

A Fase 2 entregou o catálogo de obras e a vitrine de lotes, encerrando antes de
qualquer lance:

- `CatalogItem` como snapshot imutável de um item da API externa;
- adapter `ArticProvider` com timeout, retry, circuit breaker e normalização;
- busca de catálogo com persistência local e fallback para o banco;
- download de imagens para `MEDIA_ROOT/lots/` com fallback para a URL remota;
- model `Lot` com snapshot do item, datas, valores, status derivado e
  `state_version`;
- criação de lote pelo leiloeiro a partir de um `CatalogItem` já persistido;
- cancelamento de lote sem lances pelo leiloeiro dono;
- vitrine pública com filtros, busca, ordenação e paginação;
- detalhe público do lote;
- permissões de leiloeiro e licitante;
- admin somente leitura;
- migration `auctions/0001_initial.py`;
- fixtures locais e comando `seed_demo` sem dependência da AIC;
- 65 novos testes, totalizando 97 testes verdes.

Nesta fase, `Lot.current_bid` e `Lot.current_winner` permanecem nulos. Lances,
holds, liquidação, comprovante, auditoria e WebSocket continuam fora do escopo.

---

## 2. Estrutura criada

```text
backend/
├── auctions/
│   ├── __init__.py
│   ├── admin.py
│   ├── apps.py
│   ├── models.py
│   ├── permissions.py
│   ├── seed_data.py
│   ├── selectors.py
│   ├── serializers.py
│   ├── urls.py
│   ├── views.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── catalog.py
│   │   ├── images.py
│   │   └── lots.py
│   ├── management/
│   │   ├── __init__.py
│   │   └── commands/
│   │       ├── __init__.py
│   │       └── seed_demo.py
│   └── migrations/
│       ├── __init__.py
│       └── 0001_initial.py
└── tests/
    └── auctions/
        ├── __init__.py
        ├── conftest.py
        ├── test_catalog.py
        ├── test_lot_api.py
        └── test_lot_model.py
```

Também foram alterados:

- `core/settings.py` — configurações do catálogo e mídia;
- `core/urls.py` — inclusão das rotas de `auctions` e mídia local;
- `backend/.env.example` — novas variáveis do catálogo;
- `backend/README.md` — endpoints e seed;
- `docs/fases/fase-2.md` — status e registro de implementação;
- `docs/fases/README.md` — status da fase.

---

## 3. App `auctions` — modelos

### 3.1 `CatalogItem`

Snapshot imutável de um item do catálogo externo.

| Campo | Tipo | Observação |
|---|---|---|
| `id` | UUID | PK, gerado automaticamente |
| `source` | CharField(32) | provedor; `artic` por padrão |
| `external_id` | CharField(64) | ID na AIC |
| `title` | CharField(300) | snapshot |
| `description` | TextField blank | snapshot |
| `image_url` | URLField(500) | imagem principal |
| `thumbnail_url` | URLField(500) blank | miniatura |
| `source_url` | URLField(500) | página original |
| `category` | CharField(100) blank | departamento/classificação |
| `attributes` | JSONField | artista, data, técnica, procedência etc. |
| `raw_payload` | JSONField | payload original |
| `fetched_at` | DateTimeField | instante da coleta |
| `created_at` | DateTimeField | criação local |

Constraints e índices:

```text
unique(source, external_id)
index(source)
index(category)
```

Regras:

- `save()` em uma instância já persistida levanta `ValueError`; o item é um
  snapshot e não deve ser atualizado.
- `get_or_create()` é usado na persistência, portanto um item já existente não
  é sobrescrito.
- `raw_payload` é interno e não aparece no serializer público do catálogo.
- O item é usado para copiar o snapshot do lote, que não depende do catálogo em
  leitura.

### 3.2 `Lot`

Lote com snapshot do item, datas, valores, estado derivado e campos reservados
para as fases seguintes.

| Campo | Tipo | Observação |
|---|---|---|
| `id` | UUID | PK |
| `code` | CharField(12) unique | código curto `L-XXXXXXXXXX` |
| `seller` | FK User PROTECT | `related_name="lots"` |
| `catalog_item` | FK CatalogItem PROTECT nullable | rastreabilidade |
| `title` | CharField(300) | snapshot |
| `description` | TextField blank | snapshot |
| `image_url` | URLField(500) | imagem usada pelo frontend |
| `image_remote_url` | URLField(500) | URL original |
| `image_cached` | BooleanField | imagem baixada? |
| `source` | CharField(32) | snapshot |
| `external_id` | CharField(64) | snapshot |
| `source_url` | URLField(500) | snapshot |
| `category` | CharField(100) blank | filtro |
| `attributes` | JSONField | snapshot |
| `starting_bid` | Decimal(12,2) | > 0 |
| `min_increment` | Decimal(12,2) | > 0 |
| `current_bid` | Decimal(12,2) nullable | nulo sem lances |
| `current_winner` | FK User nullable PROTECT | nulo sem lances |
| `starts_at` | DateTimeField | início |
| `ends_at` | DateTimeField | fim; muda com anti-sniping na Fase 3 |
| `original_ends_at` | DateTimeField | fim original, imutável |
| `extension_count` | PositiveIntegerField | começa em 0 |
| `bids_count` | PositiveIntegerField | começa em 0 |
| `history_head` | CharField(64) blank | último hash |
| `history_version` | PositiveSmallIntegerField | versão do algoritmo |
| `state_version` | PositiveBigIntegerField | começa em 1 |
| `cancelled_at` | DateTimeField nullable | |
| `cancelled_by` | FK User nullable PROTECT | |
| `cancel_reason` | CharField(255) blank | |
| `settled_at` | DateTimeField nullable | Fase 4 |
| `winner` | FK User nullable PROTECT | Fase 4 |
| `final_price` | Decimal(12,2) nullable | Fase 4 |
| `settlement_error` | TextField blank | interno |
| `settlement_checked_at` | DateTimeField nullable | interno |
| `created_at`, `updated_at` | DateTimeField | |

Constraints:

```text
ends_at > starts_at
starting_bid > 0
min_increment > 0
current_bid is null or current_bid >= starting_bid
current_winner is null or current_bid is not null
final_price is null or final_price >= 0
state_version >= 1
```

Índices:

```text
starts_at
ends_at
seller
category
current_winner
```

Status derivado, sem coluna `status`:

```text
cancelled_at preenchido -> cancelled
settled_at preenchido   -> ended
now < starts_at         -> scheduled
now < ends_at           -> live
caso contrário          -> ended
```

Propriedades:

```python
minimum_bid = starting_bid if current_bid is None else current_bid + min_increment
has_bids    = bids_count > 0
is_cancelled = cancelled_at is not None
is_settled   = settled_at is not None
```

Regras:

- O lote não é editável depois de criado; nesta fase só pode ser cancelado.
- `original_ends_at` é imutável.
- `state_version` começa em 1 e é incrementado em cancelamentos.
- `settlement_error` e `settlement_checked_at` não aparecem em serializers
  públicos.
- A vitrine nunca mostra lotes cancelados.
- O detalhe público continua acessível para um lote cancelado, exibindo o
  status `cancelled`.

---

## 4. Integração com a AIC

### 4.1 `ArticProvider`

Arquivo: `auctions/services/catalog.py`.

Interface:

```text
CatalogProvider.search(query, limit) -> list[ExternalItem]
CatalogProvider.get_item(external_id) -> ExternalItem
```

Endpoints usados:

```text
https://api.artic.edu/api/v1/artworks/search
https://api.artic.edu/api/v1/artworks/{id}
https://www.artic.edu/iiif/2/{image_id}/full/843,/0/default.jpg
https://www.artic.edu/iiif/2/{image_id}/full/400,/0/default.jpg
```

Comportamento:

- `httpx.Client` com timeout de 5 s;
- `User-Agent` configurável identificando a aplicação;
- até 2 tentativas no total, com backoff de 0,2 s;
- retry para timeout, erro de transporte, HTTP 429 e 5xx;
- HTTP 404 em `get_item` vira `CatalogItemNotFoundError`;
- resposta inválida vira `CatalogUnavailableError`;
- circuit breaker em `django.core.cache`:
  - 3 falhas abrem o circuito;
  - cooldown de 60 s;
  - sucesso reseta o contador.
- cache local de resultados de busca para fallback;
- client HTTP injetável, permitindo `httpx.MockTransport` nos testes.

Normalização:

- `external_id` a partir de `id`;
- `title`, com fallback `Obra sem título`;
- descrição composta com a descrição original e artista/data/técnica;
- imagem principal e thumbnail via IIIF;
- quando não há `image_id`, `image_url` usa a página original e a thumbnail fica
  vazia;
- `source_url` aponta para `https://www.artic.edu/artworks/{id}`;
- `category` usa `department_title`, com fallback para `classification_title`;
- `attributes` recebe apenas valores textuais não vazios de:
  `artist_display`, `date_display`, `medium_display`, `department_title`,
  `place_of_origin` e `credit_line`;
- `raw_payload` guarda o item original;
- `fetched_at` é preenchido no momento da coleta.

### 4.2 Persistência e fallback

Fluxo de `search_catalog`:

1. tenta o provedor configurado;
2. persiste cada item retornado com `get_or_create`;
3. devolve `from_cache=False` e `degraded=False`;
4. em falha do provedor, tenta o cache de resultados e depois o banco;
5. se houver item em cache, devolve `from_cache=True` e `degraded=True`;
6. se a busca textual não encontrar nada no banco, devolve o acervo local
   completo para não bloquear a criação de lotes;
7. se não houver nenhum item local, levanta `CatalogUnavailableError`,
   convertido em HTTP 503.

Quando a AIC responde com desafio do Cloudflare (HTTP 403), o fallback local
mantém o painel do leiloeiro funcional e o frontend avisa que o catálogo
externo está indisponível.

`get_catalog_item` consulta apenas o banco. Vitrine, detalhe, cancelamento e
criação de lote nunca chamam a AIC.

### 4.3 Imagens

Arquivo: `auctions/services/images.py`.

`cache_remote_image(image_url, external_id)`:

- baixa a imagem com timeout de 5 s;
- valida status 200, conteúdo não vazio e `content-type` iniciado por `image/`;
- grava em `MEDIA_ROOT/lots/` com nome sanitizado e único;
- devolve a URL pública `/media/lots/...`;
- em qualquer falha, devolve `None` sem propagar exceção.

Na criação do lote:

- se o download funcionar, `image_cached=True` e `image_url` aponta para o
  arquivo local;
- se falhar, `image_cached=False` e `image_url == image_remote_url`.

`MEDIA_URL` passou a ser `/media/`, e `core/urls.py` serve mídia local também
fora do modo `DEBUG`. As imagens do seed são empacotadas em
`auctions/static/auctions/catalog/` para não depender da rede, e as URLs
relativas são devolvidas como absolutas pelos serializers.

### 4.4 Configurações do catálogo

Adicionadas em `core/settings.py` e `.env.example`:

```env
CATALOG_PROVIDER="artic"
CATALOG_HTTP_TIMEOUT_SECONDS="5"
CATALOG_HTTP_MAX_ATTEMPTS="2"
CATALOG_HTTP_BACKOFF_SECONDS="0.2"
CATALOG_CIRCUIT_THRESHOLD="3"
CATALOG_CIRCUIT_COOLDOWN_SECONDS="60"
CATALOG_SEARCH_CACHE_SECONDS="300"
CATALOG_USER_AGENT="AuctionSystem/0.1 (Art Institute of Chicago catalog integration)"
```

---

## 5. Serviços e seletores

### 5.1 Criação de lote

Arquivo: `auctions/services/lots.py`.

`create_lot(seller, catalog_item, starts_at, ends_at, starting_bid,
min_increment) -> Lot`.

Validações:

- usuário precisa ser `SELLER`;
- datas precisam ser aware;
- `starts_at < ends_at`;
- `ends_at` precisa estar no futuro;
- `starting_bid` e `min_increment` precisam ser finitos e positivos.

Fluxo:

- tenta baixar a imagem antes da transação;
- copia título, descrição, imagem, origem, categoria e atributos do
  `CatalogItem`;
- preenche `image_remote_url` com a URL original;
- define `original_ends_at = ends_at`;
- define `state_version = 1`;
- mantém `current_bid` e `current_winner` nulos;
- cria o lote dentro de `transaction.atomic()`.

A assinatura usa `TypedDict` + `Unpack` para manter a chamada por palavra-chave
sem `# noqa PLR0913`.

### 5.2 Cancelamento

`cancel_lot(lot_id, seller, reason="") -> Lot`.

Regras:

- usuário precisa ser `SELLER`;
- abre transação atômica e faz `select_for_update()` no lote;
- captura `now` **depois** do lock;
- somente o leiloeiro dono pode cancelar;
- lote já cancelado retorna `LOT_CANCELLED`;
- lote encerrado retorna `LOT_ENDED`;
- lote com lances retorna `LOT_HAS_BIDS`;
- preenche `cancelled_at`, `cancelled_by` e `cancel_reason`;
- incrementa `state_version` em 1;
- salva com `update_fields` em tupla, incluindo `updated_at`.

### 5.3 Códigos de erro de lote

| Exceção | Código | HTTP |
|---|---|---|
| `LotNotFoundError` | `LOT_NOT_FOUND` | 404 |
| `LotNotOwnedError` | `LOT_NOT_OWNED` | 403 |
| `ForbiddenRoleError` | `FORBIDDEN_ROLE` | 403 |
| `LotHasBidsError` | `LOT_HAS_BIDS` | 409 |
| `LotEndedError` | `LOT_ENDED` | 409 |
| `LotAlreadyCancelledError` | `LOT_CANCELLED` | 409 |
| `InvalidLotScheduleError` | `INVALID_LOT_SCHEDULE` | 422 |
| `InvalidLotAmountError` | `INVALID_LOT_AMOUNT` | 422 |

O formato de resposta de erro de domínio é:

```json
{
  "code": "LOT_HAS_BIDS",
  "detail": "Lotes que já receberam lances não podem ser cancelados."
}
```

### 5.4 Seletores

Arquivo: `auctions/selectors.py`.

- `visible_lots()`: exclui cancelados e faz `select_related` de vendedor e
  líder atual.
- `filter_lots()`:
  - `tab=live`: `starts_at <= now < ends_at`, não liquidado;
  - `tab=scheduled`: `starts_at > now`, não liquidado;
  - `tab=ended`: `ends_at <= now` ou `settled_at` preenchido;
  - `tab` vazio: todos os visíveis;
  - `q`: busca em título, descrição e categoria;
  - `category`: comparação case-insensitive;
  - `sort=ending`: fim mais próximo;
  - `sort=price-high`/`price-low`: preço efetivo
    (`Coalesce(current_bid, starting_bid)`), com `nulls_last=True`;
  - `sort=recent`: criação mais recente;
  - desempate por `-created_at`.
- `get_public_lot()`: detalhe com `select_related`, incluindo cancelados.
- `search_cached_catalog()`: fallback de busca no banco por título, descrição,
  categoria e `external_id`.

---

## 6. API

Prefixo: `/api`.

### 6.1 Rotas

| Método | Rota | Acesso | Função |
|---|---|---|---|
| GET | `/api/catalog/search?q=&limit=` | leiloeiro | busca AIC com cache e fallback |
| GET | `/api/catalog/items/{id}` | leiloeiro | item já persistido |
| GET | `/api/lots` | público | vitrine paginada |
| GET | `/api/lots/{id}` | público | detalhe do lote |
| POST | `/api/lots` | leiloeiro | criar lote |
| POST | `/api/lots/{id}/cancel` | leiloeiro dono | cancelar sem lances |

Rotas sem barra final, registradas em `auctions/urls.py` e incluídas em
`core/urls.py` sob `/api/`.

### 6.2 Busca de catálogo

Resposta de sucesso:

```json
{
  "count": 1,
  "from_cache": false,
  "results": [
    {
      "id": "UUID",
      "source": "artic",
      "external_id": "6565",
      "title": "American Gothic",
      "description": "...",
      "image_url": "...",
      "thumbnail_url": "...",
      "source_url": "...",
      "category": "American Art",
      "attributes": {},
      "fetched_at": "2026-10-27T18:18:06Z"
    }
  ]
}
```

- `q` é obrigatório, com até 200 caracteres;
- `limit` fica entre 1 e 50, padrão 20;
- quando a AIC falha e não há cache, a resposta é HTTP 503 com
  `code=CATALOG_UNAVAILABLE`;
- `raw_payload` não é exposto.

### 6.3 Vitrine

Filtros:

```text
tab=live|scheduled|ended
q=<texto>
category=<categoria>
sort=ending|price-high|price-low|recent
```

- paginação DRF com 20 itens por página;
- resposta padrão `count`, `next`, `previous`, `results`;
- cancelados nunca aparecem;
- cada item contém `id`, `code`, `status`, `title`, `image_url`, `category`,
  `starting_bid`, `current_bid`, `min_increment`, `minimum_bid`, `starts_at`,
  `ends_at`, `bids_count`, `state_version` e `seller_alias`.

### 6.4 Detalhe público

Resposta inclui:

- `id`, `code`, `status`, `title`, `description`, `image_url`;
- `source`, `external_id`, `source_url`, `category`, `attributes`;
- `starting_bid`, `min_increment`, `current_bid`, `minimum_bid`;
- `starts_at`, `ends_at`, `original_ends_at`, `extension_count`;
- `bids_count`, `state_version`;
- `seller_alias`;
- `my_position` sempre `null` nesta fase;
- `server_time`.

Dinheiro é serializado como string decimal, por exemplo `"1000.00"`. O status
e o `server_time` usam o mesmo instante capturado pela view.

Campos internos como `settlement_error` e `settlement_checked_at`, dados
privados do usuário e IDs de usuários não são expostos.

### 6.5 Criação de lote

Payload:

```json
{
  "catalog_item_id": "UUID",
  "starts_at": "2026-10-27T18:00:00Z",
  "ends_at": "2026-10-28T18:00:00Z",
  "starting_bid": "1000.00",
  "min_increment": "100.00"
}
```

Regras:

- somente leiloeiro autenticado;
- `catalog_item_id` precisa existir no banco;
- `starts_at < ends_at`;
- `ends_at` precisa estar no futuro;
- valores precisam ser maiores que zero;
- o vendedor é sempre o usuário autenticado; campos `seller` ou `seller_id` no
  payload são ignorados;
- se `starts_at <= now < ends_at`, o lote nasce `live`;
- se `starts_at > now`, nasce `scheduled`;
- resposta `201` com o detalhe do lote.

### 6.6 Cancelamento

```http
POST /api/lots/{id}/cancel
Content-Type: application/json

{"reason": "item indisponível"}
```

Respostas esperadas:

- `200` com o detalhe atualizado e `state_version` incrementado;
- `409 LOT_HAS_BIDS` quando há lances;
- `409 LOT_ENDED` após `ends_at`;
- `409 LOT_CANCELLED` em cancelamento repetido;
- `403 LOT_NOT_OWNED` para outro leiloeiro;
- `404 LOT_NOT_FOUND` para lote inexistente.

### 6.7 Permissões

| Ação | Público | Licitante | Leiloeiro |
|---|---|---|---|
| Ver vitrine | sim | sim | sim |
| Ver detalhe | sim | sim | sim |
| Buscar catálogo | não | não | sim |
| Ver item em cache | não | não | sim |
| Criar lote | não | não | sim |
| Cancelar lote | não | não | somente o dono |

A permissão `IsSeller` exige usuário autenticado, instância de `users.User` e
`is_seller`.

---

## 7. Admin

Arquivo: `auctions/admin.py`.

### `CatalogItemAdmin`

- somente leitura: sem add, change ou delete;
- lista título, origem, `external_id`, categoria e datas;
- filtros por origem, categoria e data de coleta;
- busca por título, descrição, `external_id` e categoria;
- todos os campos são readonly, incluindo `raw_payload`.

### `LotAdmin`

- somente leitura;
- lista `code`, título, vendedor, status derivado, `bids_count`,
  `current_bid`, datas e cancelamento;
- `status_display` usa `@admin.display`;
- `list_select_related` para vendedor, catálogo e líder;
- filtros por categoria, imagem, datas, cancelamento e liquidação;
- busca por código, título, descrição, `external_id` e email do vendedor;
- todos os campos são readonly, incluindo `minimum_bid` e o status.

---

## 8. Migrations

`auctions/migrations/0001_initial.py` cria:

- `CatalogItem`;
- `Lot`;
- unique constraint de `(source, external_id)`;
- índices de catálogo e lote;
- constraints de datas, valores, líder e `state_version`.

A migration foi aplicada no banco local:

```sh
uv run python manage.py migrate
```

Estado:

```text
auctions         0001_initial applied
```

`makemigrations --check` não detecta mudanças pendentes.

---

## 9. Seed

Arquivo de dados: `auctions/seed_data.py`.

Quatro itens locais:

1. Uma Tarde de Domingo na Ilha de La Grande Jatte;
2. American Gothic;
3. Nighthawks;
4. O Quarto.

Cada item contém título, descrição, imagem, thumbnail, URL de origem, categoria,
atributos e `raw_payload` local.

Comando:

```sh
uv run python manage.py seed_demo
```

Comportamento:

- não acessa a AIC nem baixa imagens;
- cria ou reutiliza os itens com `get_or_create`;
- cria ou reutiliza o leiloeiro `leiloeiro@demo.com`;
- senha padrão `demo-password-123`, configurável por `DEMO_PASSWORD`;
- cria um lote ao vivo com o primeiro item;
- não duplica lote já existente para o mesmo vendedor/obra;
- é idempotente e imprime um resumo da operação.

O seed de lotes completo continua previsto para a Fase 7.

---

## 10. Configuração e dependências

### 10.1 Settings

Adicionados em `core/settings.py`:

- `CATALOG_PROVIDER`;
- `CATALOG_HTTP_TIMEOUT_SECONDS`;
- `CATALOG_HTTP_MAX_ATTEMPTS`;
- `CATALOG_HTTP_BACKOFF_SECONDS`;
- `CATALOG_CIRCUIT_THRESHOLD`;
- `CATALOG_CIRCUIT_COOLDOWN_SECONDS`;
- `CATALOG_SEARCH_CACHE_SECONDS`;
- `CATALOG_USER_AGENT`;
- `MEDIA_URL = "/media/"`.

`core/urls.py` passou a incluir:

```python
path("api/", include("auctions.urls"))
```

e a servir mídia local em desenvolvimento com `django.conf.urls.static.static`.

### 10.2 Dependências

Não foi necessária nova dependência: `httpx` já estava instalado desde a Fase 1.
O `known-first-party` do ruff já incluía `auctions`:

```toml
known-first-party = ["core", "users", "wallet", "auctions"]
```

---

## 11. Testes

Arquivos e quantidade:

| Arquivo | Testes |
|---|---:|
| `tests/auctions/test_catalog.py` | 19 |
| `tests/auctions/test_lot_api.py` | 24 |
| `tests/auctions/test_lot_model.py` | 22 |
| **Novos na Fase 2** | **65** |
| **Total do projeto** | **97** |

Fixtures compartilhadas em `tests/auctions/conftest.py`:

- `catalog_item`;
- `other_catalog_item`;
- `other_seller`;
- `lot`;
- `login`.

### Catálogo

- normalização de payload da AIC;
- imagem IIIF principal e thumbnail;
- fallback de imagem quando não há `image_id`;
- retry de 5xx e timeout em exatamente 2 tentativas;
- resposta de busca malformada;
- busca com persistência de `CatalogItem`;
- fallback para cache do banco;
- fallback quando a criação do provider falha;
- ausência de cache retornando `CatalogUnavailableError`;
- `get_catalog_item` sem chamada externa;
- item inexistente;
- imagem remota como fallback;
- imagem local cacheada;
- seed idempotente e offline;
- busca de catálogo exigindo leiloeiro;
- resposta 503 quando o catálogo está indisponível;
- detalhe de item para leiloeiro e 404 para inexistente.

### Modelo de lote

- `minimum_bid` sem e com lances;
- `has_bids`, `is_cancelled` e `is_settled`;
- status `scheduled`, `live`, `ended` e `cancelled`;
- precedência de cancelamento e liquidação;
- constraints de datas, valores, líder e `state_version`;
- código com 12 caracteres e unicidade;
- imutabilidade de `CatalogItem`;
- snapshot do item preservado no lote.

### API de lotes

- criação por leiloeiro com snapshot completo;
- licitante não cria;
- anônimo não cria;
- vendedor de terceiro no payload é ignorado;
- `starts_at >= ends_at` rejeitado;
- `ends_at` no passado rejeitado;
- `starting_bid` e `min_increment` inválidos rejeitados;
- vitrine pública sem login;
- exclusão de cancelados;
- filtros `live`, `scheduled`, `ended` e categoria;
- busca por título, descrição e categoria;
- ordenação por fim, preço e criação;
- paginação;
- detalhe público com todos os campos contratuais;
- `minimum_bid` após lance;
- lote inexistente;
- cancelamento pelo dono;
- `state_version` incrementado;
- lote cancelado desaparece da vitrine;
- cancelamento com lances retorna `LOT_HAS_BIDS`;
- cancelamento por outro leiloeiro retorna `LOT_NOT_OWNED`;
- cancelamento após `ends_at` retorna `LOT_ENDED`;
- cancelamento repetido retorna `LOT_CANCELLED`;
- lote inexistente no cancelamento retorna `LOT_NOT_FOUND`.

Resultado final:

```text
97 passed
```

A suíte foi executada contra o PostgreSQL local (`auction_system_db`), que é o
banco exigido para validar constraints e comportamento de concorrência nas
próximas fases.

---

## 12. Qualidade e validação

Comandos executados:

```sh
cd backend

uv run ruff check .
uv run ruff format --check .
uv run mypy .
uv run python manage.py check
uv run python manage.py makemigrations --check --dry-run
uv run pytest
```

Resultados:

| Comando | Resultado |
|---|---|
| `ruff check .` | All checks passed |
| `ruff format --check .` | 61 files already formatted |
| `mypy .` | Success, 54 source files |
| `pytest` | 97 passed |
| `manage.py check` | No issues |
| `makemigrations --check` | No changes detected |
| `migrate` | `auctions.0001_initial` aplicada |

Regras de estilo seguidas:

- sem `# noqa`;
- sem `# type: ignore`;
- sem `Any`, `Unknown` ou `object` como atalho de tipo;
- tuplas em campos de admin, serializers e coleções que aceitam sequência;
- `JsonValue` recursivo e preciso para payloads JSON;
- `TypedDict` + `Unpack` em `create_lot` para evitar supressão de `PLR0913`;
- anotações completas e `from __future__ import annotations`.

### Smoke test local

Além dos testes automatizados, foi validado com o servidor local:

```text
GET /health/                              200
POST /api/auth/token/                     200
GET /api/lots                             200, 1 lote ao vivo
GET /api/catalog/search?q=monet           503 quando a AIC estava indisponível
GET /api/catalog/search?q=Gothic          200 com from_cache=true
```

Isso confirmou que a indisponibilidade da AIC não derruba a vitrine e que o
fallback para o banco funciona.

---

## 13. Como executar

```sh
cd backend
cp .env.example .env
# editar credenciais do banco
uv sync
uv run python manage.py migrate
uv run python manage.py seed_demo
uv run uvicorn core.asgi:application --reload --port 8001
```

Health check:

```sh
curl http://localhost:8001/health/
```

Login do leiloeiro de demonstração:

```sh
curl -i -c cookies.txt \
  -H 'Content-Type: application/json' \
  -d '{"email":"leiloeiro@demo.com","password":"demo-password-123"}' \
  http://localhost:8001/api/auth/token/
```

Vitrine:

```sh
curl -s http://localhost:8001/api/lots | jq
```

Detalhe:

```sh
LOT_ID=$(curl -s http://localhost:8001/api/lots | jq -r '.results[0].id')
curl -s http://localhost:8001/api/lots/$LOT_ID | jq
```

Busca de catálogo com fallback local:

```sh
curl -s -b cookies.txt \
  'http://localhost:8001/api/catalog/search?q=Gothic&limit=5' | jq
```

Criação de lote:

```sh
ITEM_ID=$(curl -s -b cookies.txt \
  'http://localhost:8001/api/catalog/search?q=Gothic&limit=5' \
  | jq -r '.results[0].id')

STARTS_AT=$(date -u -d '+1 hour' +%Y-%m-%dT%H:%M:%SZ)
ENDS_AT=$(date -u -d '+2 hours' +%Y-%m-%dT%H:%M:%SZ)

curl -i -b cookies.txt \
  -H 'Content-Type: application/json' \
  -d "{
    \"catalog_item_id\": \"$ITEM_ID\",
    \"starts_at\": \"$STARTS_AT\",
    \"ends_at\": \"$ENDS_AT\",
    \"starting_bid\": \"1000.00\",
    \"min_increment\": \"100.00\"
  }" \
  http://localhost:8001/api/lots
```

Cancelamento, usando o `id` retornado no POST de criação:

```sh
# NEW_LOT_ID é o id retornado no corpo do POST /api/lots
NEW_LOT_ID="<id-do-lote-criado>"

curl -i -b cookies.txt \
  -X POST \
  -H 'Content-Type: application/json' \
  -d '{"reason":"teste local"}' \
  http://localhost:8001/api/lots/$NEW_LOT_ID/cancel
```

Admin:

```sh
uv run python manage.py createsuperuser
```

Acesse `http://localhost:8001/admin/`.

---

## 14. Segurança e limitações conhecidas

- A vitrine e o detalhe são públicos; escrita exige autenticação de leiloeiro.
- O leiloeiro só cancela os próprios lotes.
- Não existe endpoint de edição de lote nesta fase.
- O catálogo é imutável: uma mudança na AIC não altera itens nem lotes já
  persistidos.
- A busca pode retornar 503 se a AIC falhar e não houver item em cache.
- Vitrine, detalhe e cancelamento nunca dependem da API externa.
- O circuit breaker e o cache de busca usam `LocMemCache`, coerente com o deploy
  de uma instância; múltiplos processos não compartilham esse cache.
- O download de imagem pode falhar; nesse caso o frontend usa a URL remota e
  deve ter placeholder para imagem quebrada.
- Em produção com disco efêmero, `MEDIA_ROOT` pode não persistir; a URL remota
  continua sendo o fallback.
- Nesta fase, `current_bid`, `current_winner`, liquidação, comprovante,
  auditoria e WebSocket ainda não existem.
- O frontend ainda não consome esta API; a integração visual completa está
  prevista para a Fase 7.
- O deploy precisa rodar `migrate` para aplicar `auctions.0001_initial`.

---

## 15. Próxima fase

**Plano detalhado:** [`fases/fase-3.md`](fases/fase-3.md)  
**Índice das fases:** [`fases/README.md`](fases/README.md)

A Fase 3 deve implementar:

- lances com carteira comprometida;
- hold e release;
- valor exato do próximo lance;
- anti-sniping;
- cadeia de hashes dos lances;
- idempotência de `client_bid_id`;
- `state_version` nas respostas e eventos.

Antes de iniciar a Fase 3, os serviços de hold/release e a cadeia de hashes
precisam ser implementados sobre a base criada nesta fase.
