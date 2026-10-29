# Casa de Leilões — Auction System

Plataforma de leilões ao vivo para o **Desafio Elite Dev — Verzel**. O leiloeiro
monta lotes a partir de obras da Art Institute of Chicago; o licitante deposita
saldo simulado, disputa lotes em tempo real e recebe um comprovante público
quando arremata. Qualquer pessoa pode auditar o histórico de lances sem login.

**Stack:** React 19 + TypeScript + Vite · Django 6.1 + DRF + Channels ·
PostgreSQL · WebSocket + polling · HMAC-SHA256.

## Aplicação publicada

| Recurso | Endereço |
|---|---|
| Aplicação | https://auction-system-neon.vercel.app |
| API | https://api--auction-system-backend--cg7yjzmmcfrl.code.run/api |
| Health check | https://api--auction-system-backend--cg7yjzmmcfrl.code.run/health/ |
| Repositório | https://github.com/luis-otavio-dias/auction_system |

## Como testar

1. Abra https://auction-system-neon.vercel.app.
2. Entre como `cliente1@demo.com` / `demo-password-123`.
3. Abra o lote **ao vivo** na vitrine e dê o lance exato exibido em
   “Próximo lance exato”.
4. Em uma janela anônima, entre como `cliente2@demo.com` e cubra o lance com o
   próximo incremento. A primeira janela deve mostrar **“Você foi superado”**
   sem recarregar a página.
5. Confira a **carteira** (saldo total, comprometido e disponível), o
   **histórico público**, a **auditoria** do lote e, em **Meus arremates** do
   `cliente2`, o comprovante do lote encerrado que já vem no seed.
6. Saia e entre como `leiloeiro@demo.com` para abrir o **painel do leiloeiro**:
   buscar na AIC, criar um lote, cancelar um lote sem lances e ver o total
   recebido e o resultado por lote.

### Contas de demonstração

| Papel | E-mail | Senha |
|---|---|---|
| Leiloeiro | `leiloeiro@demo.com` | `demo-password-123` |
| Licitante | `cliente1@demo.com` | `demo-password-123` |
| Licitante | `cliente2@demo.com` | `demo-password-123` |

O seed deixa um lote **ao vivo com dois lances**, um **agendado** e um
**encerrado com comprovante**. O lote ao vivo nasce com duração de três dias; se
ele já tiver expirado no ambiente publicado, crie outro pelo painel do leiloeiro
ou execute `seed_demo --new-live` em um ambiente local.

## O que está pronto

| Requisito do desafio | Implementação |
| --- | --- |
| Dois papéis de usuário | Leiloeiro (`SELLER`) e licitante (`BIDDER`), com cadastro e login |
| Vitrine de lotes | Abas ao vivo, agendados e encerrados; cancelados ficam fora da listagem |
| Painel do leiloeiro | Busca na Art Institute of Chicago, criação, cancelamento sem lances e resultados |
| Sala ao vivo | Lance atual, histórico, posição e contagem regressiva; WebSocket e polling |
| Carteira | Depósito simulado, saldo total, comprometido, disponível e extrato |
| Meus arremates | Participações, lotes vencidos e comprovante compartilhável |
| Auditoria pública | Histórico de lances e verificação da cadeia SHA-256 + HMAC-SHA256 |
| Regras de lance | Valor exato, saldo disponível, restrição de papel e líder sem cobrir o próprio lance |
| Anti-sniping e liquidação | Prorrogação de dois minutos, débito do vencedor e crédito do leiloeiro |
| Privacidade | Aliases públicos em histórico, auditoria e comprovantes |
| Indisponibilidade da API externa | Catálogo persistido, cache e fallback local |
| Dados de teste | Um leiloeiro, dois licitantes e lotes em diferentes estados |

Opcionais implementados: busca e filtros, Docker Compose, testes automatizados
e tema claro/escuro. O cancelamento é permitido somente antes do primeiro lance;
portanto, não há saldo comprometido a estornar nesse fluxo. Cancelamento de lote
com lances e estorno não foi implementado.

## Como rodar

Requisitos: Docker com Compose, Node.js 24+ e npm. O Compose sobe PostgreSQL e
backend; o frontend roda separadamente.

1. Siga a [configuração do backend](backend/README.md#subir-com-docker-recomendado)
   para criar o `.env`, gerar segredos, subir os serviços e semear o banco.
2. Em outro terminal, a partir da raiz do repositório:

   ```sh
   cd frontend
   npm ci
   npm run dev
   ```

3. Abra `http://localhost:5173`. A API fica em `http://localhost:8001`.

Para executar sem Docker, consulte o [backend](backend/README.md#executar-sem-docker).
Variáveis e publicação estão nos guias do [backend](backend/README.md#publicar-no-northflank)
e do [frontend](frontend/README.md#publicar-na-vercel).

## Stack e por quê

| Escolha | Motivo |
|---|---|
| **React 19 + TypeScript + Vite** | SPA com rotas, tipagem estrita e build rápido; o cliente HTTP valida os contratos da API com decoders |
| **Django 6.1 + DRF** | ORM maduro, admin, migrations e uma camada de serviços explícita para as regras de leilão |
| **PostgreSQL 18** | `SELECT … FOR UPDATE`, constraints e transações reais: necessários para concorrência de lances e liquidação |
| **SimpleJWT em cookies HttpOnly** | O JavaScript não lê o token; refresh com rotação e blacklist; Bearer aceito como fallback de API |
| **Channels + `InMemoryChannelLayer`** | WebSocket sem infraestrutura extra no deploy de uma instância; polling cobre indisponibilidade |
| **Art Institute of Chicago** | API pública, com imagens e atributos de obras; o seed usa fixtures locais para não depender dela |
| **pytest + Vitest + Testing Library** | Testes de domínio, API, componentes e concorrência com PostgreSQL real |
| **Docker Compose** | Sobe PostgreSQL e backend com migrations e health checks; o frontend roda com Vite |

## Arquitetura

```text
backend/
├── core/       settings, ASGI, health checks, ticker de liquidação
├── users/      usuário UUID, papéis, cadastro, JWT em cookie e ticket WS
├── wallet/     carteira Decimal, holds, extrato append-only e depósitos
├── auctions/   catálogo AIC, lotes, lances, liquidação, recibos e auditoria
└── tests/      domínio, API, concorrência, WebSocket e seed

frontend/
├── src/api/         cliente HTTP, refresh, decoders e serviços tipados
├── src/pages/       vitrine, sala, carteira, painel, arremates, auditoria, recibo
├── src/hooks/       sala do lote e countdown sincronizado com o servidor
├── src/context/     sessão, tema, notificações e toasts
├── src/domain/      regras de estado, versão do lote e mensagens de erro
└── src/components/  layout e UI compartilhada

docs/              requisitos, plano e relatórios de cada fase
```

Fluxo de uma requisição:

```text
React → cliente HTTP tipado → API Django/DRF → serviço de domínio → PostgreSQL
                                  │
                                  ├─ transaction.on_commit → WebSocket
                                  └─ transaction.on_commit → âncora de auditoria
```

Dependências de domínio: `users` não depende das outras apps; `wallet` depende
de `users`; `auctions` usa os serviços de `wallet`; `core` conecta os serviços.

### Decisões que sustentam as regras

- **Locks determinísticos:** o lote é bloqueado primeiro; as carteiras do
  licitante e do líder são bloqueadas por chave primária. O relógio é lido
  depois dos locks.
- **Dinheiro:** `Decimal(12,2)` no banco; a API devolve strings decimais para
  não perder precisão no JavaScript.
- **Idempotência:** `(lot, bidder, client_bid_id)` devolve o lance original com
  `200 OK` e `Idempotent-Replayed: true`; a mesma chave com outro valor retorna
  `IDEMPOTENCY_KEY_REUSED`.
- **Reconciliação em tempo real:** cada mutação incrementa `Lot.state_version`.
  O cliente descarta versões antigas, detecta saltos e busca um snapshot HTTP.
- **Efeitos externos após commit:** broadcasts e âncoras só disparam em
  `transaction.on_commit`, evitando anunciar algo que sofreu rollback.

## Testes

No backend, com PostgreSQL configurado e dependências instaladas:

```sh
cd backend
uv run pytest
```

No frontend:

```sh
cd frontend
npm run lint
npm run test:run
npm run build
```

Com o backend local em execução e o seed aplicado:

```sh
cd frontend
E2E_API_URL=http://127.0.0.1:8001 npm run test:e2e
```

O smoke E2E exercita login, carteira, lances, notificações, anti-sniping,
liquidação, comprovante e auditoria por meio das APIs públicas. Ele cria dados e
movimenta saldo simulado; execute em um banco de desenvolvimento.

Os workflows em [`.github/workflows/`](.github/workflows/) executam os checks de
cada componente. O backend inclui testes de concorrência com PostgreSQL real.

## Limitações e comportamentos conhecidos

- **Tempo real:** o channel layer é em memória e exige um único processo web.
  A sala consulta o estado por HTTP a cada quatro segundos para recuperar eventos
  perdidos. Escalar exige um channel layer compartilhado, como Redis.
- **Liquidação:** o ticker roda no processo ASGI. Com a aplicação parada, o
  encerramento aguarda a retomada ou uma leitura que dispare a liquidação.
- **Auditoria:** o HMAC é verificado pelo backend. A âncora JSONL opcional requer
  armazenamento persistente; proteção contra controle total do servidor exige
  um checkpoint externo confiável. Veja as [garantias e limites](backend/README.md#integridade-do-histórico).
- **Sessão entre sites:** o deploy Vercel/Northflank usa cookies de terceiros.
  Políticas do navegador podem bloqueá-los mesmo com os atributos corretos.
- **Imagens:** arquivos baixados para `MEDIA_ROOT` precisam de disco persistente;
  falhas de imagem remota exibem um placeholder.
- **Demonstração:** o lote ao vivo do seed dura três dias. Depois, crie outro no
  painel ou execute `seed_demo --new-live` em desenvolvimento.
- **Escopo:** depósitos são simulados. Não há cobrança real, nota fiscal,
  revenda, aplicativo nativo, recuperação de senha ou upload de imagem própria.

## Documentação

| Arquivo | Conteúdo |
| --- | --- |
| [Backend](backend/README.md) | Configuração, banco, API, regras, auditoria e publicação |
| [Frontend](frontend/README.md) | Execução, telas, integração e publicação |
| [Enunciado](docs/Teste%20tecnico%20Elite%20Dev%20-%20Verzel.md) | Requisitos do desafio |
| [Fases](docs/fases/README.md) | Critérios de aceite |
| [Relatórios](docs/implemented/) | Registro de entregas |

## Uso de IA

A IA foi usada como apoio em todo o ciclo, com decisão e validação humanas: cada
entrega foi revisada contra o enunciado e coberta por testes.

No visual, o **Stitch** serviu de protótipo: gerei versões sucessivas das telas
e iterei sobre os resultados até chegar à interface final. A primeira versão
está registrada em
[docs/assets/stitch-primeira-tela.png](docs/assets/stitch-primeira-tela.png).

Na arquitetura do sistema, a IA auxiliou no levantamento de requisitos, na
modelagem do banco e na organização dos módulos (`users`, `wallet`,
`auctions`, `core`), além de mapear riscos e as
[limitações conhecidas](#limitações-e-comportamentos-conhecidos).

Na documentação, o planejamento foi quebrado em fases isoladas com critérios de
aceite em [`docs/fases`](docs/fases/README.md), e a conclusão de cada etapa fica
registrada em [`docs/implemented`](docs/implemented/). Os
[próximos passos](docs/proximos-passos.md) foram definidos a partir do que
ficou fora do escopo inicial e do que seria necessário para escalar a
aplicação.

No desenvolvimento, usei o **Orca ADE** para orquestrar agentes de IA e o
**Zed** como editor de código.
