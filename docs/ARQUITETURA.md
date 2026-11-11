# Arquitetura do BurnGeoFlow

O BurnGeoFlow é um pacote Python independente do projeto de pesquisa original.
A pasta `resultados/` na raiz não é necessária: cada execução grava em `execucoes/<ID>/resultados/`.

| Local | Responsabilidade |
| --- | --- |
| executar_pipeline.py | Entrada CLI, execução, logs, retomada |
| burngeoflow/config.py | Configuração não sensível do acesso GEE |
| burngeoflow/aquisicao/earth_engine.py | Autenticação e consulta GlobFire; geração automática de P1/P2 pendente |
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

O modo GEE de aquisição completa ainda não está liberado: a Etapa 7.2
implementará a transformação e exportação automática de P1/P2, e deverá
demonstrar equivalência com a linha de base Pantanal 24340828.
