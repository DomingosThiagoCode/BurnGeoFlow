# BurnGeoFlow

**Aquisição automatizada e exploração espaço-temporal de áreas queimadas.**

O BurnGeoFlow reúne três partes distintas:

1. **Pipeline Python:** busca dados GlobFire v2 pelo Google Earth Engine
   (ou reutiliza entradas locais), constrói P1/P2 e calcula indicadores
   geoespaciais, TR/IGT e auditorias.
2. **API FastAPI:** entrega séries e GeoJSONs por data, mantém um índice
   reconstruível e gerencia execuções com status e logs em SQLite.
3. **Frontend React:** interface responsiva com mapa MapLibre, linha do
   tempo, gráficos e botão para processar outros IDs.

**Estado científico:** os resultados calculados são análises geométricas
descritivas. Uma execução computacional bem-sucedida **não** significa
validação independente de imagens, nem comprovação de propagação física do
fogo.

## Instalação rápida no Windows

Requisitos: **Python 3.11+**, **Node.js 24** para a compilação inicial e Git.
Abra o PowerShell na pasta do repositório:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-api.txt
cd frontend
npm ci
npm run build
cd ..
python iniciar_burngeoflow.py
```

Depois abra <http://127.0.0.1:8000>. Em uso cotidiano, após ativar
o ambiente Python, basta:

```powershell
python iniciar_burngeoflow.py
```

O React compilado é servido pelo próprio FastAPI. Não precisa deixar o
Vite rodando em outro terminal. O app limita o serviço a
`127.0.0.1` por padrão: **não o exponha na internet**.

## Primeiro evento e Google Earth Engine

Para o evento **24340828** (Pantanal 2020), selecione-o se já estiver
processado em `execucoes/24340828/`.

Se não houver entradas locais, a aquisição GEE exige uma conta Google com
Earth Engine e um projeto Google Cloud configurado:

```powershell
python -m pip install -r requirements-gee.txt
Copy-Item .env.example .env
# Configure EE_PROJECT_ID em .env
earthengine authenticate
```

Na interface, abra **Processar e acompanhar eventos**, informe o ID,
escolha origem `Automática` ou `Earth Engine`, e, se souber,
informe o ano para acelerar a consulta. O serviço acompanha estado e logs.
O GEE não fornece percentual real confiável durante algumas operações.

A CLI continua disponível e é recomendada para depuração:

```powershell
python executar_pipeline.py --id 24340828 --ano 2020 --origem gee
python executar_pipeline.py --id 24340828 --origem local
```

Opções avançadas: `--origem auto|local|gee|brutos`,
`--refazer`, `--somente-aquisicao`, `--saida`,
`--p1/--p2`. Veja
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

- [Arquitetura e responsabilidades](docs/ARQUITETURA.md)
- [Auditoria técnica e riscos](docs/AUDITORIA_ARQUITETURAL_2026-11-12.md)
- [Backlog priorizado](docs/BACKLOG_REFACTOR.md)
- [API, SQLite e benchmark](docs/API.md)
- [Proveniência e limitações científicas](docs/PROVENIENCIA.md)
- [Manual completo do fluxo histórico/CLI](docs/REFERENCIA_OPERACIONAL.md)
- [Frontend e desenvolvimento](frontend/README.md)

Projeto acadêmico em evolução. Não substitui a aferição independente dos
produtos GlobFire/MODIS.
