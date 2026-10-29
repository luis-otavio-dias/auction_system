#### D4 verzel

# Teste tecnico:a Elite Dev na Verzel

Ola! Que bom ter vocé nesta etapa. Seu desafio é construir uma Casa de Leildes online, do jeito que faria no dia a dia de um time de desenvolvimento.

01 O desafio

02 Front-End

03 Back-End

04 Tecnologias e requisitos

05 Opcionais

06 Como enviar

# Proposta de solugao

Vocé deve criar uma Casa de Leildes online, onde um leiloeiro coloca itens em leilao e licitantes disputam cada lote com lances ao vivo. O que sera leiloado é escolha sua: obras de arte, carros, cartas colecionaveis, discos, livros raros, 0 que vocé quiser, desde que os itens venham de uma API publica.

O leiloeiro monta um lote a partir de um item buscado na API externa que vocé escolheu, definindo lance inicial, incremento minimo, horario de inicio e fim, e outros campos relevantes.

O licitante deposita um saldo simulado na sua carteira, acompanha os lotes ao vivo, da lances e, se vencer, recebe um comprovante de arremate que pode compartilhar por link. Qualquer pessoa, mesmo sem login, pode auditar o histdrico de lances de um lote e verificar que ele nao foi adulterado.

#### Requisitos funcionais base

#### DEPLOY

O deploy da aplicagdo é obrigatorio.

Usuarios e Autenticagao: A plataforma possui dois papéis distintos:

#### LEILOEIRO (VENDEDOR)

#### LICITANTE (CLIENTE)

Cria e gerencia os prdprios lotes. Nao pode dar lances.

Deposita saldo, da lances e arremata itens.

#### REFERENCIAS

Para ver como esses fluxos costumam ser resolvidos. Nao copie; use como ponto de partida:

- [https://www.catawiki.com/pt](https://www.catawiki.com/pt)
- [https://www.liveauctioneers.com/](https://www.liveauctioneers.com/)
- [https://www.superbid.net/](https://www.superbid.net/)

Ad verzel

Teste técnico: Elite Dev na Verzel 02

## Front-End

#### Vitrine de lotes

Interface que exibe os itens leiloados, separando lotes ao vivo, agendados e encerrados. Lotes cancelados nao aparecem na vitrine.

#### Painel do leiloeiro

Permite buscar itens na API escolhida e criar um lote a partir deles (com imagem, titulo, atributos do item, data de inicio/fim e valor minimo); cancelar um lote que ainda nao recebeu lances; e ver o resultado de cada lote encerrado (se foi arrematado e por quanto) e o total recebido.

#### Sala do lote ao vivo

Exibe o lance atual, histdrico de lances, posi¢ao do usuario nos lances, contagem regressiva e um indicador claro de “vocé esta ganhando” / “vocé foi superado”. Tudo atualizado sem recarregar a pagina.

#### Carteira do licitante

Mostra saldo total, saldo comprometido, saldo disponivel e opgao de deposito simulado.

#### Meus arremates

Interface onde o usuario vé os itens em que deu lance e os lotes vencidos, com 0 respectivo comprovante e link de compartilhamento.

#### Pagina de auditoria

Publica e sem login, mostra o histdrico completo de lances de um lote e informa se ele esta integro ou foi adulterado.

#### Mensagens de feedback

Mensagem clara para cada lance recusado, dizendo o motivo (abaixo do minimo, saldo insuficiente, vocé ja esta ganhando, lote ainda nao iniciado ou lote encerrado).

Ad verzel

Teste técnico: Elite Dev na Verzel 03

## Back-End

APIs tém limites e instabilidades. Sua aplicagao nao pode ficar inutilizavel por causa disso.

A vitrine, as salas, a auditoria e o comprovante devem continuar funcionando mesmo que a API caia.

#### REGRAS DE LANCE

- S6 sao aceitos em lotes ao vivo (entre inicio e fim).
- Oprimeiro lance deve ser = ao lance inicial. Os seguintes devem ser = ao lance atual + incremento minimo.
- Olicitante lider nado pode cobrir o proprio lance.

#### Saldo comprometido

Saldo disponivel = saldo total - comprometido. Quandoo licitante lidera, o valor fica comprometido; se superado, volta ao disponivel imediatamente. O lance so é aceito se couber no disponivel.

#### Prorrogagao (anti-sniping)

Lance aceito nos ultimos 2 minutos estende o fim do lote para +2 minutos.

#### Liquidagao

Ao encerrar, debita-se 0 valor do vencedor e credita-se ao leiloeiro, gerando o comprovante. Lotes sem lances fecham sem vencedor.

#### Historico a prova de adulteragao

Qualquer alteragao, remogao ou insergao posterior no histdérico (mesmo direto no banco de dados) deve ser detectada pela auditoria. A técnica é escolha sua; explique-a.

#### Privacidade

A auditoria e o comprovante identificam licitantes sem expor dados pessoais.

Ad verzel

Teste técnico: Elite Dev na Verzel 04

# Tecnologias e requisitos

#### Tecnologias obrigatorias

- Front-End: React, com ou sem framework (Next.js, Vite, Remix ou o que preferir).
- Back-End: NodeJS ou Python. Fique a vontade com o framework (NestJS, Express, FastAPI, Django, etc.).
- Banco de Dados: PostgreSQL, MySQL ou um banco NoSQL (como MongoDB). Certifique-se de incluir no README instrugG6es claras sobre como configurare utiliza-lo.

#### Requisitos nao funcionais

#### PRAZO

#### DADOS DE TESTE

Vocé tem 7 dias corridos a partir do recebimento deste desafio para completa-lo.

Deixe semeados um leiloeiro, dois clientes e ao menos um lote publicado com lances abertos, para que possamos percorrer o fluxo sem montar tudo do zero.

#### DOCUMENTACGAO

O projeto deve incluir um README detalhado explicando o passo a passo para configurar e executar a aplicagao. Funcionalidades com comportamento inesperado devem ser mencionadas. A auséncia de explicagdes impactara negativamente na nota final.

Ad verzel

Teste técnico: Elite Dev na Verzel O05

# Oie Opcionais

Nenhum dos itens abaixo é obrigatério, mas todos sao considerados na avaliagao.

- Buscae filtro de lotes.
- Cancelamento de lote com estorno automatico.
- Docker Compose.
- Testes automatizados.
- Dark Mode: Interface com suporte a tema claro e escuro.

#### NAO PRECISA FAZER

Nota fiscal, revenda entre usuarios, aplicativo nativo ou recupera¢gao de senha.

Ad verzel

Teste técnico: Elite Dev na Verzel 06

## Como enviar

Envie pelo formulario [https://elitedev.verzel.com.br/?elite-dev-2026-2](https://elitedev.verzel.com.br/?elite-dev-2026-2) preenchendo os campos assim:

#### Nome completo e E-mail

seus dados de contato.

#### Repositorio

o link do repositério publico no GitHub com a aplicagao.

#### Tem mais de um repositorio?

se front e back estiverem separados, informe os dois.

#### Deploy

0 link publico da aplicagao (obrigatorio).

Onde e como vocé usou IA _ usar IA é permitido. Conte onde e como usou e o que revisou ou

ajustou. Se nao usou, conte isso também.

Ad verzel

Teste técnico: Elite Dev na Verzel 07
