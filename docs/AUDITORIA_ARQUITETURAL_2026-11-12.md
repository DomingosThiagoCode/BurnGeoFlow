# Auditoria técnica pré-refatoração (12/11/2026)

## Fonte e escopo

Revisados: árvore completa do commit `0d07c34a`, 17 commits do histórico,
`executar_pipeline.py`, `visualizador.py`, visualização em
`burngeoflow/visualizacao/dados.py`, aquisição Earth Engine, GEE geométrico,
métricas P1, linhagens, TR/IGT, integração, validação, documentos, dependências,
CI e testes. **Os GeoJSONs reais e o computador Windows do usuário não estão
disponíveis neste ambiente**. Isso impede afirmar tempos reais ou confirmar
fluidez de renderização no navegador, sem benchmark no local ou no CI.

## Funcionalidades protegidas contra regressões

- CLI `executar_pipeline.py`: `--origem auto|local|gee|brutos`,
  `--somente-aquisicao`, `--refazer`, `--baixar-exemplo`.
- GEE GlobFire v2; construção de P1/P2, páginas recuperáveis e dados brutos
  preservados; normalização geométrica auditada.
- Etapas 1 a 6 do processamento (8 operações no manifesto): validação,
  auditoria, regularização, paisagem, linhagens, TR/IGT, integração e robustez.
- Produtos CSV, GeoJSON, PNG, Markdown, resumos JSON e manifesto SHA-256.
- P1 original (todos patches) e P2 (rastreamento), ambos por data; métricas,
  gráficos, exportação, status de auditoria, avisos de lacunas.
- Filosofia: sucesso computacional não equivale a validação científica externa;
  anomalias P1 e perdas espaciais não devem ser ocultadas.
- Cache local sob `execucoes/<ID>/` sem reaquisição repetitiva pelo GEE.
- Compatibilidade com `python -m burngeoflow....` e importações científicas
  atuais. Não migrar dados existentes nem alterar fórmulas de forma incidental.

## Achados priorizados

| Severidade | Problema | Evidência | Ação |
|---|---|---|---|
| P0 | Mapa reconstruído no servidor a cada interação | `visualizador.py`: `st.select_slider`, `pdk.Layer`, `st.pydeck_chart`, `st.line_chart` todos dentro de `main()` | Componentes web React e API por data; medir |
| P0 | Carga inicial retém todas as geometrias e tabelas em memória | `dados.py:carregar_evento` chama `_indexar_geojson` para P1/P2; `json.load` do FeatureCollection completo | Índice persistente por data com `ijson`, streaming na primeira indexação |
| P1 | Carregamento e transferências sem limite por data | `visualizador.py` serializa uma `FeatureCollection` inteira em pydeck; P1/P2 carregados juntos quando solicitado | API permite apenas geometria da data/camada selecionadas, FileResponse |
| P1 | UI, I/O, métricas e download acoplados | `visualizador.py` 349 linhas com Python UI/estado e Pandas/geojson | Interface separada de API Python e repositório somente leitura |
| P1 | Processamento e apresentação no mesmo ambiente Python | `requirements-viewer.txt` inclui Shapely e Matplotlib embora visor apenas leia GeoJSONs | Frontend isolado; APIs leves |
| P1 | CLI depende de caminhos/artefatos fixos e subprocessos sem fila operacional | `executar_pipeline.py` orquestra processos, logs e retomada | Expor serviço sem reimplementar CLI; jobs depois com SQLite |
| P1 | Sem banco de dados transacional | Registro é filesystem: `execucao.json`, CSV, GeoJSON, logs | Não migrar geometrias; SQLite apenas para catálogo de jobs/status quando necessário |
| P1 | Tarefas científicas grandes misturam leitura/validação/cálculo/figuras | `integracao.py` 876 linhas, `earth_engine.py` 648, `robustez.py` 375 | Refatoração ulterior por fronteiras e testes, não mover arquivos por estética |
| P1 | Testes não cobrem Web API / navegador | CI instala requirements.txt, chama unittest e caso de referência | Testes API, browser smoke test e benchmark |
| P2 | Instalação fragmentada | requirements core/gee/viewer; sem pyproject.toml | Padronizar ferramentas sem quebrar `pip install -r` atual |
| P2 | .gitignore não cobre node_modules/dist/.pytest_cache | arquivo atual | Corrigir na migração web |
| P2 | README concentra instruções históricas e do produto | README extenso | Guia rápido e docs/ detalhados, sem perder proveniência |
| P2 | Código de sumários contém formatação e negócio no mesmo módulo | `relatorios/sintese_caso.py` cerca de 490 linhas | Separar se houver necessidade demonstrada |

## Segurança e integridade

- Credenciais GEE ficam locais e estão no .gitignore; preservar.
- API futura deve ouvir em **127.0.0.1** por padrão; CORS para o dev server
  local; IDs numéricos e datas ISO, não aceitar caminho arbitrário do cliente.
- Não habilitar endpoints que disparam subprocessos com argumentos livres.
- Índices derivados são descartáveis; nunca sobrescrever P1/P2/brutos GEE.
- Validar SHA-256 registrado na Etapa 5 antes de expor métricas oriundas de
  arquivos diferentes. Uma verificação apenas por mtime/size é insuficiente
  como prova de proveniência científica.
- `execucoes/` é dado do usuário e não deve entrar em migração destrutiva.
- Dados são locais; não foi identificado SQLite nem PostgreSQL na versão atual.

## Desempenho

Não há telemetria de navegador nem tamanhos/tempos dos GeoJSONs reais do
usuário. Os gargalos listados são *candidatos sustentados pelo código*,
não um perfil de CPU/heap já medido. Instrumentar:

1. tempo frio e pico de memória para abrir P1/P2 com o leitor existente;
2. tempo de produzir GeoJSON de uma data no leitor existente;
3. tempo frio para construir índice por data no novo repositório;
4. latência repetida de geometria por data e volume de resposta (p50/p95);
5. tempos percebidos no navegador (primeiro mapa, troca de data) no Windows
   real, com 57 datas e dados originais, após disponibilidade do frontend.

Usar mesmo ID, mesma máquina, versões de dependência e entradas para
comparações. Não prometer melhoria numérica sem executar ambos.

## Escolha de arquitetura

- **Domain core**: `burngeoflow/` permanece sem alterações matemáticas.
- **Backend**: `backend/app/api` rotas FastAPI, schemas tipados,
  `repositories` (acesso local por data), `services` (casos de uso),
  `core` (configuração/erros). CLI permanece na raiz inicialmente.
- **Frontend**: React + TypeScript + Vite; MapLibre GL JS para mapa
  com atualização incremental por data; componentes e serviços de rede isolados.
  Nada de Python para renderizar páginas.
- **Persistência**: preservar GeoJSON/CSV/JSON como fonte de verdade
  geoespacial; índices reconstruíveis; SQLite, se necessário, para estado
  operacional de execuções. **Sem PostgreSQL neste estágio.**
- **Compatibilidade**: mantenha `visualizador.py` até que a nova UI passe
  em testes funcionais e de experiência no ambiente real.

## Métricas de aceite por fase

1. Auditoria: documento, benchmark replicável, CI existente verde.
2. API: data específica, métricas e downloads, sem GEE, sem leitura integral
   dos GeoJSONs em cada requisição; 404/422/409 previsíveis, testes.
3. React: paridade de seleção ID/data, P1/P2, gráficos, transições,
   downloads, status; responsividade e estados de loading/erro.
4. Jobs: acionamento seguro do CLI existente, status persistente e retomada.
5. Segurança/carga: garantir bind local; cache invalidado após alterações;
   perfis CI e Windows antes/depois.
6. Entrega: documentação atualizada; sem remoção até aprovar paridade.

Decisões reconsideráveis: SQLite apenas quando jobs realmente precisarem de
persistência; otimização geométrica (generalização/tiles) somente se
profiling confirmar payload ou browser GPU como gargalo. Nenhuma redução
silenciosa da precisão original.

## Medição inicial CI (GitHub Actions Ubuntu Python 3.11, caso de referência)

Primeira rodada instrumentada (3 repetições, antes da API):
- Leitura fria de **todos os P1/P2** no leitor Streamlit: mediana **435,629 ms**.
- Serialização da última data para GeoJSON: mediana **15,895 ms**.
- Payload GeoJSON da última data: **190.062 bytes**.
- Pico de alocações captadas por `tracemalloc`: **26,733 MiB**.

Esses valores pertencem **ao caso de referência do CI**, não ao novo cache GEE
do usuário. Não medem renderização GPU, latência de rede ou tempo total da UI.
A primeira rodada também identificou que o teste de estrutura tratava o nome
`scripts/` como legado, embora fosse uma pasta nova exclusivamente para
diagnóstico; o contrato foi restringido a `sql/` e `gee/`, que são de fato
pastas históricas removidas.
