# Frontend — Plataforma de leilões

SPA em React 19 + TypeScript + Vite que consome a API real do leilão. Inclui
vitrine, sala de lances em tempo real, carteira, painel do leiloeiro, meus
arremates, auditoria pública, comprovante compartilhável, autenticação e tema
claro/escuro.

- **Aplicação publicada:** https://auction-system-neon.vercel.app
- **API consumida:** https://api--auction-system-backend--cg7yjzmmcfrl.code.run
- **Documentação completa do projeto:** [`../README.md`](../README.md)

## O que está pronto

| Requisito | Tela |
| --- | --- |
| Vitrine, busca e filtros | `/` — ao vivo, agendados e encerrados |
| Criar e gerenciar lotes | `/painel` — busca AIC, criação, cancelamento e resultados |
| Lances ao vivo | `/lotes/:id` — posição, histórico, countdown e feedback |
| Carteira do licitante | `/carteira` — depósito, saldos e extrato |
| Participações e arremates | `/meus-arremates` — lotes disputados e comprovantes |
| Auditoria pública | `/lotes/:id/auditoria` |
| Comprovante compartilhável | `/comprovantes/:token` |
| Cadastro e login | `/cadastro` e `/login`, com dois papéis |

Também inclui tema claro/escuro com preferência persistida.

## Stack

| Camada | Tecnologia |
|---|---|
| UI | React 19 + TypeScript estrito |
| Build | Vite 8 |
| Rotas | React Router 7 |
| Estilos | Tailwind CSS 4 + tokens semânticos em `src/index.css` |
| Testes | Vitest + Testing Library |
| E2E | Script Node sem dependências novas, contra a API real |

## Como rodar

Requisitos: Node.js 24+ e npm. O backend precisa estar em execução e com o seed
aplicado; siga o [guia do backend](../backend/README.md#subir-com-docker-recomendado).
Os comandos abaixo são executados dentro de `frontend/`.

```sh
npm ci
npm run dev
```

Sem configuração adicional, o cliente usa `http://localhost:8001`.
Para outra API, crie `frontend/.env.local` (o arquivo não deve ser versionado):

```env
VITE_API_URL=http://localhost:8001
```

`VITE_API_URL` deve apontar para a **origem** do backend:

- inclua o protocolo (`http://` ou `https://`);
- não inclua `/api` no final — o cliente já monta `/api/...`;
- o padrão é `http://localhost:8001`.

A autenticação usa cookies HttpOnly, então todas as requisições são feitas com
`credentials: "include"`. O backend precisa liberar a origem do frontend em
`CORS_ALLOWED_ORIGINS` e, para WebSocket, em `WS_ALLOWED_ORIGINS`.

## Publicar na Vercel

Configure o projeto com:

| Campo | Valor |
| --- | --- |
| Root Directory | `frontend` |
| Framework | Vite |
| Build Command | `npm run build` |
| Output Directory | `dist` |
| Variável `VITE_API_URL` | `https://api--auction-system-backend--cg7yjzmmcfrl.code.run` |

Informe a URL completa com `https://` e sem `/api` no final. O cliente usa o
valor configurado; não acrescenta protocolo automaticamente.

**Vite lê `VITE_*` durante o build.** Alterar a variável exige um novo deploy.
Configure-a para o ambiente usado (Production ou Preview).

No backend, libere a origem do frontend em `CORS_ALLOWED_ORIGINS` e
`WS_ALLOWED_ORIGINS`. O endereço estável é
`https://auction-system-neon.vercel.app`; previews têm origens diferentes e
precisam ser cadastrados separadamente.

O roteamento usa `BrowserRouter`. O arquivo [`vercel.json`](vercel.json) inclui o
rewrite de SPA que entrega `index.html` ao abrir ou atualizar diretamente rotas
como `/login`, `/carteira`, `/lotes/:id`, `/lotes/:id/auditoria` e
`/comprovantes/:token`; assets de `/assets/` continuam sendo servidos pelo
próprio arquivo estático. Mantenha esse arquivo na raiz do projeto configurado
na Vercel (Root Directory `frontend`) e valide os deep links após cada deploy.

A configuração dos cookies e a verificação de sessão estão no
[guia de autenticação do deploy](../backend/README.md#verificar-autenticação-no-navegador).

## Scripts

```sh
npm run dev         # servidor de desenvolvimento
npm run build       # typecheck + build de produção
npm run preview     # prévia do build
npm run lint        # ESLint
npm run test:run     # testes unitários
npm run test:coverage
```

A suíte unitária contém 36 testes em 12 arquivos.

Smoke E2E real, usando o backend em execução com um banco de desenvolvimento:

```sh
E2E_API_URL=http://127.0.0.1:8001 npm run test:e2e
```

O script usa apenas APIs públicas, autentica as três contas do seed e cobre
lances idempotentes, anti-sniping, liquidação, comprovante, auditoria, snapshot
do WebSocket, carteira/extrato do leiloeiro, estabilidade do `server_time`,
resultado por lote e notificações com `lot_id`. O `Origin` do WebSocket deve
estar em `WS_ALLOWED_ORIGINS`; o padrão é `http://localhost:5173` e pode ser
alterado com `E2E_WS_ORIGIN`.

## Rotas

| Rota | Função |
|---|---|
| `/` | Vitrine com abas ao vivo, programados e resultados |
| `/lotes/:id` | Sala do lote: lance, posição, histórico e countdown |
| `/lotes/:id/auditoria` | Auditoria pública da cadeia de lances |
| `/comprovantes/:token` | Comprovante público e link compartilhável |
| `/carteira` | Saldo, comprometido, disponível, depósito e extrato |
| `/painel` | Painel do leiloeiro: busca AIC, criação e resultados |
| `/meus-arremates` | Lotes arrematados, participação e comprovantes |
| `/login` | Login por e-mail e senha |
| `/cadastro` | Cadastro público com escolha de papel |
| `*` | Página 404 |

## Autenticação

O frontend nunca lê access ou refresh tokens. `POST /api/auth/token/` grava os
cookies HttpOnly; em `401` o cliente tenta `POST /api/auth/refresh/` uma única
vez e repete a requisição original. Falha do refresh limpa o estado local e
redireciona o usuário para o login quando necessário.

O backend expõe `POST /api/auth/register`; a tela cria a conta e faz login em
seguida. As contas de demonstração são:

```text
cliente1@demo.com  / demo-password-123
cliente2@demo.com  / demo-password-123
leiloeiro@demo.com / demo-password-123
```

## Sala do lote e tempo real

A sala abre `POST /api/auth/ws-ticket` e conecta em
`/ws/lots/{id}/?ticket=...`. O header conecta em
`/ws/notifications/?ticket=...`. Ambos renovam o ticket em fechamentos `4401`,
aplicam backoff exponencial e reconectam. A sala mantém polling de
`GET /api/lots/{id}` a cada 4 segundos como fallback.

O estado usa `state_version` por lote: versões menores são descartadas, eventos
exigem versão maior e o snapshot do WebSocket pode atualizar `my_position` na
mesma versão; saltos disparam uma busca de snapshot. O cenário de um evento novo
chegar antes de uma resposta HTTP antiga é coberto pelo guard de versão e pelos
testes.

O countdown usa o `server_time` de cada resposta para recalcular o offset do
relógio local, sem deriva regressiva.

## Feedback de lance

Todos os códigos de erro da API têm mensagem dedicada em
`src/domain/bidErrors.ts`:

`LOT_NOT_STARTED`, `LOT_ENDED`, `LOT_CANCELLED`, `LOT_SETTLED`,
`BID_AMOUNT_MISMATCH`, `BID_BELOW_MINIMUM`, `ALREADY_LEADING`,
`INSUFFICIENT_FUNDS`, `SELLER_CANNOT_BID`, `FORBIDDEN_ROLE` e
`IDEMPOTENCY_KEY_REUSED`.

O identificador `client_bid_id` é gerado antes do request e mantido em falhas de
rede ou `5xx`, permitindo retry idempotente; ele é descartado em rejeições
`4xx` e após sucesso.

## Tema claro e escuro

O cabeçalho tem um botão para alternar entre os temas. A escolha é salva em
`localStorage` na chave `auction-theme` e passa a vencer a preferência do
sistema. Na primeira visita, o tema segue `prefers-color-scheme`; enquanto não
houver escolha salva, mudanças no sistema são aplicadas em tempo real.

Um script em `index.html` aplica o tema antes do primeiro paint para evitar
flash. As cores ficam em tokens semânticos em `src/index.css`, com a paleta
escura definida em `:root[data-theme="dark"]`. Em telas pequenas, o controle
passa para o menu de navegação.

## Estrutura

```text
src/
├── api/          # cliente HTTP, refresh, decoders e serviços tipados
├── components/   # layout, UI compartilhada e catálogo
├── context/      # sessão, tema, notificações e toasts
├── domain/       # state_version, erros de lance e regras de estado
├── hooks/        # countdown e sala do lote
├── pages/        # rotas da aplicação
├── test/         # mocks de fetch/WebSocket e fixtures
├── types/        # contratos da API
├── utils/        # formatação, erros e identificadores
├── App.tsx       # rotas e providers
├── main.tsx      # inicialização
└── index.css     # estilos globais e tokens de tema
```

## Limitações conhecidas

- O WebSocket usa uma única instância do backend; eventos transitórios podem se
  perder e o polling recupera o estado.
- Imagens remotas que falham usam placeholder; imagens cacheadas em
  `MEDIA_ROOT` exigem disco persistente no deploy.
- O seed cria o lote ao vivo com três dias de duração; depois disso, use
  `seed_demo --new-live` ou crie um lote pelo painel.
- Não há upload de imagem personalizada: o catálogo vem da Art Institute of
  Chicago.
- Recuperação de senha e verificação de e-mail estão fora do escopo do desafio.

As limitações de auditoria e liquidação estão na
[visão geral](../README.md#limitações-e-comportamentos-conhecidos).
