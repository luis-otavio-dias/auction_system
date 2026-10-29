# Fase 7 — Frontend, seed, README e deploy

**Status:** concluída no frontend, com ajustes finais aplicadas; seed,
README e deploy do backend seguem em rodada paralela  
**Depende de:** Fase 6

---

## 1. Objetivo

Fechar o fluxo ponta a ponta: frontend consumindo a API real, dados de
demonstração semeados, documentação completa e deploy validado.

---

## 2. Escopo

- Integração do frontend com a API.
- Autenticação por cookies.
- Carteira do licitante.
- Painel do leiloeiro.
- Sala do lote ao vivo.
- Meus arremates.
- Auditoria pública.
- Comprovante compartilhável.
- Seed de demonstração.
- README final.
- Deploy e validação ponta a ponta.

Opcionais:

- dark mode;
- busca/filtros adicionais;
- cancelamento com lances + liberação de hold;
- Docker Compose;
- testes E2E automatizados.

---

## 3. Frontend

### 3.1 Autenticação

- Login com email/senha.
- Cookies HttpOnly; frontend não lê access/refresh.
- Requisições com `credentials: "include"`.
- Refresh automático em 401.
- Logout chamando `/api/auth/logout/`.
- Se necessário, completar o cadastro público (`POST /api/auth/register`) com
  papel, email, senha e alias; a Fase 1 entregou login/refresh/logout/me, mas
  não o endpoint de registro.

### 3.2 Vitrine

- Consumir `GET /api/lots`.
- Abas ao vivo, agendados e encerrados; cancelados ocultos.
- Busca, categoria e ordenação.
- Imagem com placeholder.
- Countdown usando `ends_at` e `server_time`.

### 3.3 Carteira

- Saldo total, comprometido e disponível.
- Depósito simulado.
- Extrato.
- Mensagens de erro da API.

### 3.4 Painel do leiloeiro

- Busca de itens na AIC.
- Criação de lote.
- Lista dos próprios lotes.
- Cancelamento sem lances.
- Resultado por lote e total recebido.

### 3.5 Sala do lote

- Lance atual, histórico, posição do usuário.
- Indicador “você está ganhando” / “você foi superado”.
- Countdown.
- WebSocket + polling de fallback.
- Mensagens para cada código de erro.

### 3.6 Meus arremates

- Lotes vencidos e itens com lance.
- Comprovante e link compartilhável.

### 3.7 Auditoria e comprovante

- Página pública sem login.
- Histórico completo.
- Indicador de íntegro/adulterado.
- Explicação das garantias e limitações.
- Comprovante sem PII.

---

## 4. Seed de demonstração

Comando:

```sh
python manage.py seed_demo
python manage.py seed_demo --reset
python manage.py seed_demo --new-live
```

Dados:

- 1 leiloeiro:
  - `leiloeiro@demo.com`
- 2 licitantes:
  - `cliente1@demo.com`
  - `cliente2@demo.com`
- Senha de demo documentada no README.
- Carteiras com depósitos.
- 1 lote ao vivo com pelo menos 2 lances e hold consistente.
- 1 lote agendado.
- 1 lote encerrado com comprovante.
- Opcional: 1 lote cancelado.
- Itens de fixture local da AIC.
- O seed usa os serviços de domínio, não inserts diretos, para garantir hashes,
  holds e comprovantes consistentes.
- `--new-live` cria um novo lote ao vivo sem alterar datas de lote com
  histórico.
- `--reset` remove apenas dados de demonstração.

---

## 5. README final

Deve conter:

- visão geral da arquitetura;
- requisitos;
- setup local;
- Docker Compose;
- variáveis de ambiente;
- migrations;
- seed e credenciais;
- autenticação por cookies e blacklist;
- endpoints;
- regras de lance;
- anti-sniping;
- carteira e liquidação;
- técnica de auditoria e garantias;
- limitações conhecidas;
- deploy;
- testes e qualidade;
- onde/como a IA foi usada (para o formulário de submissão).

---

## 6. Deploy

Checklist:

- [ ] Banco recriado/migrado.
- [ ] `AUTH_USER_MODEL` correto desde a primeira migration.
- [ ] `migrate` aplicado.
- [ ] `collectstatic`.
- [ ] `seed_demo` executado.
- [ ] `AUTH_COOKIE_SECURE=True`.
- [ ] `AUTH_COOKIE_SAMESITE` adequado à topologia.
- [ ] CORS com origem do frontend.
- [ ] `WS_ALLOWED_ORIGINS` configurado.
- [ ] Websocket suportado pelo proxy, se usado.
- [ ] `ENABLE_SETTLEMENT_TICKER=True`.
- [ ] `BID_HISTORY_SECRET` e `RECEIPT_SECRET` distintos e estáveis.
- [ ] `BID_ANCHOR_PATH` com disco persistente ou limitação documentada.
- [ ] Storage de mídia definido.
- [ ] Uma única instância/processo uvicorn.
- [ ] Health check e `/health/settlement/` validados.
- [ ] Fluxo completo testado no domínio público.

---

## 7. Testes ponta a ponta

- Login com cookie.
- Refresh e rotação.
- Logout e revogação.
- Depósito.
- Criação de lote.
- Lance válido e inválido.
- Anti-sniping.
- Outbid e saldo liberado.
- Liquidação e comprovante.
- Auditoria pública.
- Comprovante público.
- WebSocket + polling.
- Responsividade e dark mode (opcional).

---

## 8. Critérios de aceite

- [x] Fluxo completo executável a partir do seed.
- [x] Leiloeiro e dois clientes funcionam sem montar dados manualmente.
- [x] Carteira e lances refletem o backend.
- [x] Sala do lote atualiza sem recarregar.
- [x] Auditoria e comprovante acessíveis sem login.
- [x] Nenhum PII público.
- [x] README permite configurar e executar do zero.
- [ ] Deploy público validado.
- [x] Testes, lint e tipos do frontend verdes; migrations e testes de backend na rodada paralela.

---

## 9. Riscos

| Risco | Mitigação |
|---|---|
| Cookies em HTTP local | `AUTH_COOKIE_SECURE=False` no dev; true em produção |
| CORS/credentials | origem explícita + `credentials: include` |
| WebSocket bloqueado | polling de fallback |
| Seed expirado | `seed_demo --new-live` |
| Imagem remota quebrada | cache local + placeholder |
| Liquidação parada | ticker + `settle_if_due` + health |
| Rollback de auditoria | checkpoint externo + documentação |
| Deploy com múltiplas instâncias | Redis externo ou polling documentado |

---

## 10. Checklist final

- [x] Integrar auth/cookies.
- [x] Integrar vitrine/detalhe.
- [x] Integrar carteira/depósito (incluindo carteira e extrato do leiloeiro).
- [x] Integrar painel do leiloeiro com resultado por lote.
- [x] Integrar sala ao vivo + WS/polling.
- [x] Integrar meus arremates e lotes com lance.
- [x] Integrar auditoria/comprovante.
- [x] Criar `seed_demo`.
- [x] Atualizar README.
- [ ] Configurar deploy.
- [ ] Rodar E2E final contra o backend já reiniciado com as correções.
- [x] Validar saúde, logs e limitações.

---

## 14. Registro de implementação do frontend

**Data:** 2026-10-27  
**Relatório detalhado:** [`../implemented/fase-7-frontend.md`](../implemented/fase-7-frontend.md)

O frontend foi integrado à API real conforme os contratos das fases 3–6:

- cliente HTTP tipado com `credentials: "include"`, refresh único em `401` e
  erros `{code, detail}`;
- rotas de vitrine, sala do lote, carteira, painel do leiloeiro, meus arremates,
  auditoria e comprovante;
- WebSocket por ticket efêmero, reconexão com backoff, renovação em `4401`,
  limite de idade e polling de 4 segundos;
- controle de `state_version` por lote, incluindo descarte de respostas antigas
  e busca de snapshot em salto de versão;
- testes com `vitest` e `@testing-library/react` para auth/refresh, vitrine,
  lance com erro, `state_version` e auditoria;
- `npm run lint`, `npm run build` e `npm run test:run` verdes.

O backend expõe os endpoints das fases 3–6 e foi reconciliado na segunda rodada.
A etapa final corrigiu o offset do countdown, a carteira do leiloeiro, o
consumo de `results_by_lot`, `lot_id` em notificações e `share_url`/`issued_at`
nos arremates. As evidências estão em
[`../implemented/fase-7-frontend.md`](../implemented/fase-7-frontend.md), seção 14.
