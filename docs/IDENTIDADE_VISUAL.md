# BurnGeoFlow — identidade visual do atlas

## Princípio

O BurnGeoFlow é uma **ferramenta de leitura espaço-temporal**, não um painel de gestão empresarial. A interface deve parecer uma publicação cartográfica contemporânea: precisão, superfície de papel, boa tipografia, cores funcionais e poucos elementos decorativos.

A informação mais importante é sempre o evento, a data, as duas representações P1/P2, o mapa e as evidências das análises. O visual **não** deve sugerir monitoramento de fogo ativo ou transformar estatísticas exploratórias em evidências causais.

## Sistema de design

- **Papel mineral** \`#f5f2e9\`, fundo de leitura; **papel claro** \`#fffdf7\`, superfícies de dados.
- **Tinta** \`#202d28\` e **pinho** \`#26483d\`, texto e estrutura.
- **Vermelho-terra** \`#aa4b36\`, orientação de leitura e destaques, sem depender da cor para distinguir os dados.
- **Azul-petróleo** \`#397b76\`, representação de P2; **laranja queimado** \`#b86040\`, P1.
- **Georgia/Palatino** para títulos e números de destaque, com alternativas do sistema. **Aptos/Segoe UI** para interações, rótulos e dados. Sem dependência de serviços externos de fonte.
- Retângulos de cantos retos, divisórias finas, etiquetas técnicas discretas, numeração sequencial e zero sombras decorativas.
- O SVG da marca deriva da ideia de **curvas de nível** e não pressupõe uma frente de fogo real.

## Arquitetura CSS

- \`frontend/src/styles.css\`: estrutura, comportamentos, componentes e regras herdadas.
- \`frontend/src/atlas-theme.css\`: tokens e tratamento visual específico da identidade editorial. Importado **depois** do CSS estrutural.
- \`frontend/src/components/ScientificPanels.tsx\`, \`LineChart.tsx\`, \`MapPanel.tsx\`: cores de dados em SVG/MapLibre alinhadas à paleta, sem alterar a semântica das medidas.

Esta separação permite evolução visual sem mexer no pipeline científico nem no contrato da API.

## Hierarquia e experiência

1. Cabeçalho de laboratório e marca cartográfica.
2. Título editorial e identificação da base de dados.
3. Processamento de outro evento (acesso à aquisição GEE/caches).
4. Identificação do evento e quatro indicadores essenciais num painel contínuo.
5. Seis capítulos navegáveis: Visão geral, Paisagem, Expansão, Movimento, Direções e Forma.
6. Legendas, limites científicos, verificações e detalhes técnicos.

A lateral possui scroll independente no desktop e vira gaveta acessível em telas menores. As abas são preservadas. O mapa continua opcional e carregado sob demanda para não prejudicar a resposta inicial da interface.

## Qualidade visual e funcional

O CI testa:
- compilação TypeScript e Vite;
- contratos de backend e pipeline;
- navegação das abas, mapa e menu móvel com Chromium;
- permanência da barra lateral durante a rolagem;
- marca, masthead e ausência de cartões arredondados genéricos;
- três capturas visuais (mapa no desktop, rosáceas no desktop e layout mobile), armazenadas como artefato temporário para revisão.

O conteúdo de referência deve manter sempre explícito: dados GlobFire/MODIS históricos, geometria acumulada e não uma interpretação direta de fogo ativo.

## Regras para telas futuras

Evite: cartões infinitos, gradientes artificiais, blur/glassmorphism, sombras profundas, emojis em controles, ícones que apenas repetem o texto, e badges em excesso. Use cor para codificação científica ou para orientar ações, não como decoração.

Priorize: títulos que expliquem a métrica, comparabilidade, unidades, origem dos dados, hierarquia tipográfica e transparência de limitações metodológicas.
