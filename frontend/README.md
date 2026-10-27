# Plataforma de leilões

Frontend em React e TypeScript, com Vite e CSS responsivo. A tela inicial é `Home`.

```sh
npm install
npm run dev
```

```sh
npm run build
npm run lint
```

O catálogo e as categorias começam vazios. A interface apresenta contagens zeradas, perfil sem nome ou foto e estados vazios para lotes e resultados. Não há imagens de produtos, dados pessoais ou informações de leilões pré-cadastradas.

Os dados locais ficam em `src/services/lots.json`. O acesso é centralizado em `auctionService`, preparado para futura integração com o backend. Busca, filtros e componentes de lance continuam disponíveis na estrutura. Os lances usam apenas estado local; assinatura de novidades e serviços ainda não possuem integração.

```text
src/
├── components/       # Cabeçalho, lotes, modais, ícones e avisos
├── pages/
│   └── Home/         # Tela inicial e estilos do layout
├── hooks/            # Estado dos lances, cronômetro e notificações
├── services/         # Acesso aos dados do catálogo
├── types/            # Tipos do domínio e da interface
├── utils/            # Formatação, filtros e ordenação
├── App.tsx           # Renderiza Home
├── main.tsx          # Inicialização do React
└── index.css         # Estilos globais
```

As fontes são carregadas pelo Google Fonts, com alternativas locais em caso de indisponibilidade.
