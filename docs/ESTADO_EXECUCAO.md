# Estado de execução e mapa anti-retrabalho — BurnGeoFlow

> **Última reconciliação:** 2026-11-26, depois dos merges #53, #51, #49 e #52; GitHub remoto verificado, sem acesso ao disco local.
> **Tipo:** fotografia operacional que DEVE ser reconciliada com issues, PRs, commits e arquivos a cada nova sessão.
> **Regra:** `main` ≠ PR aberto ≠ experimento validado ≠ conclusão científica.
> **Ponto de entrada para agentes:** [AGENTS.md](../AGENTS.md), [COORDENACAO_AGENTES.md](COORDENACAO_AGENTES.md), [METODOLOGIA.md](METODOLOGIA.md) e [ROTEIRO.md](ROTEIRO.md).

## Marco de integração seguinte (26/11/2026): catálogo e E2 experimental integrados

- **[PR #49](https://github.com/DomingosThiagoCode/BurnGeoFlow/pull/49) MESCLADA** no commit [`af99a2e`](https://github.com/DomingosThiagoCode/BurnGeoFlow/commit/af99a2e69f5590ec1f99416a32a0e5b9dbb1f654). UF/Brasil com malha IBGE, desenho de AOI e cache, com [CI da main aprovada](https://github.com/DomingosThiagoCode/BurnGeoFlow/actions/runs/45848420608). **Issue #31 permanece aberta** somente pelos requisitos ainda não homologados com IBGE/GEE reais e eventuais critérios restantes.
- **[PR #52](https://github.com/DomingosThiagoCode/BurnGeoFlow/pull/52) MESCLADA** no commit [`327fee2`](https://github.com/DomingosThiagoCode/BurnGeoFlow/commit/327fee2c282178b16866aa05696e5b20cb10105c), depois da [CI completa do conjunto integrado aprovada](https://github.com/DomingosThiagoCode/BurnGeoFlow/actions/runs/45849937965). P1 conectado por contato usa união de cobertura (sem somar área compartilhada duas vezes); gera auditoria de `Σ áreas − área da união` e mantém ranks de origem. P2 retrospectivo, balanço D-005 por calendário P2, hashes dos produtos e painel de checkpoints estão **na main em modo experimental/versionado**, sem substituir a execução antiga. Otimização STRtree para vizinho mais próximo da branch `codex/issue-34-indice-vizinhanca` também entrou nessa PR.
- **Evidência científica versus teste:** os testes automatizados do merge provaram contratos sintéticos, não a execução v2 ponta a ponta em 24340828/24194371. Reprojeção WGS84/LAEA, geometrias inválidas, critérios quantitativos D-013/D-014 e integração integral TR/IGT seguem pendentes. **Issues #3/#34/#44/#45/#46/#47 não são fechadas por esse merge**.
- **CI da main após #52:** [workflow](https://github.com/DomingosThiagoCode/BurnGeoFlow/actions/runs/45850186229). Consultar o status final; não presumir verde por haver CI aprovada antes do merge.
- **A branch `agente/integracao-e2` contém histórico e trabalho do Codex, mas é anterior aos merges atuais.** Reconciliar diferenças, não importar os 53 commits indiscriminadamente. O commit mencionado `947a82c` não foi localizado no remoto durante a auditoria anterior.

> Abaixo constam registros históricos de quando #49/#51/#52/#53 eram PRs abertas. **Este marco prevalece para o estado atual.** Alterações científicas adicionais devem atualizar o estado em marcos verificáveis.

## Marco de integração de 26/11/2026: entregas efetivas na main

- **[PR #53](https://github.com/DomingosThiagoCode/BurnGeoFlow/pull/53) MESCLADA** por squash no commit [`5fbc82f`](https://github.com/DomingosThiagoCode/BurnGeoFlow/commit/5fbc82f347812e8b37d38aeb3794ef66815c321f). GEE: validação pré-cache, preservação de página corrompida e hash SHA-256 de brutos/publicados. [CI da main após #53 aprovada nos três jobs](https://github.com/DomingosThiagoCode/BurnGeoFlow/actions/runs/45846590746). **Issue #2 segue aberta**, pois equivalência remota GEE/local não foi comprovada.
- **[PR #51](https://github.com/DomingosThiagoCode/BurnGeoFlow/pull/51) MESCLADA** por squash no commit [`2e5781c`](https://github.com/DomingosThiagoCode/BurnGeoFlow/commit/2e5781cb0cc92fd9e4a4d01a7df0b6a943429c9e). Diagnóstico em etapa de linhagens, com interseção duplicada, ranks e arquivo de evidência sem alterar geometrias. [CI da main após #51](https://github.com/DomingosThiagoCode/BurnGeoFlow/actions/runs/45846849159): verificar conclusão antes de anunciar resultado. **Issue #44 segue aberta**, pois não existe reparo topológico científico homologado.
- **[PR #49](https://github.com/DomingosThiagoCode/BurnGeoFlow/pull/49) aberta e DRAFT:** catálogo ampliado (UF/Brasil/AOI desenhada), CI aprovada na branch; requer reconciliação com o HEAD da main e testes reais IBGE/GEE. O GitHub retornou mergeabilidade `unknown` na consulta deste marco: **não afirmar conflito como comprovado** até nova verificação. O catálogo por bioma já existia na main.
- **[PR #52](https://github.com/DomingosThiagoCode/BurnGeoFlow/pull/52) aberta e DRAFT:** P1/P2 v2 e checkpoints experimentais; CI na branch não equivale à integração científica. A branch `agente/integracao-e2` tem contratos/trabalho posteriores e divergiu da PR; comparar antes de qualquer merge.
- **Nenhum outro PR ou issue criado por causa destes dois merges.** A investigação de faces `investigacao/d013-d014-faces` é experimento segregado, não correção aprovada nem produto de produção.
- **Nada de reaquisição GEE dos IDs 24340828 e 24194371** sem confirmação de ausência/corrupção dos insumos locais. Os dois casos ainda aguardam reprocessamento integral na metodologia nova.
- **Outras evidências remotas:** `agente/integracao-e2` em `148471e` com CI verde; `947a82c` não localizado remotamente na última investigação, pode existir apenas no workspace original do Codex.

> Esta seção é o estado pós-merge. Notas históricas abaixo devem ser interpretadas conforme este marco, nunca como prova de PR ainda aberta.

## 0. Resumo executivo, sem ambiguidades

1. **A metodologia científica D-001 a D-016 está documentada e conceitualmente aprovada**, mas sua implementação integral e validação NÃO estão concluídas.
2. **A `main` ainda executa o pipeline científico legado:** P1 sem o agrupamento por contato da D-002 como produto oficial e P2 progressivo a partir do maior componente inicial, incompatível com a D-001. NÃO declarar saída antiga como resultado da nova metodologia.
3. **PR #52 (MESCLADA na `main`):** pré-processador P1 conectado/P2 retrospectivo, auditoria de cobertura, balanço D-005 e checkpoints. O fluxo permanece experimental e não integrado a todas as etapas finais; NÃO permite reprocessamento científico completo.
4. **PR #51 (MESCLADA na `main`):** diagnóstico da falha topológica de linhagens do ID 24194371. Não contém correção científica da causa.
5. **PR #49 (MESCLADA na `main`):** catálogo por UF/Brasil e AOI desenhada; faltam homologação remota de limites IBGE e GEE autenticado.
6. **Landing narrativa:** primeira versão JÁ EXISTE na `main`, em `/apresentacao/`. Issue #50 trata da evolução e homologação, NÃO de criar outra landing do zero.
7. **Não reexecutar aquisição GEE dos IDs 24340828 e 24194371** só para testar uma mudança de pipeline. Primeiro localizar/verificar os insumos locais e seus hashes. Não presumir que os arquivos locais estão presentes nesta sessão.

## 1. Estado da `main` (comprovado pelos arquivos do repositório)

| Área | Já na `main` | Ainda NÃO é |
| --- | --- | --- |
| Aquisição | Consulta GlobFire v2/GEE, caminhos interativo e batch, cache/retomada, verificação de páginas e hashes de arquivos (#53), P1/P2 legados | Equivalência autenticada GEE/local não concluída; metodologia P2 retrospectiva |
| Orquestrador | `executar_pipeline.py`, oito etapas, `execucao.json`, hashes das entradas, assinatura de código e reaproveitamento de etapas | Motor integralmente atualizado à D-001/D-002, auditoria completa de perdas/versões ou retomada fina de todos os subpassos |
| API | FastAPI, leitura de eventos/GeoJSONs/séries, jobs SQLite/logs e inspeção de hashes/checkpoints por ID (#52) | Reprocessamento completo v2 orquestrado automaticamente |
| Atlas | React/TypeScript, mapa, P1/P2 legados, séries e indicadores, execução por ID | Navegação final modular (#43), rosáceas interativas (#42), design definitivo |
| Catálogo | Consulta leve por bioma/UF/Brasil/desenho, filtro temporal, cache JSON e encaminhamento para processamento (#49) | Homologação real com GEE/IBGE; paginação de 5 por página (#40) |
| Landing | `frontend/src/story/`, `frontend/public/story/24340828.json`, oito cenas em `/apresentacao/` | Homepage definitiva, dados P2 revisados, design final da issue #50 |
| Testes | CI de API, frontend, Chromium, regressão do código legado | Validação independente de satélite, execução científica v2 completa nos dois casos |

Documentos de referência já existentes: `docs/ARQUITETURA.md`, `docs/REFERENCIA_OPERACIONAL.md`, `docs/PROVENIENCIA.md`, `docs/LANDING_SCROLLYTELLING.md` e `docs/BACKLOG_REFACTOR.md`.

**Atenção:** existência de teste automatizado aprovado ou visualização bonita NÃO prova validade física das observações MODIS nem validade científica dos indicadores.

## 2. Histórico de trabalho desenvolvido antes dos merges: NÃO duplicar

| PR e issue(s) | Branch e HEAD inspecionado | Entrega técnica efetiva | Evidência CI no HEAD | O que NÃO foi entregue |
| --- | --- | --- | --- | --- |
| [#52](https://github.com/DomingosThiagoCode/BurnGeoFlow/pull/52), issues #3/#45/#34/#46 (parcial) | `feat/e2-metodologia-v2-checkpoints`, `79c42fb8` | `processamento/metodologia_v2.py`: agrupamento P1 por contato e P2 retrospectivo, bloqueio de sobreposições; `--preparar-metodologia-v2` só local; derivados versionados; manifesto e progresso por data; SHA do código/insumos/saídas; API `/api/events/{id}/pipeline-status`; `frontend/src/components/PipelineStatusPanel.tsx`, testes. | [Aprovado](https://github.com/DomingosThiagoCode/BurnGeoFlow/actions/runs/45830497673) | Pipeline v2 oficial; TR/IGT e integração adaptados à duração menor de P2; recuperação completa de checkpoints; validação nos dois IDs reais; tratamento científico definitivo de todas as inconsistências |
| [#49](https://github.com/DomingosThiagoCode/BurnGeoFlow/pull/49), issue #31 | `feat/31-catalogo-completo-aoi`, `3ebdc062` | Limites estaduais e Brasil IBGE 2024, cache de malhas, seleção de UF, polígono desenhado via `AoiDrawMap.tsx`, filtros e testes de contrato | [Aprovado](https://github.com/DomingosThiagoCode/BurnGeoFlow/actions/runs/45822318498) | Homologação dos arquivos oficiais reais/consultas GEE para novas AOIs; integração/merge; paginação #40 |

**As PRs #49, #51, #52 e #53 do histórico acima estão MESCLADAS na main.** O texto e a tabela são registros de estágio anterior. CI verde não equivale a validação científica ou autorização para substituir produtos legados.

### Arquivos com provável colisão

- A `main` agora contém o diagnóstico da #51 em `burngeoflow/processamento/linhagens.py`; novos desenvolvimentos nesse arquivo devem preservar a instrumentação.
- PR #52 usa `executar_pipeline.py`, `burngeoflow/processamento/metodologia_v2.py`, `backend/app/api/routes.py`, `backend/app/services/estado_pipeline.py`, `frontend/src/components/JobsPanel.tsx`, `PipelineStatusPanel.tsx` e `frontend/src/atlas-theme.css`.
- PR #49 usa `backend/app/api/catalogo.py`, `burngeoflow/aquisicao/catalogo.py`, `limites_ibge.py`, `frontend/src/components/CatalogoPanel.tsx`, `AoiDrawMap.tsx` e `atlas-theme.css`.
- **Colisão real de CSS:** PRs #49 e #52 alteram `frontend/src/atlas-theme.css`. Integração sequencial e resolução manual são necessárias.
- **Colisão científica potencial:** #3 (P1/linhagens) e #45 (P2) compartilham contratos; um único responsável deve integrar a versão científica e revisar a PR #51 antes de adaptar linhagens.

## 3. Casos de desenvolvimento, sem novas aquisições

| Evento | Estado histórico observado | Estado sob D-001/D-002 |
| --- | --- | --- |
| **24340828**, Pantanal/2020 | 947 registros de fonte GlobFire, 57 datas; P1 legado com 978 feições, P2 legado com 57; pipeline antigo concluiu no ambiente local do usuário | **Não reprocessado integralmente nem validado**. Necessário conferir arquivos locais e regenerar produtos v2, sem substituição silenciosa. |
| **24194371**, 2020 | 18.175 registros de fonte, 128 datas; P1 legado com 30.795 feições. Aquisição anterior chegou a gerar produtos. `linhagens` falhou em 2020-09-10, **rank 97**, porque a soma das interseções superou a área do patch | **Bloqueado** até diagnóstico/correção justificada #44 e compatibilização científica v2. **Não** é um caso de validação independente. |

Números acima são **histórico documentado**, não garantia de que arquivos ainda existem no computador do usuário. O manifesto e os arquivos efetivos no disco local são a fonte para disponibilidade e integridade atual.

**Distinção científica:** os dados representam evolução de área QUEIMADA ACUMULADA, não movimento medido de uma frente de fogo. Crescimento geométrico de P2 pode incluir fusão/incorporação de área previamente queimada.

## 4. Pendências reais e bloqueios, na ordem de dependências

| Fila | Issue | Trabalho restante | Bloqueio / critério |
| --- | --- | --- | --- |
| P0 | [#44](https://github.com/DomingosThiagoCode/BurnGeoFlow/issues/44) | Executar diagnóstico #51 no P1 real, identificar origem da sobreposição/excesso, aprovar política de reparo sem apagar evidência | Acesso aos arquivos reais 24194371; D-013/D-014 |
| P0 | [#2](https://github.com/DomingosThiagoCode/BurnGeoFlow/issues/2) | Conferir aquisição, fontes locais, hashes e equivalência GEE/local; casos limítrofes | Evidência em dados reais; não baixar de novo sem necessidade |
| P0 | [#3](https://github.com/DomingosThiagoCode/BurnGeoFlow/issues/3) | Consolidar P1 por contato, auditoria intradata, rank/métricas, grafo/linhagens e testes reais | #44, D-002/D-013/D-014; aproveitar #52 |
| P0 | [#45](https://github.com/DomingosThiagoCode/BurnGeoFlow/issues/45) | Concluir/validar P2 retrospectivo, desempates, ausência de ancestrais, representatividade; integrar no fluxo | P1 final validado #3, D-001/D-003/D-004/D-007; aproveitar #52 |
| P1 | [#34](https://github.com/DomingosThiagoCode/BurnGeoFlow/issues/34) | Checkpoints reproduzíveis completos, invalidação por dependência, estado de subtarefas, desempenho/memória e arquivo de diagnóstico em falhas | #52 é apenas inspeção e progresso preliminar; não é solução completa |
| P1 | [#46](https://github.com/DomingosThiagoCode/BurnGeoFlow/issues/46) | Adequar validadores e `analises/regioes_moveis.py`, `incrementos.py`, `tr_igt.py`, `integracao.py`, `robustez.py`, API e atlas a P2 com menos datas; D-005–D-012 | Antes, diversos contratos exigem `set(datas_p1)==set(datas_p2)`. NÃO forçar o mesmo período |
| P1 | [#47](https://github.com/DomingosThiagoCode/BurnGeoFlow/issues/47) | Ampliar testes sintéticos, medir invariantes, regressão real e avaliação exploratória TR/IGT | Correção E2 não é validação científica E4 |
| P2 | [#31](https://github.com/DomingosThiagoCode/BurnGeoFlow/issues/31) | Homologação real da #49, merge após aprovação | IBGE/GEE real |
| P2 | [#40](https://github.com/DomingosThiagoCode/BurnGeoFlow/issues/40), [#43](https://github.com/DomingosThiagoCode/BurnGeoFlow/issues/43), [#42](https://github.com/DomingosThiagoCode/BurnGeoFlow/issues/42) | Paginação, navegação modular, rosáceas interativas | Evitar colisão com #49/#52 e terminologia antes de #46 |
| P2 | [#41](https://github.com/DomingosThiagoCode/BurnGeoFlow/issues/41), [#50](https://github.com/DomingosThiagoCode/BurnGeoFlow/issues/50) | README/documentação e polimento da landing existente | Landing deve ser atualizada com P2 v2 só após validade metodológica |
| P3 | [#48](https://github.com/DomingosThiagoCode/BurnGeoFlow/issues/48), [#4](https://github.com/DomingosThiagoCode/BurnGeoFlow/issues/4) | Estudo com novos incêndios, validação e distribuição | E2/E3/E4 antes da avaliação independente E5 |

## 5. Inventário dos arquivos de checkpoints e respectivos limites

**Na `main` (legado):**
- `execucoes/<ID>/dados/estudo_caso_<ID>/brutos_gee/`: arquivos originais quando a aquisição GEE foi realizada. Nem toda execução possui esse diretório.
- `execucoes/<ID>/dados/estudo_caso_<ID>/P1_componentes_<ID>.geojson` e `P2_regiao_movel_<ID>.geojson`: produtos locais, atualmente **legados**, que NÃO devem ser sobrescritos.
- `execucoes/<ID>/execucao.json`: manifesto de etapas legadas; `resultados/etapa1...etapa6/`: relatórios e derivados; `logs/`: logs por etapa. Testar SHA, assinatura do código, presença e integridade dos artefatos antes de afirmar que estão atuais.
- `execucoes/.burngeoflow/jobs.sqlite3` e `execucoes/.burngeoflow/logs/`: histórico de jobs e logs de execução. Histórico de job concluído não comprova validade sob D-001/D-002.

**Somente na PR #52, até merge:**
- `--preparar-metodologia-v2`: usa P1 local; **não invoca GEE** e **não executa o pipeline científico final**.
- `execucoes/<ID>/dados/estudo_caso_<ID>/derivados_v2/<versao>/`: P1/P2 experimentais separados; `manifesto_metodologia.json`, `estado_preprocessamento.json` e, se falhar, `diagnostico_bloqueio.json`.
- `GET /api/events/<ID>/pipeline-status` e o botão `Inspecionar arquivos` no painel: leitura sob demanda de brutos, hash, versão, faltantes, etapas legadas e erros. O progresso registrado por datas **não é barra de progresso de execução integral nem garante processo ativo**.
- O botão principal `Executar` **continua usando o pipeline legado**; mesmo após a PR #52, NÃO o anunciar como botão de reprocessamento v2.

**Na `main` após o merge da PR #51:**
- `resultados/etapa3/diagnostico_topologia_<ID>_<data>_<lado>_r<rank>.json`: evidência quando a soma de interseções viola o limite existente.

## 6. Definição explícita de “feito” e “não feito”

**FEITO e integrado na main:** componentes e testes das PRs #49/#51/#52/#53. **Ainda não integrado/homologado:** trabalho residual da branch `agente/integracao-e2`, tratamento numérico de D-013/D-014, processamento completo v2 dos dois IDs.

**FEITO na `main`:** API/atlas/landing inicial/catálogo ampliado #49/worker GEE batch/estágios científicos legados, cache/proveniência #53, diagnóstico de linhagens #51 e preparo v2 experimental/checkpoints/balanço D-005/STRtree #52.

**NÃO FEITO / NÃO COMPROVADO:**
- Aprovação da política numérica de tolerâncias e reparação em todos os casos;
- Diagnóstico real da origem topológica em 24194371 e correção;
- P1 conectado e P2 retrospectivo como **único fluxo oficial de ponta a ponta**;
- Suporte integral a P2 com menos datas em validação, TR/IGT, integração, robustez, API, gráficos e série;
- Recuperação seletiva completa, com dependências e backup dos derivados antigos;
- Reprocessamento científico integral dos IDs 24340828 e 24194371 sob a metodologia v2;
- Homologação visual/operacional da landing final e do catálogo ampliado com serviços externos;
- Validação científica independente por outros eventos/sensores; publicação/release final.

## 7. Retomada recomendada: ação exata, evitando retrabalho

1. Verificar issues e PRs vivos: #49/#51/#52/#53 já foram mescladas. Conferir `gh issue view 44`, `gh issue view 3`, `gh issue view 45`, `gh issue view 46`. NÃO abrir PR duplicada para componentes que já estão na main.
2. Usar o diagnóstico #51 **já presente na main** nos arquivos reais de 24194371, sem readquirir GEE; preservar SHA de entrada e registrar evidência real em #44.
3. Em paralelo, aproveitar o código da PR #52 **já na main** para compatibilizar TR/IGT, demais validadores e visualização com P2 de início próprio (#46); **não gerar indicadores finais pela v2 até compatibilizar a cadeia inteira**.
4. Homologar catálogo #49 **já na main** contra IBGE/GEE real quando houver ambiente, sem reimplementar nem iniciar aquisição completa de um ID para testar o catálogo.
5. Após revisão/homologação e autorização de merge, integrar PRs de modo sequencial; resolver colisões e repetir CI no HEAD integrado.
6. **Só depois:** reprocessar os dois IDs a partir dos insumos locais válidos, com backup/versionamento, checkpoints, relatórios e testes reais.

### Regras anti-retrabalho para todos os agentes

- **Antes de escrever código:** verificar esta tabela, a issue e PR associadas, SHA atual e proprietário do conjunto de arquivos em [COORDENACAO_AGENTES.md](COORDENACAO_AGENTES.md).
- **Uma tarefa, um dono de integração.** Não abrir PR paralela duplicada sobre trabalho em curso. Agentes auxiliares fornecem testes, análise ou commits para o dono.
- Separar no relatório: `Implementado na branch`, `CI aprovado`, `Integrado na main`, `Homologado em dados reais`, `Validado cientificamente`. Esses estados NÃO são equivalentes.
- Nunca falsificar testes concluídos, status de tarefas do GEE ou existência de dados locais.
- Atualizar este documento **apenas em marcos** (merge, erro real diagnosticado, mudança de escopo/estado), conciliando com GitHub, e evitar commits de status a cada execução de CI.
