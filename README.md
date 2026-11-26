# BurnGeoFlow

**Aquisição automatizada e exploração espaço-temporal de áreas queimadas.**

O BurnGeoFlow reúne três partes distintas:

1. **Pipeline Python:** busca dados GlobFire v2 pelo Google Earth Engine
   (ou reutiliza entradas locais), constrói P1/P2 e calcula indicadores
   geoespaciais, TR/IGT e auditorias.
2. **API FastAPI:** entrega séries e GeoJSONs por data, mantém um índice
   reconstruível e gerencia execuções com status e logs em SQLite.
3. **Frontend React:** interface responsiva com mapa MapLibre, linha do
   tempo e seis abas de análise: Visão geral, Paisagem, Expansão, Movimento,
   Direções (rosáceas TR/IGT e dos cinco feixes) e Forma. A navegação
   modular usa uma barra de ícones compacta com expansão por hover/foco
   no desktop e menu acessível no celular.

**Estado científico:** os resultados calculados são análises geométricas
descritivas. Uma execução computacional bem-sucedida **não** significa
validação independente de imagens, nem comprovação de propagação física do
fogo. O botão **Executar** ainda usa a cadeia científica legada; a preparação
P1 conectado/P2 retrospectivo e o balanço D-005 existem em modo
**experimental versionado**. A integração completa às análises permanece
pendente. Consulte [METODOLOGIA.md](docs/METODOLOGIA.md),
[ROTEIRO.md](docs/ROTEIRO.md) e [ESTADO_EXECUCAO.md](docs/ESTADO_EXECUCAO.md).

## Instalação rápida no Windows

Requisitos: **Python 3.11+**, **Node.js 24** para a compilação inicial e Git.
Abra o PowerShell na pasta do repositório:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
cd frontend
npm ci
npm run build
cd ..
python iniciar_burngeoflow.py
```

O `requirements.txt` reúne todas as dependências Python; não é necessário instalar arquivos separados para API, GEE ou visualizador. Depois abra <http://127.0.0.1:8000>. Em uso cotidiano, após ativar
o ambiente Python, basta:

```powershell
python iniciar_burngeoflow.py
```

O React compilado é servido pelo próprio FastAPI. Não precisa deixar o
Vite rodando em outro terminal. O app limita o serviço a
`127.0.0.1` por padrão: **não o exponha na internet**.

## Páginas e navegação da plataforma

A home narrativa está em **`/apresentacao/`**,
com oito cenas de scrollytelling sobre dados históricos de 2020. O scroll
controla observações acumuladas do ID `24340828`; não é uma simulação
da frente ativa do fogo. O logotipo do atlas leva de volta à apresentação.

A aplicação científica está em **`/`**, organizada por módulos:
- **Visão geral** (`/#atlas`): mapa temporal sob demanda, áreas P1/P2, patches
  e controles de evento, data, reprodução e camadas no cartão à direita;
- **Paisagem, Expansão, Movimento, Direções e Forma** (`/#analise/<nome>`):
  gráficos e rosáceas. Os setores das rosáceas podem ser selecionados com
  mouse, toque ou teclado; o recorte temporal usa as datas **observadas**,
  exibe valores absolutos e percentuais, e só compartilha a escala entre
  gráficos ponderados na mesma unidade. Escolher uma transição atualiza a
  data de referência do atlas;
- **Explorar incêndios** (`/#catalogo`): busca de IDs por bioma oficial
  IBGE 2019, UF/Brasil (malha IBGE 2024), GeoJSON WGS84 ou polígono
  desenhado no mapa. Filtros por ano ou datas, margem ±N dias e cache JSON
  com opção explícita de atualizar. Contagens **na AOI** representam feições
  que intersectam a região, não a área recortada nem o total do evento;
  `Ver total` consulta o ID/ano completo separadamente;
- **Processamento** (`/#processamento`): iniciar jobs, inspecionar a
  disponibilidade de arquivos/checkpoints, consultar histórico, erros e
  logs. Um indicador de job ativo aparece na navegação.

O catálogo apresenta **cinco eventos por página**, com busca por ID,
ordenação e navegação sem repetir consultas GEE apenas por trocar de
página. Navegação entre módulos preserva seleção de evento e data,
mantendo os jobs ativos no servidor.

O processamento remoto do GEE pode continuar depois de uma interrupção
do worker local. A recuperação deve consultar logs e tarefas remotas antes
de criar qualquer nova aquisição. Não repita o download dos IDs `24340828`
e `24194371` se já houver dados brutos locais íntegros.

## Primeiro evento e Google Earth Engine

Para o evento **24340828** (Pantanal 2020), selecione-o se já estiver
processado em `execucoes/24340828/`.

Se não houver entradas locais, a aquisição GEE exige uma conta Google com
Earth Engine e um projeto Google Cloud configurado:

```powershell
Copy-Item .env.example .env
# Configure EE_PROJECT_ID em .env
earthengine authenticate
```

Na interface, abra **Processar e acompanhar eventos**, informe o ID,
escolha origem `Automática` ou `Earth Engine`, e, se souber,
informe o ano para acelerar a consulta. O serviço acompanha estado e logs.
Para incêndios extensos, a aquisição passa a utilizar tarefas GEE **batch**
com assets temporários e checkpoint para retomada, evitando depender do
limite interativo de aproximadamente cinco minutos. Os assets são excluídos
somente após validação e gravação locais. É preciso ter permissão de escrita
nos assets de `EE_PROJECT_ID`. O GEE não oferece percentual de progresso
confiável para todas as operações.

Para escolher explicitamente o modo no terminal:

```powershell
python executar_pipeline.py --id 24340828 --ano 2020 --origem gee --modo-gee lote
```

A CLI continua disponível e é recomendada para depuração:

```powershell
python executar_pipeline.py --id 24340828 --ano 2020 --origem gee
python executar_pipeline.py --id 24340828 --origem local
```

Opções avançadas: `--origem auto|local|gee|brutos`,
`--refazer`, `--somente-aquisicao`, `--saida`,
`--p1/--p2` e `--preparar-metodologia-v2` (somente P1 local;
gera derivados experimentais sem substituir os produtos legados).
Veja
[referência operacional detalhada](docs/REFERENCIA_OPERACIONAL.md).

## Fluxo de uso

```text
ID do evento / GEE / cache local
              |
              v
P1 (todos os patches) + P2 (região rastreada)
              |
              v
Pipeline científico (Python, 8 operações)
              |
              v
GeoJSON / CSV / JSON / gráficos em execucoes/<ID>/
              |
              +----> API FastAPI + índice por data
                         |
                         v
                 Visualizador React
```

O visualizador lê o resultado da data e das camadas selecionadas,
sem reconstruir todo o mapa no servidor a cada interação. O banco SQLite
em `execucoes/.burngeoflow/jobs.sqlite3` contém **apenas**
informações de tarefas, não duplica geometrias.

## Desenvolvimento

**API e frontend em dois terminais** (com hot reload do Vite):

```powershell
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
cd frontend
npm ci
npm run dev
```

Abra <http://127.0.0.1:5173> em desenvolvimento.
O frontend compilado abre na porta 8000, servida pela API.

**Testes:**

```powershell
python -m unittest discover -s tests -v
python -m unittest discover -s backend/tests -v
cd frontend
npm run test
npm run build
```

O GitHub Actions roda a suíte científica, os contratos da API, o caso
de referência, benchmarks e os testes/build do frontend. A comparação de
desempenho no caso do CI e suas limitações constam em
[docs/API.md](docs/API.md). O teste com os GeoJSONs reais do usuário no
Windows ainda é necessário para afirmar a qualidade da experiência.

## Estrutura

```text
burngeoflow/         Núcleo científico (aquisição, análises e auditoria)
backend/app/          API, modelos de entrada, serviços e repositórios
backend/tests/        Testes independentes de API, SQLite e distribuição
frontend/src/         Componentes React, tipos e serviços REST
frontend/tests/       Testes unitários do cliente
docs/                 Arquitetura, metodologia e decisões técnicas
scripts/              Benchmarks reproduzíveis
executar_pipeline.py  CLI científica compatível
iniciar_burngeoflow.py Inicializador do app compilado
execucoes/            Dados locais, índices descartáveis e banco de jobs (Git-ignored)
```

O visualizador anterior `visualizador.py` (Streamlit) permanece como
fallback durante a homologação, sem apagar funcionalidades nem histórico.

## Documentação

- [Decisões científicas D-001 a D-016](docs/METODOLOGIA.md)
- [Roteiro de pesquisa e dependências](docs/ROTEIRO.md)
- [Estado operacional, merges e pendências](docs/ESTADO_EXECUCAO.md)
- [Landing e proveniência dos 57 quadros](docs/LANDING_SCROLLYTELLING.md)
- [Reprocessamento v2 com checkpoints](docs/PLANO_REPROCESSAMENTO_V2.md)
- [Arquitetura e responsabilidades](docs/ARQUITETURA.md)
- [Auditoria técnica e riscos](docs/AUDITORIA_ARQUITETURAL_2026-11-12.md)
- [Backlog priorizado](docs/BACKLOG_REFACTOR.md)
- [API, SQLite e benchmark](docs/API.md)
- [Proveniência e limitações científicas](docs/PROVENIENCIA.md)
- [Manual completo do fluxo histórico/CLI](docs/REFERENCIA_OPERACIONAL.md)
- [Frontend e desenvolvimento](frontend/README.md)

Projeto acadêmico em evolução. Não substitui a aferição independente dos
produtos GlobFire/MODIS.
