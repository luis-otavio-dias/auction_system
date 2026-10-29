# Fase 7 — Backend, seed, carteira e deploy

**Status:** concluída  
**Data:** 2026-10-27  
**Escopo:** backend da fase 7, em complemento a
[`fase-7-frontend.md`](fase-7-frontend.md).

## Resumo

O seed offline cria o leiloeiro, dois licitantes, carteiras com depósitos, um
lote ao vivo com ao menos dois lances e holds válidos, um lote agendado e um
lote liquidado com recibo. `--new-live` cria lote adicional sem reescrever
histórico; `--reset` remove dados e lançamentos de seed e lances dos lotes
demo, mantendo depósitos não relacionados. Implementadas API de wallet,
registro público, configuração de deploy e README raiz em português.

## Arquivos e dados

- `backend/auctions/management/commands/seed_demo.py`: seed via serviços
  `create_lot`, `deposit`, `place_bid`, `settle_lot` e `release`.
- `backend/wallet/views.py`, `serializers.py`, `urls.py`: saldo privado,
  depósitos simulados e extrato.
- `backend/users/views.py`, `serializers.py`, `urls.py`: cadastro com papel,
  email, senha e alias opcional.
- `backend/.env.example`, `backend/core/settings.py`,
  `backend/docker-compose.yaml`: PostgreSQL em produção, segredos HMAC
  distintos, allowed origins, healthcheck de container e migrations no
  entrypoint.
- `README.md` raiz contém arquitetura, setup, compose, env, migrations,
  credenciais, cookies/blacklist, endpoints, regras, liquidação, auditoria,
  limites, deploy, testes e uso de IA.
- Sem migrations novas nesta etapa; models das fases 3/4 já migrados.

## Endpoints

- `GET /api/wallet`: balance, committed e available para usuário autenticado.
- `POST /api/wallet/deposits`: depósito simulado apenas para BIDDER.
- `GET /api/wallet/transactions`: extrato privado para usuário autenticado,
  inclusive leiloeiro.
- `POST /api/auth/register`: cria usuário com papel e alias opcional.
- Lista de lotes do leiloeiro e extrato de wallet são paginados; depósito
  retorna `IDEMPOTENCY_KEY_REUSED` se uma chave for repetida com valor distinto.

## Testes e comandos

- Testes de carteira HTTP verificam acesso, dinheiro string, autorização de
  papel, depósito e extrato; seed cobre idempotência, reset e `--new-live`.
- 30 testes focados de auth/seed passaram após a correção do reset.
- Fase 6: suíte completa anterior à fase 7 **144 testes passaram**; após as
  ajustes finais, a suíte completa do backend: **165 testes passaram**.
- Comandos finais executados com sucesso: `uv run ruff check .`,
  `uv run ruff format --check .`, `uv run mypy .`,
  `uv run python manage.py check`,
  `uv run python manage.py makemigrations --check --dry-run`,
  `uv run python manage.py migrate` e `uv run pytest -q`.
- Ruff verificou todos os arquivos; format check cobriu 83 arquivos; mypy
  verificou 74 arquivos-fonte. O banco PostgreSQL local estava acessível e
  `migrate` confirmou que não havia migrations pendentes.

## Limitações e decisões

Depósitos são simulados, não integram adquirente. Deploy demonstrativo supõe
uma instância/processo por causa do channel layer em memória. O `.env` existente
é preservado; como está em `DEBUG=False` e não define secrets HMAC, comandos de
qualidade neste ambiente usam dois valores temporários distintos por variável
de ambiente. O operador deve configurar segredos próprios antes do deploy.

## Ajustes finais

- A busca textual confirmou que a senha demonstrativa já documentada está
  alinhada entre seed, configuração e interface. O seed agora reaplica
  `DEMO_PASSWORD` às três contas mesmo quando já existem.
- `GET /api/wallet` e `GET /api/wallet/transactions` aceitam qualquer usuário
  autenticado; `POST /api/wallet` não existe e depósitos continuam restritos a
  BIDDER. Replay de depósito responde 200 com `Idempotent-Replayed: true`.
- Admin de `Bid` e `Receipt` é somente leitura. A suíte final
  passou com **165 testes**.
