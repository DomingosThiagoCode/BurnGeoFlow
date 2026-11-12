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
