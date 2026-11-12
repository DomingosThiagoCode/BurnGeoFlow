# API local de visualização

O backend **não substitui** o pipeline científico. Ele recebe um diretório
de execuções já concluídas e expõe respostas leves por evento, data e camada.
O CLI atual permanece independente e sem alterações.

## Instalação

    python -m pip install -r requirements-api.txt

## Iniciar

    python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000

A documentação OpenAPI estará em <http://127.0.0.1:8000/docs>.

Configurações:

- `BURNGEOFLOW_DATA_DIR`: caminho da pasta que contém subpastas por ID
  (padrão: `<repositório>/execucoes`).
- `BURNGEOFLOW_ENV=production`: desativa origens CORS pré-configuradas.
- `BURNGEOFLOW_CORS_ORIGINS`: lista de origens permitidas separadas
  por vírgulas (em desenvolvimento, localhost:5173 e 127.0.0.1:5173).

**Não exponha esta API local à internet:** não há login ou autenticação.
Ouvimos em 127.0.0.1, não 0.0.0.0.

## Endpoints

- `GET /api/health`
- `GET /api/events`
- `GET /api/events/{id}/overview`
- `GET /api/events/{id}/series`
- `GET /api/events/{id}/transitions`
- `GET /api/events/{id}/dates/{YYYY-MM-DD}`
- `GET /api/events/{id}/dates/{YYYY-MM-DD}/geometry?layer=p1|p2`
- `GET /api/events/{id}/downloads/series.csv`

Os GeoJSONs originais não são modificados. Na primeira consulta geométrica,
o repositório cria um índice reconstruível por data em
`execucoes/<ID>/.visualizador_index/`. O conteúdo é escrito como
JSON Lines por data para evitar carregar todos os polígonos a cada requisição;
a resposta HTTP é convertida em GeoJSON válido por streaming.

O índice é invalidado se tamanho ou modificação da fonte mudar. Caso
a Etapa 5 esteja disponível, seu SHA-256 é conferido antes da indexação;
os próprios resumos e métricas também são conferidos. Índices derivados
são descartáveis; P1/P2 e brutos GEE não sofrem nenhuma alteração.

**Restrição inicial:** servidor local com um único worker Uvicorn.
A indexação usa lock por processo e ainda não implementa lock entre
processos diferentes. Não executar múltiplos workers concorrentes.

Uma instância nova sem série integrada pode listar as datas da fonte P1,
mas não inventa indicadores científicos. `409` indica inconsistência de
dados, `404` ausência de evento/data, `422` parâmetro inválido.

## Continuidade e banco de dados

Persistência geoespacial permanece em GeoJSON/CSV/JSON e manifesto.
SQLite será considerado para **gerenciamento de jobs**, não para duplicar
geometrias existentes. Não há migração destrutiva nesta entrega.

## Benchmark da API (mesmo caso de referência em CI, Python 3.11)

A execução instrumentada do PR #21 registrou:

| Métrica | Valor |
|---|---:|
| Leitor antigo, abertura completa | 566,128 ms (3 repetições) |
| Índice novo, construção inicial | 1.847,904 ms |
| Índice novo, consulta repetida P1+P2 por data | 4,293 ms (mediana de 5) |
| Pico Python leitor antigo | 26,733 MiB |
| Pico Python indexação nova | 2,386 MiB |
| GeoJSON antigo última data | 190.062 bytes |
| GeoJSON indexado última data P1+P2 | 190.103 bytes |

A primeira indexação demora mais do que uma leitura completa individual.
O ganho mensurável de latência está nas **consultas posteriores sem reparse
do arquivo integral**. Os bytes são equivalentes: nesta etapa ainda não
houve simplificação cartográfica. Valores não incluem navegador ou rede.

A medição do leitor legado inclui serialização separada (20,613 ms nessa
mesma execução), enquanto a consulta da API inclui a serialização
pré-materializada no cache. Por isso, não interpretar a razão dos dois
tempos como aceleração total de todo o produto.


## Execução assíncrona a partir do painel (jobs)

A API pode iniciar a CLI já existente em um **processo Python separado**.
O servidor HTTP retorna imediatamente um identificador de tarefa e permite
consultar estado e logs. Nenhuma fórmula ou aquisição GEE foi copiada
para o backend.

Endpoints:

- `POST /api/jobs` com corpo JSON
  `{"id_incendio":24340828,"origem":"auto","ano":2020}`.
  A origem aceita auto, local, gee ou brutos; ano é opcional quando aplicável.
- `GET /api/jobs` lista as execuções recentes.
- `GET /api/jobs/{id}` mostra estado queued/running/completed/failed/interrupted.
- `GET /api/jobs/{id}/logs` retorna até 100 últimas linhas,
  com limite de leitura por solicitação.

O banco de estado é `execucoes/.burngeoflow/jobs.sqlite3`
(SQLite padrão, schema versão 1). Logs ficam em
`execucoes/.burngeoflow/logs/<id>.log`. Esses arquivos são
ignorados pelo Git. **A implementação não migra nem edita P1/P2/GeoJSONs**.
O CLI grava resultados onde sempre gravou: `execucoes/<ID>`.
Não há backup dos dados geoespaciais porque nenhuma migração deles é feita.

Uma tarefa ativa por vez evita duas operações pesadas concorrentes,
inclusive se duas requisições chegarem ao mesmo tempo. Somente a própria
CLI decide se pode reutilizar resultados existentes; o servidor não marca
etapas como científicamente validadas.

O worker atualiza uma marca de atividade de 5 em 5 segundos. Caso seja
interrompido, após 120 s sem atividade o serviço tenta classificá-lo como
interrupted, sem presumir sucesso. Processos GEE podem ser longos e não
possuem percentual confiável. O painel mostra logs, **não estimativas
inventadas de progresso**.

**Segurança:** o endpoint de escrita só aceita Host local e origem
permitida. CORS não substitui autenticação; a aplicação foi projetada para
uso em loopback e não pode ser exposta a redes públicas. OAuth GEE deve ser
previamente configurado no computador; processos iniciados pela interface
não solicitam login interativo.

Para verificar, use:
`python -m unittest discover -s backend/tests -v`.


## Distribuição unificada

Depois de executar `cd frontend && npm ci && npm run build` uma vez,
use `python iniciar_burngeoflow.py`. O FastAPI serve os arquivos
gerados em `frontend/dist/` na mesma origem da API, mantendo as rotas
`/api` e `/docs` prioritárias. A interface compilada utiliza
a URL de origem da página como endpoint padrão, inclusive quando a porta
local muda. No modo desenvolvimento, o Vite mantém endpoint 8000.

O backend **não** remove a CLI nem altera os GeoJSONs. O código no navegador
usa mensagens assíncronas e solicita geometrias por dia e camada.
A execução remota de subprocessos fica restrita ao worker local e aos
argumentos conhecidos. Não iniciar esta aplicação em 0.0.0.0 sem revisão
de autenticação e controles de acesso.
