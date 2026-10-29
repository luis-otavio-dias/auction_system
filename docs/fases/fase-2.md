# Fase 2 — Catálogo AIC e lotes

**Status:** concluída  
**Data:** 2026-10-27  
**Depende de:** Fase 1

---

## 1. Objetivo

Permitir que o leiloeiro busque um item na Art Institute of Chicago, crie um
lote a partir do snapshot desse item e que qualquer visitante veja a vitrine e
o detalhe dos lotes.

A fase termina antes de qualquer lance. Nesta etapa, `Lot.current_bid` e
`Lot.current_winner` permanecem nulos.

---

## 2. Escopo

- Model `CatalogItem` como cache imutável da API externa.
- Adapter `ArticProvider` com timeout, retry, cache e fallback.
- Model `Lot` com snapshot do item, datas, valores e estado derivado.
- Serializers, selectors, views, permissões, URLs e admin.
- Vitrine pública com filtros.
- Detalhe público do lote.
- Criação de lote pelo leiloeiro.
- Cancelamento de lote sem lances.
- Seed de itens com fixtures locais.
- Testes de catálogo, permissões, filtros, criação e cancelamento.

Fora do escopo: lances, holds, liquidação, comprovante, auditoria e WebSocket.

---

## 3. Modelos

### 3.1 `CatalogItem`

| Campo | Tipo | Observação |
|---|---|---|
| `id` | UUID | PK |
| `source` | CharField(32) | `artic` |
| `external_id` | CharField(64) | ID na AIC |
| `title` | CharField(300) | snapshot |
| `description` | TextField blank | snapshot |
| `image_url` | URLField | imagem principal |
| `thumbnail_url` | URLField blank | miniatura |
| `source_url` | URLField | página original |
| `category` | CharField(100) blank | departamento/classificação |
| `attributes` | JSONField | artista, data, técnica, procedência etc. |
| `raw_payload` | JSONField | payload original |
| `fetched_at` | DateTimeField | |
| `created_at` | DateTimeField | |

Constraints e índices:

```text
unique(source, external_id)
index(source)
index(category)
```

- Campos de exibição não são atualizados depois da criação.
- O item é um snapshot; mudança no provedor não altera lotes existentes.
- Busca pode reutilizar itens do banco quando a AIC falhar.

### 3.2 `Lot`

| Campo | Tipo | Observação |
|---|---|---|
| `id` | UUID | PK |
| `code` | CharField(12) unique | código curto |
| `seller` | FK User PROTECT | somente `SELLER` |
| `catalog_item` | FK CatalogItem PROTECT nullable | rastreabilidade |
| `title` | CharField(300) | snapshot |
| `description` | TextField blank | snapshot |
| `image_url` | URLField | imagem usada pelo frontend |
| `image_remote_url` | URLField | original |
| `image_cached` | BooleanField | imagem baixada? |
| `source` | CharField(32) | snapshot |
| `external_id` | CharField(64) | snapshot |
| `source_url` | URLField | snapshot |
| `category` | CharField(100) blank | filtro |
| `attributes` | JSONField | snapshot |
| `starting_bid` | Decimal(12,2) | > 0 |
| `min_increment` | Decimal(12,2) | > 0 |
| `current_bid` | Decimal(12,2) nullable | nulo sem lances |
| `current_winner` | FK User nullable PROTECT | nulo sem lances |
| `starts_at` | DateTimeField | |
| `ends_at` | DateTimeField | muda com anti-sniping |
| `original_ends_at` | DateTimeField | imutável |
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
| `settlement_error` | TextField blank | Fase 4 |
| `settlement_checked_at` | DateTimeField nullable | Fase 4 |
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

Status derivado, sem coluna `status`:

```text
cancelled_at preenchido -> cancelled
settled_at preenchido   -> ended
now < starts_at         -> scheduled
now < ends_at           -> live
caso contrário          -> ended
```

- A vitrine nunca mostra cancelados.
- `state_version` incrementa a cada mutação relevante.
- `settlement_error` e `settlement_checked_at` são internos e não aparecem em
  serializers públicos.

---

## 4. Integração com a AIC

Adapter `auctions/services/catalog.py`:

```text
ArticProvider.search(query, limit) -> list[ExternalItem]
ArticProvider.get_item(external_id) -> ExternalItem
```

Endpoints externos de referência:

```text
https://api.artic.edu/api/v1/artworks/search
https://api.artic.edu/api/v1/artworks/{id}
https://www.artic.edu/iiif/2/{image_id}/full/843,/0/default.jpg
```

Regras:

- `httpx.Client` com timeout de 5 s.
- User-Agent identificando a aplicação.
- Até 2 tentativas com backoff curto.
- Circuit breaker em cache local.
- Normalização para `CatalogItem`.
- Criar lote só aceita `catalog_item_id` já persistido.
- Vitrine, detalhe e cancelamento nunca chamam a API externa.
- Se a busca falhar:
  - procurar itens em cache no banco;
  - se não houver, retornar 503 com mensagem clara.
- Imagem:
  - tentar baixar para `MEDIA_ROOT/lots/`;
  - se falhar, manter `image_remote_url`;
  - `image_cached` indica o estado.
- Seed usa fixtures locais para não depender da AIC.

---

## 5. API

Prefixo: `/api`.

### Catálogo

| Método | Rota | Acesso | Função |
|---|---|---|---|
| GET | `/api/catalog/search?q=` | leiloeiro | busca AIC com cache |
| GET | `/api/catalog/items/{id}` | leiloeiro | item em cache |

### Lotes

| Método | Rota | Acesso | Função |
|---|---|---|---|
| GET | `/api/lots` | público | vitrine com filtros |
| GET | `/api/lots/{id}` | público | detalhe |
| POST | `/api/lots` | leiloeiro | criar lote |
| POST | `/api/lots/{id}/cancel` | leiloeiro dono | cancelar sem lances |

Filtros:

```text
tab=live|scheduled|ended
q=<texto>
category=<categoria>
sort=ending|price-high|price-low|recent
```

Resposta de detalhe deve incluir:

- `id`, `code`, `status`, `title`, `description`, `image_url`;
- `starting_bid`, `min_increment`, `current_bid`;
- `minimum_bid` (calculado);
- `starts_at`, `ends_at`, `server_time`;
- `bids_count`, `state_version`;
- `seller_alias`;
- `my_position` quando autenticado (nulo nesta fase).

Permissões:

- Público: vitrine e detalhe.
- Leiloeiro: busca, criação e cancelamento dos próprios lotes.
- Licitante não cria lote.
- Leiloeiro não pode cancelar lote com lances (`LOT_HAS_BIDS`).
- Cancelamento só antes de `ends_at`.

---

## 6. Regras de criação

- O leiloeiro escolhe um `CatalogItem` persistido.
- `starts_at < ends_at`; `ends_at` deve estar no futuro.
- `starting_bid > 0`; `min_increment > 0`.
- Se `starts_at <= now < ends_at`, o lote já nasce `live`.
- Se `starts_at > now`, nasce `scheduled`.
- `title`, `description`, imagem e atributos são copiados do item.
- `current_bid` e `current_winner` começam nulos.
- `original_ends_at = ends_at` na criação.
- `state_version = 1`.
- O lote não é editável depois de criado; nesta fase só pode ser cancelado.

---

## 7. Admin e migrations

- Registrar `CatalogItem` e `Lot` no Django Admin.
- `CatalogItem` somente leitura.
- `Lot` com status derivado, contagem de lances, vendedor e datas.
- Criar migration `auctions/0001_initial.py`.
- Rodar `migrate`.
- Atualizar `known-first-party` se necessário.

---

## 8. Seed

Criar itens de fixture local com:

- título, descrição, imagem, categoria e atributos;
- `source=artic` e `external_id` fictício ou real;
- pelo menos 3 itens para permitir montar lotes.

O seed de lotes completo será concluído na Fase 7; nesta fase, criar pelo menos
um lote agendado ou ao vivo para validar a vitrine.

---

## 9. Testes

### Catálogo

- busca com sucesso na AIC;
- timeout e erro 5xx;
- fallback para cache;
- normalização de payload;
- imagem remota como fallback.

### Lotes

- criação por leiloeiro;
- licitante não cria;
- leiloeiro não cria lote para outro usuário;
- `starts_at >= ends_at` rejeitado;
- `starting_bid`/`min_increment` inválidos rejeitados;
- snapshot do item imutável;
- vitrine exclui cancelados;
- filtros `live`, `scheduled`, `ended`, categoria, busca e ordenação;
- detalhe público sem autenticação;
- cancelamento sem lances;
- cancelamento com lances retorna `LOT_HAS_BIDS`;
- cancelamento por outro leiloeiro retorna 403;
- `state_version` e `server_time` presentes.

---

## 10. Critérios de aceite

- [x] Leiloeiro busca item na AIC e vê resultados.
- [x] Leiloeiro cria lote a partir de um item em cache.
- [x] Lote aparece na vitrine com o status correto.
- [x] Licitante não consegue criar lote.
- [x] Lote sem lances pode ser cancelado pelo dono e desaparece da vitrine.
- [x] API externa indisponível não derruba vitrine/detalhe.
- [x] Migrations aplicadas e testes verdes.

---

## 11. Riscos

| Risco | Mitigação |
|---|---|
| AIC lenta/instável | timeout, retry, circuit breaker e cache |
| Imagem remota quebrada | download local + fallback remoto + placeholder |
| Datas inconsistentes | validação no serializer e constraint no banco |
| Status divergente | status derivado de timestamps |
| Lote editado após criação | não expor endpoint de edição |
| Cache desatualizado | snapshot imutável e `fetched_at` |

---

## 12. Checklist de implementação

- [x] Criar `CatalogItem` e migration.
- [x] Criar `ArticProvider` e cache.
- [x] Criar `Lot` e migration.
- [x] Criar serializers, selectors, permissions e views.
- [x] Criar rotas em `auctions/urls.py` e incluir no `core/urls.py`.
- [x] Registrar admin.
- [x] Criar fixtures de catálogo.
- [x] Escrever testes.
- [x] Rodar `ruff`, `mypy`, `pytest`, `check` e `makemigrations --check`.

---

## 13. Registro de implementação

### Entregue

- `CatalogItem` imutável com unique `(source, external_id)` e índices de
  `source` e `category`.
- `Lot` com snapshot do catálogo, constraints de datas/valores/estado,
  status derivado, `state_version` e campos das fases seguintes.
- `ArticProvider` com timeout de 5 s, User-Agent, duas tentativas, backoff,
  circuit breaker em cache, normalização, cache de busca e fallback para o
  banco.
- Download de imagem para `MEDIA_ROOT/lots/` com fallback para a URL remota e
  `image_cached` indicando o resultado.
- Serializers, selectors, permissões, views e rotas de catálogo e lotes.
- Vitrine pública com `tab`, `q`, `category`, `sort` e paginação.
- Criação de lote por leiloeiro e cancelamento pelo dono sem lances.
- Admin somente leitura para catálogo e lotes.
- Migration `auctions/0001_initial.py`.
- Fixtures locais e comando `seed_demo` idempotente, sem acesso à rede.

### Decisões

- O cancelamento repetido retorna `LOT_CANCELLED` (409) em vez de ser
  idempotente; o frontend deve tratar o lote já cancelado.
- `my_position` é sempre `null` nesta fase, como previsto.
- `server_time` é gerado no serializer com o mesmo instante usado no status.
- O detalhe público continua acessível para lote cancelado; a vitrine nunca o
  lista.
- `CatalogItem.save()` bloqueia alterações depois da criação; o admin também é
  somente leitura.
- `MEDIA_URL` passou a ter barra inicial (`/media/`) e o `core/urls.py` serve
  mídia local em desenvolvimento.

### Validação

```text
ruff check .                  All checks passed
ruff format --check .         61 files already formatted
mypy .                        Success, 54 source files
python manage.py check        No issues
makemigrations --check        No changes detected
pytest                        95 passed
migrate                       auctions.0001_initial aplicada
```

### Limitações

- A busca usa cache de resposta e snapshots imutáveis; itens já persistidos não
  são atualizados a partir da AIC.
- O circuit breaker é local ao processo (`LocMemCache`), coerente com o deploy
  de uma instância.
- A imagem remota é o fallback quando o download falha; o frontend deve manter
  placeholder para URLs quebradas.
