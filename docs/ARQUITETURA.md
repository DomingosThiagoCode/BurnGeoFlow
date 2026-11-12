# Arquitetura do BurnGeoFlow

O BurnGeoFlow é um pacote Python independente do projeto de pesquisa original.
A pasta `resultados/` na raiz não é necessária: cada execução grava em `execucoes/<ID>/resultados/`.

| Local | Responsabilidade |
| --- | --- |
| executar_pipeline.py | Entrada CLI, execução, logs, retomada |
| burngeoflow/config.py | Configuração não sensível do acesso GEE |
| burngeoflow/aquisicao/earth_engine.py | Consulta GlobFire, gera P1/P2, exporta com checkpoint por página e salva entradas brutas |
| burngeoflow/aquisicao/geometrias.py | Diagnóstico, normalização auditada de coleções e tratamento de feições sem área |
| burngeoflow/aquisicao/dados_referencia.py | Baixa amostra pública com hash para testes de regressão |
| burngeoflow/processamento/componentes.py | Organização das componentes P1 por data |
| burngeoflow/processamento/conectividade.py | Contatos geométricos, incluindo vértices |
| burngeoflow/processamento/linhagens.py | Linhagens temporais pais-filhos |
| burngeoflow/analises/ | Paisagem, TR, IGT, análise integrada |
| burngeoflow/validacao/ | Validação numérica, auditoria e robustez |
| burngeoflow/relatorios/ | Síntese dos registros de execução |
| tests/ | Contratos e testes de regressão |

O método científico previamente implementado foi transferido para módulos
sem alterações de fórmulas nesta refatoração. A política de conectividade por
vértice já existe como função isolada testável, mas sua integração analítica
será uma entrega da Etapa 7.3.

O JavaScript do GEE e os SQLs de experimentação continuam preservados no
[CDG_incendio](https://github.com/DomingosThiagoCode/CDG_incendio),
não no produto BurnGeoFlow.

A Etapa 7.2 implementa P1/P2 pelo GEE e exporta via `ee.data.computeFeatures`.
O GitHub Actions testa a aquisição com mocks, sem credenciais Google.
A equivalência geométrica com os resultados históricos do Pantanal 24340828
precisa ser aferida numa execução autenticada real. Para eventos grandes,
a exportação paginada pode exigir futura alternativa em lote.

## Segurança e reprocessamento

O cache de páginas usa chave vinculada ao ID, ano, parâmetros e versão
da construção. Dados brutos são preservados antes da validação, e
`--origem brutos` pode recuperar os produtos sem nova requisição ao GEE.
Nenhuma geometria não poligonal com área positiva é descartada:
a execução é interrompida e um diagnóstico persistente é gerado.

## Topologia nas análises TR/IGT

`burngeoflow/validacao/topologia_p2.py` é o módulo compartilhado para
reconciliação entre P2 e P1 após reprojeção LAEA. O `make_valid` é
permitido apenas em memória e se o resultado for equivalente ao P1
projetado e validado dentro de tolerância explícita de área simétrica.
As análises registram o número de reparos, as datas/ranks envolvidos
e a diferença residual. Falhas acima da tolerância não são disfarçadas.

A consolidação `burngeoflow/analises/tr_igt.py` também reutiliza o
P1 LAEA projetado canônico para perdas e incrementos, conferindo todos os
registros P2 com `reconciliar_p2`. Os arquivos originais permanecem intactos;
o resumo consolidado registra as diferenças geométricas e intervenções.

## Arquitetura de consulta desacoplada (2026)

`frontend/`: interface React/TS, MapLibre e gráficos SVG.
`backend/app/`: rotas FastAPI, contratos, configuração e repositórios.
`burngeoflow/`: permanece como **núcleo científico do produto**, sem
duplicar fórmulas no backend ou frontend.

Persistência primária continua sendo P1/P2 GeoJSON e relatórios CSV/JSON.
A API mantém índice JSON Lines **reconstruível** por data em
`execucoes/<ID>/.visualizador_index/`, sem migrar geometrias para SQL.
SQLite será adicionado apenas caso o gerenciamento de jobs exigir
persistência transacional. Sem dependência operacional PostgreSQL.

O Streamlit existente é interface legada de compatibilidade temporária,
mantida até o frontend React estar homologado. Não executar a API em rede
externa sem autenticação: host local 127.0.0.1.
