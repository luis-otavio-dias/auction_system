# Plataforma de leilões — frontend

Aplicação React + TypeScript + Vite que consome a API real do leilão. Inclui
vitrine, sala de lances em tempo real, carteira, painel do leiloeiro, meus
arremates, auditoria pública e comprovante compartilhável.

## Executar

```sh
npm install
npm run dev
```

Variáveis:

```env
VITE_API_URL=http://localhost:8001
```

`VITE_API_URL` deve apontar para a origem do backend, sem `/api` no final. O
padrão é `http://localhost:8001`. A autenticação usa cookies HttpOnly, então as
requisições são feitas com `credentials: "include"` e o backend precisa liberar
a origem do frontend em CORS.

## Scripts

```sh
npm run lint
npm run build
npm run test:run
```

Smoke E2E real (Node 24, sem dependências novas), usando o backend em execução:

```sh
E2E_API_URL=http://127.0.0.1:8002 npm run test:e2e
```

O script usa apenas APIs públicas, autentica os três usuários do seed sem
fallback de cadastro, cobre lances idempotentes, anti-sniping, liquidação,
comprovante, auditoria, snapshot do WebSocket, carteira/extrato do leiloeiro,
estabilidade do `server_time`, resultado por lote e notificações com `lot_id`. O `Origin` do WebSocket deve estar em
`WS_ALLOWED_ORIGINS`; o padrão do script é `http://localhost:5173` e pode ser
alterado com `E2E_WS_ORIGIN`.

## Rotas

| Rota | Função |
|---|---|
| `/` | Vitrine com abas ao vivo, programados e resultados |
| `/lotes/:id` | Sala do lote: lance, posição, histórico, countdown |
| `/lotes/:id/auditoria` | Auditoria pública da cadeia de lances |
| `/comprovantes/:token` | Comprovante público e link compartilhável |
| `/carteira` | Saldo, comprometido, disponível, depósito e extrato |
| `/painel` | Painel do leiloeiro (busca AIC, criação e resultados) |
| `/meus-arremates` | Lotes arrematados e comprovantes |
| `/login` | Login por e-mail e senha |
| `/cadastro` | Cadastro público quando o backend oferece o endpoint |

## Autenticação

O frontend nunca lê access ou refresh tokens. `POST /api/auth/token/` grava os
cookies HttpOnly; em `401` o cliente tenta `POST /api/auth/refresh/` uma única
vez e repete a requisição original. Falha do refresh limpa o estado local e
redireciona o usuário para o login quando necessário.

O backend expõe `POST /api/auth/register`; a tela cria a conta e faz login em
seguida. Se o endpoint não existir em outro ambiente, a tela exibe a limitação e
orienta o uso do seed:

```text
cliente1@demo.com / demo-password-123
cliente2@demo.com / demo-password-123
leiloeiro@demo.com / demo-password-123
```

## Tempo real

A sala abre `POST /api/auth/ws-ticket` e conecta em
`/ws/lots/{id}/?ticket=...`. O header conecta em `/ws/notifications/?ticket=...`.
Ambos renovam o ticket em fechamentos `4401`, aplicam backoff exponencial e
reconectam. A sala mantém polling de `GET /api/lots/{id}` a cada 4 segundos como
fallback.

O estado usa `state_version` por lote: versões menores são descartadas, eventos
exigem versão maior e o snapshot do WebSocket pode atualizar `my_position` na
mesma versão; saltos disparam uma busca de snapshot. O cenário de um evento novo
chegar antes de uma resposta HTTP antiga é coberto pelo guard de versão e pelos
testes.

## Estrutura

```text
src/
├── api/          # cliente HTTP, decoders e serviços tipados
├── components/   # layout, UI compartilhada e catálogo
├── context/      # sessão, notificações e toasts
├── domain/       # state_version e mensagens de erro de lance
├── hooks/        # countdown e sala do lote
├── pages/        # rotas da aplicação
├── test/         # mocks de fetch/WebSocket e fixtures
├── types/        # contratos da API
├── utils/        # formatação, erros e identificadores
├── App.tsx       # rotas e providers
├── main.tsx      # inicialização
└── index.css     # estilos globais
```

O catálogo estático legado (`Home`, `LotCard`, `BidModal`, `auctionService` e
`lots.json`) foi removido por não ser mais referenciado pela aplicação
integrada. Nenhum componente da interface lê credenciais de cookie.

A carteira do leiloeiro consulta `GET /api/wallet` e
`GET /api/wallet/transactions`; se o extrato responder `403` em um backend
antigo, a página mantém o saldo e o bloco de orientação em vez de falhar. O
painel consome `results_by_lot`, `unsold_lots` e `blocked_lots` de
`GET /api/seller/summary`.
