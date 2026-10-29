# Fase 1 — Fundação do backend

**Status:** concluída  
**Data:** 2026-10-27  
**Depende de:** nenhuma fase anterior  
**Relatório de entrega:** [`../implemented/fase-1.md`](../implemented/fase-1.md)

---

## 1. Objetivo

Estabelecer a base de usuários, autenticação e carteira para as regras do
leilão. Um usuário criado pelo manager ou admin deve conseguir entrar,
consultar a própria conta e possuir uma carteira inicial com saldo zero.

Este documento organiza o escopo e os critérios da fase a partir do relatório
de entrega. O cadastro público e os endpoints de carteira pertencem a etapas
posteriores.

---

## 2. Escopo

- Apps `users`, `wallet` e esqueleto de `auctions`.
- Usuário customizado, manager, formulários e administração.
- Carteira automática e livro-razão de movimentações.
- Serviço transacional de depósito com idempotência.
- Login JWT em cookies HttpOnly, refresh com rotação e logout.
- Settings de Django, DRF, CORS, Channels, mídia e variáveis de ambiente.
- Migrations, testes e documentação de execução.

Fora do escopo: catálogo externo, lotes, lances, holds/releases, liquidação,
comprovantes, auditoria pública, consumers WebSocket e frontend.

---

## 3. Modelos

### 3.1 `User`

Baseado em `AbstractBaseUser` e `PermissionsMixin`:

| Campo | Regra |
| --- | --- |
| `id` | UUID como chave primária |
| `email` | Único, normalizado para minúsculas e usado como login |
| `role` | `SELLER` ou `BIDDER` |
| `public_alias` | Único, gerado com prefixo por papel e sufixo aleatório |
| `full_name` | Opcional e privado |
| `is_active`, `is_staff`, `is_superuser` | Controle de conta e administração |
| `date_joined`, `last_login` | Datas de cadastro e último login |

- `UserManager` oferece `create_user` e `create_superuser`, usando
  `set_password` para armazenar o hash da senha.
- Aliases seguem `Leiloeiro-XXXXXX` e `Licitante-XXXXXX`, com seis caracteres
  hexadecimais maiúsculos no sufixo e constraint de unicidade no banco.
- Definir `AUTH_USER_MODEL` antes das migrations de domínio.

### 3.2 `Wallet`

- UUID e relação um-para-um com `User`, protegida por `PROTECT`.
- `balance` e `committed` em `Decimal(12,2)`, iniciados em zero.
- `available = balance - committed`.
- Constraints: `balance >= 0`, `committed >= 0` e `committed <= balance`.
- Signal de `post_save` cria a carteira para qualquer papel, inclusive leiloeiro.

### 3.3 `WalletTransaction`

Livro-razão append-only com carteira, tipo, valor positivo, snapshots de saldo
total e comprometido, referência, chave de idempotência e data de criação.

- Tipos previstos: depósito, hold, liberação, débito/crédito de liquidação,
  liberação por cancelamento e ajustes de crédito/débito.
- Nesta fase, o serviço implementado movimenta apenas depósitos.
- Constraint `amount > 0` e unicidade de `(wallet, idempotency_key)` quando a
  chave não é nula.
- Índices por carteira/data e por referência.
- `signed_amount` expressa a direção; holds e liberações alteram apenas o
  comprometido.

---

## 4. Autenticação e API

| Método | Rota | Acesso | Função |
| --- | --- | --- | --- |
| POST | `/api/auth/token/` | Público | Validar credenciais e gravar cookies |
| POST | `/api/auth/refresh/` | Cookie de refresh | Renovar access e rotacionar refresh |
| POST | `/api/auth/token/refresh/` | Cookie de refresh | Alias de compatibilidade |
| POST | `/api/auth/logout/` | Público | Revogar refresh e limpar cookies |
| GET | `/api/auth/me/` | Autenticado | Consultar os dados da própria conta |

- Access de 15 minutos e refresh de sete dias.
- Tokens enviados em `Set-Cookie`, sem exposição no corpo das respostas.
- Cookies HttpOnly: `access_token` com path `/` e `refresh_token` com path
  `/api/auth/`.
- `CookieJWTAuthentication` usa o access cookie e aceita Bearer quando ele
  está ausente. Cookie presente e inválido não permite fallback para o header.
- Refresh rotacionado entra na blacklist e não pode ser reutilizado.
- Logout revoga o refresh atual; o access permanece válido até expirar.
- Ausência de credenciais ou token inválido resulta em `401` nas rotas privadas.

---

## 5. Serviço de depósito

Contrato em `wallet/services.py`:

```text
deposit(wallet_id, amount, idempotency_key=None, description="")
    -> WalletTransaction
```

1. Validar valor positivo e finito.
2. Abrir transação atômica e bloquear a carteira com `select_for_update()`.
3. Consultar a chave de idempotência depois do lock.
4. Devolver o lançamento original quando chave e valor coincidirem.
5. Rejeitar a mesma chave com outro valor com `IdempotencyConflictError`.
6. Atualizar saldo e gravar o lançamento com snapshots na mesma transação.

O depósito é um serviço interno nesta fase; ainda não há endpoint HTTP para ele.

---

## 6. Configuração, admin e migrations

- Registrar os apps e `rest_framework_simplejwt.token_blacklist`.
- Configurar autenticação por cookie, paginação DRF e CORS com credenciais.
- Preparar ASGI e `InMemoryChannelLayer`, sem consumers nesta etapa.
- Usar UTC, locale `pt-br` e configurar diretórios de mídia.
- Documentar cookies, origens e demais variáveis em `.env.example`.
- Registrar `UserAdmin` customizado; carteiras e lançamentos ficam somente
  leitura no admin.
- Criar `users/0001_initial.py` e `wallet/0001_initial.py`.
- Aplicar migrations do projeto e da blacklist.

`AUTH_COOKIE_SECURE` e `AUTH_COOKIE_SAMESITE` devem corresponder ao ambiente.
As instruções atuais de produção estão no
[guia do backend](../../backend/README.md#verificar-autenticação-no-navegador).

---

## 7. Testes

| Área | Cobertura esperada |
| --- | --- |
| Usuário | Normalização de e-mail, papéis, aliases únicos e superusuário |
| Login | Cookies HttpOnly, paths, validade e atributos configurados |
| Conta atual | Cookie, fallback Bearer e rejeição de credenciais inválidas |
| Refresh | Rotação, blacklist e rejeição de refresh ausente/inválido |
| Logout | Limpeza dos cookies e revogação do refresh |
| Carteira | Criação automática, saldo zero, disponível e constraints |
| Depósito | Saldo, lançamento, descrição, replay e conflito de idempotência |
| Valores inválidos | Depósitos zero e negativos rejeitados |

Usar PostgreSQL para validar o comportamento de banco e os locks. A suíte da
fase está registrada no relatório; os testes atuais incluem as fases seguintes.

---

## 8. Critérios de aceite

- [x] Usuário criado com e-mail normalizado, papel e alias único.
- [x] Carteira criada automaticamente com saldo total e comprometido em zero.
- [x] Login entrega cookies HttpOnly e permite consultar `/api/auth/me/`.
- [x] Refresh rotaciona os tokens e invalida o refresh anterior.
- [x] Logout limpa os cookies e revoga o refresh atual.
- [x] Depósito grava saldo e livro-razão atomicamente, sem duplicar em replay.
- [x] Constraints de saldo e idempotência presentes nas migrations.
- [x] Admin, settings e variáveis de ambiente documentados.
- [x] Migrations aplicadas e verificações de qualidade registradas.

---

## 9. Riscos e limitações

| Risco | Tratamento |
| --- | --- |
| Trocar usuário customizado após criar o banco | Definir `AUTH_USER_MODEL` antes das migrations de domínio |
| Depósito duplicado | Lock, chave de idempotência e constraint única |
| Saldo inconsistente | `Decimal`, transação atômica e constraints |
| Exposição de dados pessoais | Separar dados privados da conta e aliases públicos |
| Cookies incompatíveis com o deploy | Conferir atributos e configuração efetiva no runtime |
| Access válido após logout | Validade curta; blacklist cobre apenas refresh |
| Eventos entre vários processos | Camada em memória restrita a uma instância/processo |

---

## 10. Checklist de implementação

- [x] Criar apps, modelos, manager e signal de carteira.
- [x] Implementar autenticação por cookies e endpoints de sessão.
- [x] Implementar serviço de depósito idempotente.
- [x] Configurar Django, DRF, JWT, CORS e Channels.
- [x] Registrar admin e criar migrations.
- [x] Escrever testes de usuários, cookies, carteira e depósito.
- [x] Executar Ruff, mypy, pytest, Django checks e verificação de migrations.
- [x] Registrar entrega em [`../implemented/fase-1.md`](../implemented/fase-1.md).

## 11. Registro de implementação

O [relatório da fase 1](../implemented/fase-1.md) registra a estrutura criada,
os contratos e os resultados da validação de 2026-10-27: 32 testes passando,
Ruff e mypy aprovados, Django sem problemas e nenhuma migration pendente de
geração. Esses resultados pertencem à entrega original.

Próxima etapa: [Fase 2 — Catálogo AIC e lotes](fase-2.md).
