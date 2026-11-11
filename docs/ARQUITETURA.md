# Arquitetura do BurnGeoFlow

O BurnGeoFlow é um pacote Python independente do projeto de pesquisa original.
A pasta `resultados/` na raiz não é necessária: cada execução grava em `execucoes/<ID>/resultados/`.

| Local | Responsabilidade |
| --- | --- |
| executar_pipeline.py | Entrada CLI, execução, logs, retomada |
| burngeoflow/config.py | Configuração não sensível do acesso GEE |
| burngeoflow/aquisicao/earth_engine.py | Consulta GlobFire, constrói P1/P2 acumulados e exporta GeoJSON por páginas |
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
